"""Exercise the upgrade of real single-organization records."""
import tempfile
from pathlib import Path
from django.contrib.auth.hashers import make_password
from django.test import TransactionTestCase,override_settings
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from apps.organizations.scoping import organization_scope

class LegacyUpgradeTests(TransactionTestCase):
    def test_legacy_content_accounts_groups_and_settings_survive(self):
        media=tempfile.TemporaryDirectory()
        self.addCleanup(media.cleanup)
        media_override=override_settings(MEDIA_ROOT=media.name)
        media_override.enable();self.addCleanup(media_override.disable)
        executor=MigrationExecutor(connection)
        latest=executor.loader.graph.leaf_nodes()
        before=[('organizations','0001_initial'),('core','0002_alter_siteconfiguration_primary_color'),('menus','0002_default_navigation'),('manuals','0002_alter_manualpermissionassignment_action'),('integrations','0001_initial')]
        try:
            executor.migrate(before)
            apps=executor.loader.project_state(before).apps
            User=apps.get_model('auth','User');Group=apps.get_model('auth','Group')
            user=User.objects.create(username='legacy-admin',password=make_password('Legacy-password-test-129!'),is_active=True,is_staff=True,is_superuser=False)
            group=Group.objects.create(name='legacy-editors');user.groups.add(group)
            site=apps.get_model('core','SiteConfiguration').objects.create(name='Legacy branding')
            menu=apps.get_model('menus','Menu').objects.get(code='dashboard')
            menu.name='Legacy dashboard';menu.save();menu.allowed_groups.add(group)
            space=apps.get_model('manuals','ManualSpace').objects.create(name='Legacy manuals')
            space.edit_groups.add(group);space.view_groups.add(group)
            node=apps.get_model('manuals','ManualNode').objects.create(space=space,title='Legacy document')
            revision=apps.get_model('manuals','ManualRevision').objects.create(node=node,number=1,title='Legacy publication',markdown='# Legacy body',html='<h1>Legacy body</h1>',author=user)
            node.draft=revision;node.published=revision;node.version=1;node.save()
            file_path=Path(media.name)/'manual_private'/'legacy.txt'
            file_path.parent.mkdir(parents=True,exist_ok=True)
            file_path.write_bytes(b'legacy private attachment bytes')
            attachment=apps.get_model('manuals','ManualAttachment').objects.create(node=node,revision=revision,name='legacy.txt',file='manual_private/legacy.txt',author=user)
            connection_obj=apps.get_model('integrations','Connection').objects.create(name='legacy-api',provider='llm',owner=user,encrypted_secrets='opaque-preserved-ciphertext')
            executor=MigrationExecutor(connection);executor.migrate(latest)
            from .models import Organization,Membership,OrganizationGroup
            from apps.manuals.models import ManualNode,ManualAttachment
            from apps.core.models import SiteConfiguration
            from apps.menus.models import Menu
            from apps.integrations.models import Connection
            org=Organization.objects.get(slug='legacy')
            with organization_scope(org):
                member=Membership.objects.get(user_id=user.pk)
                self.assertEqual(member.role,'admin')
                self.assertEqual(set(member.groups.values_list('group_id',flat=True)),{group.pk})
                self.assertEqual(OrganizationGroup.objects.get(group_id=group.pk).name,'legacy-editors')
                restored=ManualNode.objects.get(pk=node.pk)
                self.assertEqual(restored.published_id,revision.pk)
                self.assertEqual(restored.draft_id,revision.pk)
                self.assertEqual(restored.published.markdown,'# Legacy body')
                self.assertEqual(restored.space.organization_id,org.pk)
                self.assertEqual(set(restored.space.edit_groups.values_list('pk',flat=True)),{group.pk})
                self.assertEqual(set(restored.space.view_groups.values_list('pk',flat=True)),{group.pk})
                restored_attachment=ManualAttachment.objects.get(pk=attachment.pk)
                self.assertEqual(restored_attachment.file.name,'manual_private/legacy.txt')
                with restored_attachment.file.open('rb') as preserved_file:
                    self.assertEqual(preserved_file.read(),b'legacy private attachment bytes')
                self.assertEqual(SiteConfiguration.objects.get(pk=site.pk).name,'Legacy branding')
                restored_menu=Menu.objects.get(pk=menu.pk)
                self.assertEqual(restored_menu.name,'Legacy dashboard')
                self.assertEqual(set(restored_menu.allowed_groups.values_list('pk',flat=True)),{group.pk})
                restored_connection=Connection.objects.get(pk=connection_obj.pk)
                self.assertEqual(restored_connection.organization_id,org.pk)
                self.assertEqual(restored_connection.encrypted_secrets,'opaque-preserved-ciphertext')
                self.assertFalse(member.user.is_superuser)
            response=self.client.post('/o/legacy/login/',{'username':'legacy-admin','password':'Legacy-password-test-129!'})
            self.assertEqual(response.status_code,302)
            self.assertEqual(self.client.get('/o/legacy/home/').status_code,200)
        finally:
            MigrationExecutor(connection).migrate(latest)
