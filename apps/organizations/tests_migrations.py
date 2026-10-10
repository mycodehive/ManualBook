"""Exercise the upgrade of real single-organization records."""
from django.test import TransactionTestCase
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from apps.organizations.scoping import organization_scope

class LegacyUpgradeTests(TransactionTestCase):
    def test_legacy_content_accounts_groups_and_settings_survive(self):
        executor=MigrationExecutor(connection)
        latest=executor.loader.graph.leaf_nodes()
        before=[('organizations','0001_initial'),('core','0002_alter_siteconfiguration_primary_color'),('menus','0002_default_navigation'),('manuals','0002_alter_manualpermissionassignment_action'),('integrations','0001_initial')]
        try:
            executor.migrate(before)
            apps=executor.loader.project_state(before).apps
            User=apps.get_model('auth','User');Group=apps.get_model('auth','Group')
            user=User.objects.create(username='legacy-admin',is_active=True,is_staff=True,is_superuser=False)
            group=Group.objects.create(name='legacy-editors');user.groups.add(group)
            site=apps.get_model('core','SiteConfiguration').objects.create(name='Legacy branding')
            menu=apps.get_model('menus','Menu').objects.get(code='dashboard')
            menu.name='Legacy dashboard';menu.save();menu.allowed_groups.add(group)
            space=apps.get_model('manuals','ManualSpace').objects.create(name='Legacy manuals')
            space.edit_groups.add(group);space.view_groups.add(group)
            node=apps.get_model('manuals','ManualNode').objects.create(space=space,title='Legacy document')
            revision=apps.get_model('manuals','ManualRevision').objects.create(node=node,number=1,title='Legacy publication',markdown='# Legacy body',html='<h1>Legacy body</h1>',author=user)
            node.draft=revision;node.published=revision;node.version=1;node.save()
            attachment=apps.get_model('manuals','ManualAttachment').objects.create(node=node,revision=revision,name='legacy.txt',file='manual_private/legacy.txt',author=user)
            connection_obj=apps.get_model('integrations','Connection').objects.create(name='legacy-api',provider='llm',owner=user)
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
                self.assertEqual(ManualAttachment.objects.get(pk=attachment.pk).file.name,'manual_private/legacy.txt')
                self.assertEqual(SiteConfiguration.objects.get(pk=site.pk).name,'Legacy branding')
                self.assertEqual(Menu.objects.get(pk=menu.pk).name,'Legacy dashboard')
                self.assertEqual(Connection.objects.get(pk=connection_obj.pk).organization_id,org.pk)
                self.assertFalse(member.user.is_superuser)
        finally:
            MigrationExecutor(connection).migrate(latest)
