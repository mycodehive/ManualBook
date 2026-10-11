"""Public publication access remains separate from organization management."""
import tempfile
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from apps.organizations.models import Organization, Membership, OrganizationGroup
from apps.organizations.scoping import organization_scope
from .models import ManualSpace, ManualNode, ManualRevision, ManualAttachment, ManualRecentView, ManualFavorite, ManualPermissionAssignment


class PublicManualSecurityTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        User = get_user_model()
        self.admin = User.objects.create_user('public-space-owner', password='Manual-security-928!')
        self.member = User.objects.create_user('public-space-member', password='Manual-security-928!')
        self.foreign = User.objects.create_user('other-space-member', password='Manual-security-928!')
        self.org = Organization.objects.create(name='Public company', slug='public-company')
        self.other = Organization.objects.create(name='Other company', slug='other-company')
        with organization_scope(self.other):
            Membership.objects.create(user=self.foreign)
        with organization_scope(self.org):
            Membership.objects.create(user=self.admin, role='admin')
            Membership.objects.create(user=self.member)
            self.space = ManualSpace.objects.create(name='Public knowledge', visibility='public')
            self.private = ManualSpace.objects.create(name='Private knowledge')
            self.node = self.make_page(self.space, 'Published title', 'Published body')
            self.draft = ManualRevision.objects.create(node=self.node, number=2, title='HIDDEN DRAFT TITLE', markdown='HIDDEN DRAFT BODY', author=self.admin)
            self.node.draft = self.draft
            self.node.title = self.draft.title
            self.node.save()
            self.unpublished = ManualNode.objects.create(space=self.space, title='UNPUBLISHED TITLE')
            empty_folder = ManualNode.objects.create(space=self.space, title='UNPUBLISHED FOLDER', kind='folder')
            ManualNode.objects.create(space=self.space, title='UNPUBLISHED CHILD', parent=empty_folder)
            self.private_node = self.make_page(self.private, 'PRIVATE TITLE', 'PRIVATE BODY')
            self.published_file = ManualAttachment.objects.create(node=self.node, revision=self.node.published, file=SimpleUploadedFile('published.txt', b'published bytes'), name='published.txt', author=self.admin)
            self.draft_file = ManualAttachment.objects.create(node=self.node, revision=self.draft, file=SimpleUploadedFile('draft.txt', b'DRAFT FILE SECRET'), name='draft.txt', author=self.admin)

    def make_page(self, space, title, body, parent=None):
        node = ManualNode.objects.create(space=space, title=title, parent=parent)
        revision = ManualRevision.objects.create(node=node, number=1, title=title, markdown=body, author=self.admin)
        node.published = revision
        node.draft = revision
        node.save()
        return node

    def url(self, inner, other=False):
        return '/o/' + (self.other.slug if other else self.org.slug) + '/manuals/' + inner

    def as_user(self, user):
        self.client.logout()
        if user:
            self.client.force_login(user)

    def test_public_readers_see_publication_only_and_no_management_controls(self):
        self.assertEqual(self.private.visibility, 'private')
        for user in (None, self.foreign, self.member):
            with self.subTest(user=user):
                self.as_user(user)
                response = self.client.get(self.url(f'spaces/{self.space.pk}/'))
                self.assertEqual(response.status_code, 200)
                self.assertIn('no-store', response['Cache-Control'])
                self.assertContains(response, 'Published title')
                self.assertNotContains(response, 'HIDDEN DRAFT TITLE')
                self.assertNotContains(response, 'UNPUBLISHED TITLE')
                self.assertNotContains(response, 'UNPUBLISHED FOLDER')
                self.assertNotContains(response, 'UNPUBLISHED CHILD')
                for route in ('/settings/', '/trash/', '/import-files/', '/export/', '/nodes/create/'):
                    self.assertNotContains(response, self.url(f'spaces/{self.space.pk}{route}'))
                response = self.client.get(self.url(f'nodes/{self.node.pk}/') + '?draft=1')
                self.assertContains(response, 'Published body')
                self.assertNotContains(response, 'HIDDEN DRAFT BODY')
                self.assertNotContains(response, self.url(f'nodes/{self.node.pk}/edit/'))
                self.assertNotContains(response, self.url(f'nodes/{self.node.pk}/favorite/'))
        self.assertEqual(ManualRecentView.all_objects.count(), 0)
        self.assertEqual(ManualFavorite.all_objects.count(), 0)

    def test_private_and_unpublished_documents_remain_closed(self):
        for user in (None, self.foreign, self.member):
            self.as_user(user)
            for inner in (f'spaces/{self.private.pk}/', f'nodes/{self.private_node.pk}/', f'nodes/{self.unpublished.pk}/'):
                with self.subTest(user=user, inner=inner):
                    response = self.client.get(self.url(inner))
                    self.assertIn(response.status_code, (302, 403, 404))
                    self.assertNotIn(b'PRIVATE BODY', response.content)

    def test_published_attachment_only_and_head_access(self):
        for user in (None, self.foreign, self.member):
            self.as_user(user)
            response = self.client.get(self.url(f'attachments/{self.published_file.pk}/'))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b''.join(response.streaming_content), b'published bytes')
            self.assertEqual(self.client.get(self.url(f'attachments/{self.draft_file.pk}/')).status_code, 404)
            for inner in (f'spaces/{self.space.pk}/', f'nodes/{self.node.pk}/', f'attachments/{self.published_file.pk}/'):
                response = self.client.head(self.url(inner))
                self.assertEqual(response.status_code, 200)
                if response.streaming:
                    # Django's test-client wrapper closes safely without closing
                    # the transaction held by TestCase on PostgreSQL/MariaDB.
                    list(response.streaming_content)

    def test_archived_or_deleted_ancestry_hides_descendants_and_attachments(self):
        with organization_scope(self.org):
            folder = ManualNode.objects.create(space=self.space, title='Hidden folder', kind='folder')
            child = self.make_page(self.space, 'HIDDEN CHILD', 'HIDDEN CHILD BODY', parent=folder)
            attachment = ManualAttachment.objects.create(node=child, revision=child.published, file=SimpleUploadedFile('child.txt', b'hidden child'), name='child.txt', author=self.admin)
        for field in ('archived', 'deleted'):
            with organization_scope(self.org):
                folder.archived = field == 'archived'
                folder.deleted = field == 'deleted'
                folder.save()
            self.assertNotContains(self.client.get(self.url(f'spaces/{self.space.pk}/')), 'HIDDEN CHILD')
            self.assertEqual(self.client.get(self.url(f'nodes/{child.pk}/')).status_code, 404)
            self.assertEqual(self.client.get(self.url(f'attachments/{attachment.pk}/')).status_code, 404)

    def test_inactive_space_and_organization_are_not_public(self):
        with organization_scope(self.org):
            self.space.active = False
            self.space.save()
        self.assertIn(self.client.get(self.url(f'spaces/{self.space.pk}/')).status_code, (403, 404))
        self.assertIn(self.client.get(self.url(f'nodes/{self.node.pk}/')).status_code, (403, 404))
        self.org.active = False
        self.org.save()
        self.assertEqual(self.client.get(self.url(f'spaces/{self.space.pk}/')).status_code, 404)

    def test_management_endpoints_and_mutations_are_not_public(self):
        routes = ['spaces/', 'spaces/create/', f'spaces/{self.space.pk}/settings/', f'spaces/{self.space.pk}/trash/', f'spaces/{self.space.pk}/nodes/create/', f'spaces/{self.space.pk}/export/', f'nodes/{self.node.pk}/settings/', f'nodes/{self.node.pk}/edit/', f'nodes/{self.node.pk}/history/', f'nodes/{self.node.pk}/export/', f'nodes/{self.node.pk}/pdf/']
        mutations = [f'spaces/{self.space.pk}/', f'nodes/{self.node.pk}/', f'attachments/{self.published_file.pk}/', f'spaces/{self.space.pk}/import/', f'spaces/{self.space.pk}/import-files/', f'nodes/{self.node.pk}/autosave/', f'nodes/{self.node.pk}/favorite/', f'nodes/{self.node.pk}/upload/', f'nodes/{self.node.pk}/permissions/', f'nodes/{self.node.pk}/actions/delete/', f'nodes/{self.node.pk}/actions/copy/']
        before = (ManualNode.all_objects.count(), ManualRevision.all_objects.count(), ManualAttachment.all_objects.count())
        for user in (None, self.foreign, self.member):
            self.as_user(user)
            denied = (403, 404) if user else (302, 403, 404)
            for inner in routes:
                if user == self.member and inner == 'spaces/':
                    continue
                with self.subTest(user=user, get=inner):
                    self.assertIn(self.client.get(self.url(inner)).status_code, denied)
            for inner in mutations:
                with self.subTest(user=user, post=inner):
                    self.assertIn(self.client.post(self.url(inner), {'title': 'attack', 'markdown': 'attack'}).status_code, denied + (405,))
        self.assertEqual(before, (ManualNode.all_objects.count(), ManualRevision.all_objects.count(), ManualAttachment.all_objects.count()))
        self.assertEqual(ManualFavorite.all_objects.count(), 0)
        with organization_scope(self.org):
            self.node.refresh_from_db()
        self.assertFalse(self.node.deleted)

    def test_url_organization_mismatch_is_not_found(self):
        for inner in (f'spaces/{self.space.pk}/', f'nodes/{self.node.pk}/', f'attachments/{self.published_file.pk}/'):
            self.assertEqual(self.client.get(self.url(inner, other=True)).status_code, 404)

    def test_manager_can_switch_visibility_and_retains_editing(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url(f'spaces/{self.space.pk}/'))
        self.assertContains(response, self.url(f'spaces/{self.space.pk}/settings/'))
        self.assertContains(response, self.url(f'nodes/{self.node.pk}/edit/'))
        response = self.client.post(self.url(f'spaces/{self.space.pk}/settings/'), {'name': self.space.name, 'active': 'on', 'visibility': 'private'})
        self.assertEqual(response.status_code, 302)
        with organization_scope(self.org):
            self.space.refresh_from_db()
        self.assertEqual(self.space.visibility, 'private')
        self.client.logout()
        self.assertIn(self.client.get(self.url(f'spaces/{self.space.pk}/')).status_code, (302, 403, 404))
        self.client.force_login(self.admin)
        response = self.client.post(self.url(f'spaces/{self.space.pk}/settings/'), {'name': self.space.name, 'active': 'on', 'visibility': 'public'})
        self.assertEqual(response.status_code, 302)
        self.client.logout()
        self.assertContains(self.client.get(self.url(f'spaces/{self.space.pk}/')), 'Published title')

    def test_read_group_member_uses_public_mode_without_tracking_or_exports(self):
        with organization_scope(self.org):
            group = OrganizationGroup.objects.create(name='Readers')
            Membership.objects.get(user=self.member).groups.add(group)
            self.space.view_groups.add(group.group)
            ManualPermissionAssignment.objects.create(node=self.node, user=self.member, action='export', effect='allow')
        self.client.force_login(self.member)
        response = self.client.get(self.url(f'nodes/{self.node.pk}/'))
        self.assertContains(response, 'Published body')
        self.assertTrue(response.context['public_reader'])
        self.assertEqual(ManualRecentView.all_objects.count(), 0)
        for inner in (f'spaces/{self.space.pk}/export/', f'nodes/{self.node.pk}/export/', f'nodes/{self.node.pk}/pdf/'):
            self.assertEqual(self.client.get(self.url(inner)).status_code, 403)
        self.assertEqual(self.client.post(self.url(f'nodes/{self.node.pk}/favorite/')).status_code, 403)
        for inner in (f'spaces/{self.space.pk}/', f'nodes/{self.node.pk}/', f'attachments/{self.published_file.pk}/'):
            self.assertEqual(self.client.post(self.url(inner)).status_code, 405)
        self.assertEqual(ManualFavorite.all_objects.count(), 0)
        self.assertEqual(ManualRecentView.all_objects.count(), 0)

    def test_public_read_ignores_menu_visibility_without_opening_other_routes(self):
        from apps.menus.models import Menu
        with organization_scope(self.org):
            Menu.objects.create(code='public-manuals', name='Hidden manuals', url='/manuals/', is_active=False)
        self.client.force_login(self.member)
        self.assertContains(self.client.get(self.url(f'nodes/{self.node.pk}/')), 'Published body')
        self.assertEqual(self.client.get(self.url('spaces/')).status_code, 403)

    def test_space_editor_with_document_edit_denied_remains_read_only(self):
        with organization_scope(self.org):
            group = OrganizationGroup.objects.create(name='Editors')
            Membership.objects.get(user=self.member).groups.add(group)
            self.space.edit_groups.add(group.group)
            ManualPermissionAssignment.objects.create(node=self.node, user=self.member, action='edit', effect='deny')
            ManualPermissionAssignment.objects.create(node=self.node, user=self.member, action='export', effect='allow')
        self.client.force_login(self.member)
        response = self.client.get(self.url(f'nodes/{self.node.pk}/'))
        self.assertContains(response, 'Published body')
        self.assertTrue(response.context['public_reader'])
        for route in ('edit/', 'favorite/', 'export/', 'pdf/'):
            self.assertNotContains(response, self.url(f'nodes/{self.node.pk}/{route}'))
        for route in ('export/', 'pdf/'):
            self.assertEqual(self.client.get(self.url(f'nodes/{self.node.pk}/{route}')).status_code, 403)
        for route in ('favorite/', 'actions/delete/'):
            self.assertEqual(self.client.post(self.url(f'nodes/{self.node.pk}/{route}')).status_code, 403)
        self.assertEqual(ManualRecentView.all_objects.count(), 0)
        self.assertEqual(ManualFavorite.all_objects.count(), 0)
        with organization_scope(self.org):
            self.node.refresh_from_db()
        self.assertFalse(self.node.deleted)
