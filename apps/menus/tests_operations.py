"""Standalone regression coverage for tenant-safe menu configuration operations."""
import copy
import json

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from apps.core.models import AuditEvent
from apps.organizations.models import Membership, Organization, OrganizationGroup
from apps.organizations.scoping import organization_scope
from .models import Menu
from .operations import StaleMenuTree, export_menus, import_menus, move_menu, tree_revision
from .permissions import can_access_menu


@override_settings(SECURE_SSL_REDIRECT=False)
class MenuOperationsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user('menu-alpha-admin', password='menu-test-password!')
        self.other_admin = User.objects.create_user('menu-beta-admin', password='menu-test-password!')
        self.reader = User.objects.create_user('menu-alpha-reader', password='menu-test-password!')
        self.a = Organization.objects.create(name='Menu Alpha', slug='menu-alpha')
        self.b = Organization.objects.create(name='Menu Beta', slug='menu-beta')
        self.assets = {}
        for org, admin in [(self.a, self.admin), (self.b, self.other_admin)]:
            with organization_scope(org):
                Membership.objects.create(user=admin, role='admin')
                group = OrganizationGroup.objects.create(name='Editors')
                root = Menu.objects.create(code='root', name=org.name + ' Root', order=1)
                peer = Menu.objects.create(code='peer', name=org.name + ' Peer', order=2)
                child = Menu.objects.create(code='child', name=org.name + ' Child', parent_menu=root, order=1)
                leaf = Menu.objects.create(code='leaf', name=org.name + ' Leaf', parent_menu=child, order=1)
                child.allowed_groups.add(group.group)
                child.inherited_group_rules = [[group.group_id]]
                child.description = 'Portable menu configuration'
                child.workspace_dir_name = 'shared-documents'
                child.workspace_path = '/private/' + org.slug
                child.save()
                self.assets[org.pk] = {'group': group, 'root': root, 'peer': peer, 'child': child, 'leaf': leaf}
        with organization_scope(self.a):
            member = Membership.objects.create(user=self.reader, role='member')
            member.groups.add(self.assets[self.a.pk]['group'])

    def revision(self):
        return tree_revision(list(Menu.objects.all()))

    def snapshot(self, org):
        with organization_scope(org):
            values = []
            for menu in Menu.objects.order_by('pk'):
                values.append((menu.pk, menu.parent_menu_id, menu.order, menu.name, menu.code, menu.url,
                               menu.is_active, menu.children_as_tabs, menu.description,
                               menu.workspace_dir_name, menu.workspace_path,
                               json.dumps(menu.inherited_group_rules),
                               tuple(menu.allowed_groups.order_by('pk').values_list('pk', flat=True)),
                               menu.updated_at.isoformat()))
            return values

    def test_move_preserves_subtree_and_permission_rules_and_audits_only_own_org(self):
        other_before = self.snapshot(self.b)
        a = self.assets[self.a.pk]
        with organization_scope(self.a):
            move_menu(a['child'].pk, a['peer'].pk, 'inside', self.revision(), self.admin)
            a['child'].refresh_from_db(); a['leaf'].refresh_from_db()
            self.assertEqual(a['child'].parent_menu_id, a['peer'].pk)
            self.assertEqual(a['leaf'].parent_menu_id, a['child'].pk)
            self.assertEqual(a['child'].inherited_group_rules, [[a['group'].group_id]])
            self.assertEqual(list(a['child'].allowed_groups.values_list('pk', flat=True)), [a['group'].group_id])
            self.assertTrue(AuditEvent.objects.filter(action='menu.move', actor=self.admin).exists())
        self.assertEqual(self.snapshot(self.b), other_before)

    def test_move_before_after_normalizes_sibling_order(self):
        a = self.assets[self.a.pk]
        with organization_scope(self.a):
            move_menu(a['peer'].pk, a['root'].pk, 'before', self.revision(), self.admin)
            roots = list(Menu.objects.filter(parent_menu=None).order_by('order').values_list('pk', 'order'))
            self.assertEqual(roots, [(a['peer'].pk, 1), (a['root'].pk, 2)])
            move_menu(a['peer'].pk, a['root'].pk, 'after', self.revision(), self.admin)
            roots = list(Menu.objects.filter(parent_menu=None).order_by('order').values_list('pk', 'order'))
            self.assertEqual(roots, [(a['root'].pk, 1), (a['peer'].pk, 2)])

    def test_stale_revision_rejects_second_writer_without_partial_reorder(self):
        a = self.assets[self.a.pk]
        with organization_scope(self.a):
            stale = self.revision()
            move_menu(a['peer'].pk, a['root'].pk, 'before', stale, self.admin)
            after_first = self.snapshot(self.a)
            audit_count = AuditEvent.objects.count()
            with self.assertRaises(StaleMenuTree):
                move_menu(a['root'].pk, a['peer'].pk, 'before', stale, self.admin)
            self.assertEqual(self.snapshot(self.a), after_first)
            self.assertEqual(AuditEvent.objects.count(), audit_count)

    def test_failed_cycle_depth_and_foreign_move_are_atomic(self):
        a = self.assets[self.a.pk]
        b = self.assets[self.b.pk]
        before = self.snapshot(self.a)
        with organization_scope(self.a):
            audit_count = AuditEvent.objects.count()
            cases = [(a['root'].pk, a['child'].pk, 'inside'),
                     (a['root'].pk, a['peer'].pk, 'inside'),
                     (a['child'].pk, b['peer'].pk, 'inside'),
                     (b['child'].pk, a['peer'].pk, 'inside'),
                     (a['child'].pk, a['peer'].pk, 'invalid')]
            for source, target, position in cases:
                with self.subTest(source=source, target=target, position=position):
                    with self.assertRaises((ValidationError, PermissionDenied)):
                        move_menu(source, target, position, self.revision(), self.admin)
                    self.assertEqual(self.snapshot(self.a), before)
            self.assertEqual(AuditEvent.objects.count(), audit_count)

    def test_reader_other_org_admin_and_missing_scope_cannot_call_services(self):
        a = self.assets[self.a.pk]
        with organization_scope(self.a):
            data = export_menus(self.admin)
            for user in [self.reader, self.other_admin]:
                with self.subTest(user=user.username):
                    with self.assertRaises(PermissionDenied): export_menus(user)
                    with self.assertRaises(PermissionDenied): import_menus(data, user)
                    with self.assertRaises(PermissionDenied):
                        move_menu(a['peer'].pk, a['root'].pk, 'before', self.revision(), user)
        with organization_scope(None):
            with self.assertRaises(PermissionDenied): export_menus(self.admin)
            with self.assertRaises(PermissionDenied): import_menus(data, self.admin)
            with self.assertRaises(PermissionDenied):
                move_menu(a['peer'].pk, a['root'].pk, 'before', 'unused', self.admin)

    def test_portable_export_uses_org_group_names_instead_of_global_ids(self):
        a = self.assets[self.a.pk]
        with organization_scope(self.a):
            data = export_menus(self.admin)
            rows = {row['code']: row for row in data['menus']}
            self.assertEqual(set(rows), {'root', 'peer', 'child', 'leaf'})
            self.assertEqual(rows['child']['allowed_groups'], ['Editors'])
            self.assertEqual(rows['child']['inherited_group_rules'], [['Editors']])
            self.assertEqual(rows['leaf']['parent_code'], 'child')
            serialized = json.dumps(data)
            self.assertNotIn(a['group'].group.name, serialized)
            self.assertNotIn('/private/menu-alpha', serialized)
            self.assertNotIn('encrypted_secrets', serialized)
            self.assertNotIn('organization_id', serialized)

    def test_portable_import_maps_same_group_names_to_target_org_only(self):
        original_a = self.snapshot(self.a)
        with organization_scope(self.a): data = export_menus(self.admin)
        with organization_scope(self.b):
            retained = Menu.objects.create(code='unlisted', name='Do not delete')
            original_path = self.assets[self.b.pk]['child'].workspace_path
            count = import_menus(data, self.other_admin)
            self.assertEqual(count, 4)
            child = Menu.objects.get(code='child')
            target_group = self.assets[self.b.pk]['group']
            self.assertEqual(list(child.allowed_groups.values_list('pk', flat=True)), [target_group.group_id])
            self.assertEqual(child.inherited_group_rules, [[target_group.group_id]])
            self.assertEqual(child.workspace_path, original_path)
            self.assertTrue(Menu.objects.filter(pk=retained.pk).exists())
            self.assertTrue(AuditEvent.objects.filter(action='menu.import', actor=self.other_admin).exists())
        self.assertEqual(self.snapshot(self.a), original_a)

    def test_invalid_import_group_code_and_tree_roll_back_all_changes(self):
        with organization_scope(self.a):
            original = export_menus(self.admin)
            base = copy.deepcopy(original['menus'][0])
            base.update(code='new-valid', name='New valid menu', parent_code=None)
            bad_cases = [dict(code='new-invalid', name='bad', parent_code='missing-parent'),
                         dict(code='new-invalid', name='bad', allowed_groups=['Missing group']),
                         dict(code='new-invalid', name='bad', url='javascript:alert(1)'),
                         dict(code='new-valid', name='duplicate')]
            before = self.snapshot(self.a)
            audit_count = AuditEvent.objects.count()
            for overrides in bad_cases:
                data = copy.deepcopy(original)
                bad = copy.deepcopy(base); bad.update(overrides)
                data['menus'] = [copy.deepcopy(base), bad]
                with self.subTest(overrides=overrides):
                    with self.assertRaises(ValidationError): import_menus(data, self.admin)
                    self.assertEqual(self.snapshot(self.a), before)
                    self.assertEqual(AuditEvent.objects.count(), audit_count)

    def test_inherited_group_rules_are_enforced_after_transfer(self):
        a = self.assets[self.a.pk]
        with organization_scope(self.a):
            restricted = OrganizationGroup.objects.create(name='Restricted')
            node = a['child']
            node.allowed_groups.clear()
            node.inherited_group_rules = [[restricted.group_id]]; node.save()
            self.assertFalse(can_access_menu(self.reader, node))
            Membership.objects.get(user=self.reader).groups.add(restricted)
            self.assertTrue(can_access_menu(self.reader, node))

    def test_http_mutations_require_csrf_and_org_admin(self):
        self.client.force_login(self.admin)
        a = self.assets[self.a.pk]
        with organization_scope(self.a): revision = self.revision()
        payload = {'source': a['peer'].pk, 'target': a['root'].pk, 'position': 'before', 'revision': revision}
        client = Client(enforce_csrf_checks=True); client.force_login(self.admin)
        response = client.post('/o/menu-alpha/menus/move/', json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        response = client.post('/o/menu-alpha/menus/import/', {'file': SimpleUploadedFile('menus.json', b'{}')})
        self.assertEqual(response.status_code, 403)
        self.client.force_login(self.reader)
        for method, path, values in [('get', '/o/menu-alpha/menus/export/', {}),
                                     ('post', '/o/menu-alpha/menus/move/', payload),
                                     ('post', '/o/menu-alpha/menus/import/', {})]:
            with self.subTest(path=path):
                response = getattr(self.client, method)(path, values)
                self.assertEqual(response.status_code, 403)

    def test_effective_inactive_filter_preserves_raw_child_state(self):
        a = self.assets[self.a.pk]
        with organization_scope(self.a):
            root = a['root']; root.is_active = False; root.save()
        self.client.force_login(self.admin)
        active = self.client.get('/o/menu-alpha/menus/?status=active')
        inactive = self.client.get('/o/menu-alpha/menus/?status=inactive')
        self.assertEqual(active.status_code, 200); self.assertEqual(inactive.status_code, 200)
        self.assertNotIn(a['child'].pk, [menu.pk for menu in active.context['menus']])
        self.assertIn(a['child'].pk, [menu.pk for menu in inactive.context['menus']])
        with organization_scope(self.a):
            a['child'].refresh_from_db()
            self.assertTrue(a['child'].is_active)
            # Export must contain every menu despite the active/inactive UI filter.
            self.assertEqual(len(export_menus(self.admin)['menus']), 4)

    def test_http_move_rejects_stale_revision_and_get_requests(self):
        self.client.force_login(self.admin)
        a = self.assets[self.a.pk]
        with organization_scope(self.a):
            revision = self.revision()
        payload = {'source': a['peer'].pk, 'target': a['root'].pk,
                   'position': 'before', 'revision': revision}
        endpoint = '/o/menu-alpha/menus/move/'
        self.assertEqual(self.client.get(endpoint).status_code, 405)
        first = self.client.post(endpoint, json.dumps(payload), content_type='application/json')
        self.assertEqual(first.status_code, 200)
        after_first = self.snapshot(self.a)
        stale = self.client.post(endpoint, json.dumps(payload), content_type='application/json')
        self.assertEqual(stale.status_code, 409)
        self.assertIn('error', stale.json())
        self.assertEqual(self.snapshot(self.a), after_first)

    def test_import_rejects_groups_found_only_in_a_foreign_organization(self):
        with organization_scope(self.b):
            OrganizationGroup.objects.create(name='Beta private group')
        with organization_scope(self.a):
            data = export_menus(self.admin)
            data['menus'][0]['allowed_groups'] = ['Beta private group']
            before = self.snapshot(self.a)
            with self.assertRaises(ValidationError):
                import_menus(data, self.admin)
            self.assertEqual(self.snapshot(self.a), before)

    def test_successful_import_invalidates_an_earlier_move_revision(self):
        a = self.assets[self.a.pk]
        with organization_scope(self.a):
            stale = self.revision()
            data = export_menus(self.admin)
            data['menus'][0]['name'] = 'A changed imported name'
            import_menus(data, self.admin)
            after_import = self.snapshot(self.a)
            with self.assertRaises(StaleMenuTree):
                move_menu(a['peer'].pk, a['root'].pk, 'before', stale, self.admin)
            self.assertEqual(self.snapshot(self.a), after_import)
