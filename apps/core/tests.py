from apps.organizations.models import Organization, Membership, OrganizationGroup
from apps.organizations.scoping import organization_scope
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError, PermissionDenied
from cryptography.fernet import Fernet
from apps.menus.models import Menu
from apps.menus.permissions import can_access_menu
from apps.core.bootstrap import seed_platform
from apps.core.models import SiteConfiguration, AuditEvent
from apps.integrations.models import Connection, FeatureBinding, ConfigurationRevision
from apps.integrations.forms import FeatureBindingForm
from apps.integrations.services import save_binding, resolve_binding

@override_settings(SECURE_SSL_REDIRECT=False)
class PlatformTests(TestCase):
    def setUp(self):
        self.organization=Organization.objects.create(name='Test organization',slug='test-org')
        self.scope=organization_scope(self.organization);self.scope.__enter__()
        self.addCleanup(self.scope.__exit__,None,None,None)
        self.user=get_user_model().objects.create_user('reader',password='test-secret-xyz')
        self.admin=get_user_model().objects.create_superuser('administrator',password='test-secret-xyz')
        self.membership=Membership.objects.create(user=self.user,role='member')
        Membership.objects.create(user=self.admin,role='admin')
        seed_platform()
    def test_bootstrap_preserves_admin_changes(self):
        seed_platform()
        menu=Menu.objects.get(code='manuals.spaces');menu.name='운영자 지정 메뉴';menu.save()
        count=Menu.objects.count();seed_platform()
        menu.refresh_from_db()
        self.assertEqual(menu.name,'운영자 지정 메뉴');self.assertEqual(Menu.objects.count(),count)
    def test_group_ancestor_rule_is_server_enforced(self):
        group=Group.objects.create(name='restricted')
        wrapper=OrganizationGroup.objects.create(group=group,name=group.name)
        root=Menu.objects.create(code='private',name='private')
        root.allowed_groups.add(group)
        child=Menu.objects.create(code='private.home',name='Home',url='/home/',parent_menu=root)
        self.assertFalse(can_access_menu(self.user,child))
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/o/test-org/home/').status_code,403)
        self.membership.groups.add(wrapper)
        self.assertEqual(self.client.get('/o/test-org/home/').status_code,200)
        root.is_active=False;root.save()
        self.assertFalse(can_access_menu(self.admin,child))
    def test_menu_url_and_depth_validation(self):
        for url in ['javascript:alert(1)','//evil.example','/\\evil.example']:
            menu=Menu(organization=self.organization,name='bad',code='bad',url=url)
            with self.assertRaises(ValidationError):menu.full_clean()
        a=Menu.objects.create(code='a',name='a');b=Menu.objects.create(code='b',name='b',parent_menu=a)
        c=Menu.objects.create(code='c',name='c',parent_menu=b)
        with self.assertRaises(ValidationError):Menu(organization=self.organization,code='d',name='d',parent_menu=c).full_clean()
        a.parent_menu=c
        with self.assertRaises(ValidationError):a.full_clean()
    def test_staff_settings_denied_for_regular_user(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/o/test-org/settings/').status_code,403)
        self.assertEqual(self.client.get('/o/test-org/menus/').status_code,403)
        seed_platform()
        self.assertFalse(can_access_menu(self.user,Menu.objects.get(code='settings.organization')))
        self.assertTrue(can_access_menu(self.admin,Menu.objects.get(code='settings.organization')))
    def test_post_csrf_and_logout(self):
        from django.test import Client
        client=Client(enforce_csrf_checks=True);client.force_login(self.admin)
        self.assertEqual(client.post('/o/test-org/settings/',{'name':'Changed'}).status_code,403)
        self.assertEqual(client.get('/logout/').status_code,405)
    @override_settings(INTEGRATION_ENCRYPTION_KEY=Fernet.generate_key().decode())
    def test_encrypted_connection_and_isolation(self):
        connection=Connection(name='private',provider='llm',owner=self.admin)
        connection.set_secrets({'api_key':'sensitive-token'});connection.save()
        self.assertNotIn('sensitive-token',connection.encrypted_secrets)
        self.assertEqual(connection.secrets()['api_key'],'sensitive-token')
        self.assertFalse(connection.can_use(self.user))
        binding=FeatureBinding.objects.create(feature_code='manuals.ai',connection=connection)
        with self.assertRaises(PermissionDenied):resolve_binding(binding.feature_code,self.user)
        connection.shared=True;connection.save()
        self.assertTrue(connection.can_use(self.user))
        connection.config={'api_key':'cleartext'}
        with self.assertRaises(ValidationError):connection.full_clean()
    def test_binding_versions_and_audit(self):
        connection=Connection.objects.create(name='llm',provider='llm',owner=self.admin)
        values={'feature_code':'manuals.ai','connection':connection.pk,'config':'{}','field_mapping':'{}'}
        form=FeatureBindingForm(values);self.assertTrue(form.is_valid(),form.errors)
        binding=save_binding(form,self.admin)
        values['revision_token']=binding.revision
        form=FeatureBindingForm(values,instance=binding);self.assertTrue(form.is_valid(),form.errors)
        binding=save_binding(form,self.admin)
        self.assertEqual(binding.revision,2)
        self.assertEqual(ConfigurationRevision.objects.filter(binding=binding).count(),2)
        self.assertEqual(AuditEvent.objects.filter(action='binding.updated').count(),2)
    def test_changed_menu_url_does_not_bypass_registry_guard(self):
        group=Group.objects.create(name='private-manuals')
        OrganizationGroup.objects.create(group=group,name=group.name)
        menu=Menu.objects.get(code='manuals.spaces')
        menu.url='/changed/';menu.allowed_groups.add(group);menu.save()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/o/test-org/manuals/spaces/').status_code,403)
        self.assertEqual(self.client.get('/o/test-org/accounts/profile/').status_code,200)
    def test_inactive_user_cannot_use_shared_connection(self):
        connection=Connection.objects.create(name='shared',provider='llm',owner=self.admin,shared=True)
        self.user.is_active=False
        self.assertFalse(connection.can_use(self.user))
    @override_settings(INTEGRATION_ENCRYPTION_KEY=Fernet.generate_key().decode())
    def test_configuration_export_import_excludes_credentials_and_rolls_back(self):
        from apps.integrations.configuration import export_configuration, import_configuration
        connection=Connection(name='api',provider='llm',owner=self.admin)
        connection.set_secrets({'api_key':'private-token'});connection.save()
        data=export_configuration(self.admin)
        self.assertNotIn('private-token',str(data));self.assertNotIn('encrypted_secrets',str(data))
        invalid={'version':1,'connections':[{'name':'new-connection','provider':'llm','config':{}}],'resources':[{'name':'bad','connection':'missing'}]}
        with self.assertRaises(ValidationError):import_configuration(invalid,self.admin)
        self.assertFalse(Connection.objects.filter(name='new-connection').exists())
        import_configuration(data,self.admin)
        connection.refresh_from_db();self.assertEqual(connection.secrets()['api_key'],'private-token')
    def test_binding_restore_creates_new_revision_and_rejects_stale_tokens(self):
        connection=Connection.objects.create(name='restore',provider='llm',owner=self.admin)
        values={'feature_code':'manuals.ai','connection':connection.pk,'config':'{"model":"first"}','field_mapping':'{}'}
        form=FeatureBindingForm(values);self.assertTrue(form.is_valid(),form.errors)
        binding=save_binding(form,self.admin)
        values['revision_token']=1;values['config']='{"model":"second"}'
        form=FeatureBindingForm(values,instance=binding);self.assertTrue(form.is_valid(),form.errors)
        binding=save_binding(form,self.admin)
        self.client.force_login(self.admin)
        url=f'/o/test-org/settings/integrations/binding/{binding.pk}/revisions/1/restore/'
        self.assertEqual(self.client.post(url,{'revision_token':2}).status_code,302)
        binding.refresh_from_db();self.assertEqual(binding.revision,3);self.assertEqual(binding.config,{'model':'first'})
        self.client.post(url,{'revision_token':2})
        binding.refresh_from_db();self.assertEqual(binding.revision,3)
        values['revision_token']=2
        form=FeatureBindingForm(values,instance=binding);self.assertTrue(form.is_valid(),form.errors)
        with self.assertRaises(ValidationError):save_binding(form,self.admin)
    def test_configuration_import_cannot_overwrite_other_owner(self):
        from apps.integrations.configuration import import_configuration
        self.user.is_staff=True;self.user.save()
        Connection.objects.create(name='someone-elses',provider='llm',owner=self.admin)
        with self.assertRaises(PermissionDenied):
            import_configuration({'version':1,'connections':[{'name':'someone-elses','provider':'llm'}]},self.user)
