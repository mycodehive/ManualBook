"""Tenant boundary regression tests."""
import io
import tempfile
import zipfile
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from apps.organizations.models import Organization, Membership, OrganizationGroup, Department
from apps.organizations.scoping import organization_scope, current_organization, is_org_admin
from apps.core.bootstrap import seed_platform
from apps.core.models import SiteConfiguration, AuditEvent
from apps.menus.models import Menu
from apps.integrations.models import Connection, DataResource, FeatureBinding
from apps.manuals.models import ManualSpace, ManualNode, ManualRevision, ManualAttachment, ApprovalRequest
from apps.manuals.services import save_revision, publish, request_review

@override_settings(SECURE_SSL_REDIRECT=False)
class TenantIsolationTests(TestCase):
    def setUp(self):
        self.media=tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings_override=override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        User=get_user_model()
        self.a_admin=User.objects.create_user('a-admin',password='tenant-test-password!')
        self.a_user=User.objects.create_user('a-member',password='tenant-test-password!')
        self.b_admin=User.objects.create_user('b-admin',password='tenant-test-password!')
        self.b_user=User.objects.create_user('b-member',password='tenant-test-password!')
        self.superuser=User.objects.create_superuser('global-admin',password='tenant-test-password!')
        self.a=Organization.objects.create(name='Alpha',slug='alpha')
        self.b=Organization.objects.create(name='Beta',slug='beta')
        self.tenants={}
        for org,admin,user,marker in [(self.a,self.a_admin,self.a_user,'ALPHA-PRIVATE'),(self.b,self.b_admin,self.b_user,'BETA-PRIVATE')]:
            with organization_scope(org):
                seed_platform()
                group=OrganizationGroup.objects.create(organization=org,name='Editors')
                department=Department.objects.create(organization=org,name='Engineering')
                manager=Membership.objects.create(organization=org,user=admin,role='admin',department=department)
                member=Membership.objects.create(organization=org,user=user,role='member',department=department)
                manager.groups.add(group);member.groups.add(group)
                space=ManualSpace.objects.create(name='Operations',require_approval=False)
                space.edit_groups.add(group.group);space.view_groups.add(group.group)
                node=ManualNode.objects.create(space=space,title=marker)
                revision=save_revision(admin,node.pk,marker,'# '+marker,0)
                node.refresh_from_db();publish(admin,node);node.refresh_from_db()
                attachment=ManualAttachment.objects.create(node=node,revision=revision,file=SimpleUploadedFile(marker+'.txt',marker.encode()),name=marker+'.txt',author=admin)
                review=request_review(admin,node)
                connection=Connection.objects.create(name='shared',provider='llm',owner=admin,shared=True)
                self.tenants[org.slug]={'group':group,'department':department,'manager':manager,'member':member,'space':space,'node':node,'revision':revision,'attachment':attachment,'review':review,'connection':connection}
        self.assertIsNone(current_organization())

    def url(self,org,suffix):
        return '/o/'+org.slug+suffix

    def denied(self,response):
        self.assertIn(response.status_code,(403,404),response.content[:500])

    def test_default_manager_without_context_returns_no_tenant_rows(self):
        with organization_scope(None):
            for model in [Membership,OrganizationGroup,Department,SiteConfiguration,AuditEvent,Menu,Connection,DataResource,FeatureBinding,ManualSpace,ManualNode,ManualRevision,ManualAttachment,ApprovalRequest]:
                self.assertEqual(model.objects.count(),0,model.__name__)
            self.assertGreater(ManualNode.all_objects.count(),0)
            with self.assertRaises((ValidationError,PermissionDenied)):
                ManualSpace.objects.create(name='unscoped-write')

    def test_nested_scope_and_exception_restore_prior_context(self):
        with organization_scope(self.a):
            self.assertEqual(current_organization(),self.a)
            self.assertEqual(ManualNode.objects.get().title,'ALPHA-PRIVATE')
            with self.assertRaises(RuntimeError):
                with organization_scope(self.b):
                    self.assertEqual(ManualNode.objects.get().title,'BETA-PRIVATE')
                    raise RuntimeError('intentional regression fixture')
            self.assertEqual(current_organization(),self.a)
            self.assertEqual(ManualNode.objects.get().title,'ALPHA-PRIVATE')
        self.assertIsNone(current_organization())
        self.assertFalse(ManualNode.objects.exists())

    def test_slug_access_requires_active_membership(self):
        self.client.force_login(self.a_user)
        self.denied(self.client.get(self.url(self.b,'/manuals/')))
        with organization_scope(self.a):
            member=self.tenants['alpha']['member'];member.active=False;member.save()
        self.denied(self.client.get(self.url(self.a,'/manuals/')))
        self.assertIsNone(current_organization())
        self.assertFalse(ManualSpace.objects.exists())

    def test_inactive_organization_is_not_accessible(self):
        self.a.active=False;self.a.save()
        self.client.force_login(self.a_admin)
        self.denied(self.client.get(self.url(self.a,'/settings/')))
        self.assertIsNone(current_organization())

    def test_cross_organization_manual_ids_never_resolve(self):
        target=self.tenants['beta']
        self.client.force_login(self.a_user)
        from django.urls import reverse
        for name,key in [('page','node'),('edit','node'),('history','node'),('export_page','node'),('export_pdf','node'),('download','attachment'),('export_space','space'),('review_detail','review')]:
            path=reverse('manuals:'+name,args=[target[key].pk])
            self.denied(self.client.get(self.url(self.a,path)))
        before=target['node'].version
        path=reverse('manuals:autosave',args=[target['node'].pk])
        response=self.client.post(self.url(self.a,path),data='{"title":"stolen","markdown":"stolen","version":1}',content_type='application/json')
        self.denied(response)
        with organization_scope(self.b):
            target['node'].refresh_from_db();self.assertEqual(target['node'].version,before)

    def test_search_and_zip_export_exclude_other_organization(self):
        self.client.force_login(self.a_user)
        from django.urls import reverse
        response=self.client.get(self.url(self.a,reverse('manuals:index')))
        self.assertContains(response,'ALPHA-PRIVATE')
        self.assertNotContains(response,'BETA-PRIVATE')
        response=self.client.get(self.url(self.a,reverse('manuals:index'))+'?q=BETA')
        self.assertNotContains(response,'BETA-PRIVATE')
        response=self.client.get(self.url(self.a,reverse('manuals:export_space',args=[self.tenants['alpha']['space'].pk])))
        self.assertEqual(response.status_code,200)
        payload=b''.join(response.streaming_content)
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            content='\n'.join(archive.read(name).decode() for name in archive.namelist())
        self.assertIn('ALPHA-PRIVATE',content);self.assertNotIn('BETA-PRIVATE',content)

    def test_cross_tenant_foreign_keys_are_rejected(self):
        a=self.tenants['alpha'];b=self.tenants['beta']
        with organization_scope(self.a):
            invalid=[
                ManualNode(organization=self.a,space=b['space'],title='wrong-space'),
                ManualNode(organization=self.a,space=a['space'],parent=b['node'],title='wrong-parent'),
                ManualRevision(organization=self.a,node=b['node'],number=999,title='wrong-node',author=self.a_admin),
                ManualAttachment(organization=self.a,node=a['node'],revision=b['revision'],file='fixture.txt',name='wrong-revision'),
                FeatureBinding(organization=self.a,feature_code='wrong-connection',connection=b['connection']),
                Membership(organization=self.a,user=self.b_user,department=b['department'],role='member'),
            ]
            for obj in invalid:
                with self.subTest(model=type(obj).__name__):
                    with self.assertRaises(ValidationError): obj.full_clean()

    def test_global_auth_group_does_not_grant_membership_role(self):
        self.a_user.groups.add(self.tenants['beta']['group'].group)
        self.a_user.is_staff=True;self.a_user.save()
        with organization_scope(self.a): self.assertFalse(is_org_admin(self.a_user))
        self.client.force_login(self.a_user)
        self.denied(self.client.get(self.url(self.a,'/settings/')))
        self.denied(self.client.get(self.url(self.b,'/manuals/')))
        self.assertIn(self.client.get('/admin/').status_code,(302,403,404))

    def test_org_admin_cannot_set_global_privilege_flags(self):
        self.client.force_login(self.a_admin)
        data={'username':'created-by-org','email':'member@example.com','first_name':'Member','role':'member','active':'on','password':'Unique-tenant-password-927!','password_confirm':'Unique-tenant-password-927!','is_staff':'on','is_superuser':'on','department':self.tenants['alpha']['department'].pk,'groups':[self.tenants['alpha']['group'].pk]}
        response=self.client.post(self.url(self.a,'/organization/members/create/'),data)
        self.assertEqual(response.status_code,302,response.content[:500])
        from .backends import organization_username
        created=get_user_model().objects.get(username=organization_username(self.a,'created-by-org'))
        self.assertFalse(created.is_staff);self.assertFalse(created.is_superuser)
        with organization_scope(self.a): self.assertEqual(Membership.objects.get(user=created).role,'member')
        with organization_scope(self.b): self.assertFalse(Membership.objects.filter(user=created).exists())

    def test_org_admin_cannot_edit_foreign_membership_or_assign_foreign_group(self):
        self.client.force_login(self.a_admin)
        b=self.tenants['beta'];a=self.tenants['alpha']
        self.denied(self.client.get(self.url(self.a,'/organization/members/'+str(b['member'].pk)+'/edit/')))
        data={'username':'cross-group-attempt','email':'new@example.com','role':'member','active':'on','password':'Unique-tenant-password-927!','password_confirm':'Unique-tenant-password-927!','groups':[b['group'].pk]}
        response=self.client.post(self.url(self.a,'/organization/members/create/'),data)
        self.assertEqual(response.status_code,200,response.content[:500])
        from .backends import organization_username
        self.assertFalse(get_user_model().objects.filter(username=organization_username(self.a,'cross-group-attempt')).exists())
        with organization_scope(self.a): self.assertFalse(a['member'].groups.filter(pk=b['group'].pk).exists())

    def test_same_codes_and_settings_are_independent(self):
        with organization_scope(self.a):
            Menu.objects.create(code='same-code',name='A only')
            alpha=SiteConfiguration.objects.get();alpha.name='Alpha branding';alpha.save()
        with organization_scope(self.b):
            Menu.objects.create(code='same-code',name='B only')
            self.assertEqual(Menu.objects.get(code='same-code').name,'B only')
            self.assertNotEqual(SiteConfiguration.objects.get().name,'Alpha branding')
            before=Menu.objects.count();seed_platform();self.assertEqual(Menu.objects.count(),before)
        with organization_scope(self.a): self.assertEqual(Menu.objects.get(code='same-code').name,'A only')

    def test_superuser_can_switch_tenant_but_not_mix_relations(self):
        self.client.force_login(self.superuser)
        for org in [self.a,self.b]:
            self.assertEqual(self.client.get(self.url(org,'/settings/')).status_code,200)
            self.assertIsNone(current_organization())
        with organization_scope(self.a):
            node=ManualNode(organization=self.a,space=self.tenants['beta']['space'],title='cross-boundary')
            with self.assertRaises(ValidationError): node.full_clean()

    def test_corrupt_cross_tenant_publication_never_leaks(self):
        a=self.tenants['alpha'];b=self.tenants['beta']
        ManualNode.all_objects.filter(pk=a['node'].pk).update(published_id=b['revision'].pk)
        self.client.force_login(self.a_user)
        from django.urls import reverse
        self.denied(self.client.get(self.url(self.a,reverse('manuals:page',args=[a['node'].pk]))))
        response=self.client.get(self.url(self.a,reverse('manuals:index')))
        self.assertNotContains(response,'BETA-PRIVATE')
        self.assertIsNone(current_organization())

    def test_corrupt_attachment_revision_is_not_downloadable(self):
        a=self.tenants['alpha'];b=self.tenants['beta']
        ManualAttachment.all_objects.filter(pk=a['attachment'].pk).update(revision_id=b['revision'].pk)
        self.client.force_login(self.a_user)
        from django.urls import reverse
        self.denied(self.client.get(self.url(self.a,reverse('manuals:download',args=[a['attachment'].pk]))))

    def test_programmatic_cross_org_group_assignment_is_rejected(self):
        a=self.tenants['alpha'];b=self.tenants['beta']
        from django.db import transaction
        with organization_scope(self.a):
            with self.assertRaises((ValidationError,PermissionDenied)), transaction.atomic(): a['space'].view_groups.add(b['group'].group)
            self.assertFalse(a['space'].view_groups.filter(pk=b['group'].group_id).exists())

    def test_async_scopes_do_not_leak_between_tasks(self):
        import asyncio
        async def observe(org):
            with organization_scope(org):
                await asyncio.sleep(0)
                self.assertEqual(current_organization(),org)
                return current_organization().pk
        async def run(): return await asyncio.gather(observe(self.a),observe(self.b))
        self.assertEqual(asyncio.run(run()),[self.a.pk,self.b.pk])
        self.assertIsNone(current_organization())

    def test_canonical_navigation_links_keep_organization_slug(self):
        self.client.force_login(self.a_user)
        from django.urls import reverse
        response=self.client.get(self.url(self.a,reverse('manuals:spaces')))
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'/o/alpha/manuals/spaces/')
        self.assertNotContains(response,'/o/beta/')
        self.assertIsNone(current_organization())

    def test_repeated_login_failures_are_limited_per_organization(self):
        from .backends import organization_username
        with organization_scope(self.a):
            user=get_user_model().objects.create_user(organization_username(self.a,'same-user'),password='Unique-test-password-942!')
            Membership.objects.create(user=user)
        with organization_scope(self.b):
            user=get_user_model().objects.create_user(organization_username(self.b,'same-user'),password='Unique-test-password-942!')
            Membership.objects.create(user=user)
        for _ in range(5):
            self.assertEqual(self.client.post(self.url(self.a,'/login/'),{'username':'same-user','password':'wrong'}).status_code,200)
        blocked=self.client.post(self.url(self.a,'/login/'),{'username':'same-user','password':'Unique-test-password-942!'})
        self.assertEqual(blocked.status_code,429)
        self.assertIn('Retry-After',blocked)
        self.assertEqual(self.client.post(self.url(self.b,'/login/'),{'username':'same-user','password':'Unique-test-password-942!'}).status_code,302)

    def test_short_username_login_requires_its_own_organization(self):
        from .backends import organization_username
        with organization_scope(self.a):
            user=get_user_model().objects.create_user(organization_username(self.a,'local-user'),password='Unique-test-password-942!')
            Membership.objects.create(user=user)
        self.assertEqual(self.client.post(self.url(self.b,'/login/'),{'username':'local-user','password':'Unique-test-password-942!'}).status_code,200)
        self.assertEqual(self.client.post('/login/',{'username':user.username,'password':'Unique-test-password-942!'}).status_code,200)
        self.assertEqual(self.client.post(self.url(self.a,'/login/'),{'username':'local-user','password':'Unique-test-password-942!'}).status_code,302)

    def test_last_active_organization_admin_cannot_be_demoted(self):
        member=self.tenants['alpha']['manager']
        self.client.force_login(self.a_admin)
        response=self.client.post(self.url(self.a,f'/organization/members/{member.pk}/edit/'),{'role':'member','active':'on','username':'a-admin'})
        self.assertEqual(response.status_code,200)
        with organization_scope(self.a):
            member.refresh_from_db()
            self.assertEqual(member.role,'admin')

    def test_global_admin_registers_organization_and_first_local_admin(self):
        self.client.force_login(self.superuser)
        response=self.client.post('/organizations/create/',{'name':'New Company','slug':'new-company','active':'on','admin_username':'admin','admin_email':'admin@example.test','admin_password':'Unique-company-password-827!','confirmation':'Unique-company-password-827!'})
        self.assertEqual(response.status_code,302,response.content[:500])
        org=Organization.objects.get(slug='new-company')
        with organization_scope(org):
            member=Membership.objects.get(role='admin')
            self.assertEqual(member.display_username,'admin')
            self.assertFalse(member.user.is_staff)
            self.assertFalse(member.user.is_superuser)
            self.assertEqual(Menu.objects.filter(code='dashboard').count(),1)
            self.assertEqual(SiteConfiguration.objects.get().name,'New Company')
        self.client.logout()
        self.assertEqual(self.client.post(self.url(org,'/login/'),{'username':'admin','password':'Unique-company-password-827!'}).status_code,302)

    def test_organization_admin_cannot_create_global_organization(self):
        self.client.force_login(self.a_admin)
        self.denied(self.client.post('/organizations/create/',{'name':'Unauthorized','slug':'unauthorized'}))
        self.assertFalse(Organization.objects.filter(slug='unauthorized').exists())
