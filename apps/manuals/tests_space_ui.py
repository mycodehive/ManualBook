from bs4 import BeautifulSoup
from django.contrib.auth import get_user_model
from django.test import TestCase
from apps.core.bootstrap import seed_platform
from apps.organizations.models import Organization, Membership, OrganizationGroup
from apps.organizations.scoping import organization_scope
from .models import ManualSpace, ManualNode, ManualPermissionAssignment
from .services import save_revision, publish


class ManualSpaceUiTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Space UI', slug='space-ui')
        self.other_org = Organization.objects.create(name='Other space', slug='other-space')
        User = get_user_model()
        self.manager = User.objects.create_user('space-manager')
        self.editor = User.objects.create_user('space-editor')
        self.reader = User.objects.create_user('space-reader')
        self.other_user = User.objects.create_user('space-other-user')
        with organization_scope(self.org):
            seed_platform()
            Membership.objects.create(user=self.manager, role='admin')
            edit_membership = Membership.objects.create(user=self.editor)
            read_membership = Membership.objects.create(user=self.reader)
            editors = OrganizationGroup.objects.create(name='Editors')
            readers = OrganizationGroup.objects.create(name='Readers')
            edit_membership.groups.add(editors)
            read_membership.groups.add(readers)
            self.space = ManualSpace.objects.create(name='Published space', require_approval=False)
            self.space.edit_groups.add(editors.group)
            self.space.view_groups.add(readers.group)
            self.node = ManualNode.objects.create(space=self.space, title='Published public title')
            save_revision(self.manager, self.node.pk, 'Published public title', 'Published body', 0)
            self.node.refresh_from_db()
            publish(self.manager, self.node)
            save_revision(self.manager, self.node.pk, 'PRIVATE-LATER-DRAFT', 'Private draft body', 1)
            self.draft_node = ManualNode.objects.create(space=self.space, title='EDITOR-ONLY-DRAFT')
        with organization_scope(self.other_org):
            Membership.objects.create(user=self.other_user)
        self.url = f'/o/{self.org.slug}/manuals/spaces/{self.space.pk}/'

    def response_for(self, user):
        self.client.force_login(user)
        return self.client.get(self.url)

    def test_editor_has_shared_space_layout_and_scoped_post_actions(self):
        response = self.response_for(self.editor)
        self.assertEqual(response.status_code, 200)
        soup = BeautifulSoup(response.content, 'html.parser')
        self.assertIsNotNone(soup.select_one('.manual-space-page'))
        self.assertIsNotNone(soup.select_one('.manual-space-actions'))
        self.assertIsNotNone(soup.select_one('.manual-space-transfer'))
        transfer = soup.select_one('.manual-space-transfer form')
        self.assertIsNotNone(transfer)
        self.assertEqual(transfer.get('method'), 'post')
        self.assertIsNotNone(transfer.select_one('[name="csrfmiddlewaretoken"]'))
        self.assertTrue(transfer.get('action').startswith('/o/space-ui/manuals/'))
        label = transfer.find('label')
        self.assertIsNotNone(label)
        self.assertIsNotNone(soup.find('input', id=label.get('for')))
        self.assertContains(response, 'EDITOR-ONLY-DRAFT')
        self.assertContains(response, f'data-node-id="{self.node.pk}"')

    def test_reader_has_no_editor_controls_and_no_unpublished_content(self):
        response = self.response_for(self.reader)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Published public title')
        self.assertNotContains(response, 'PRIVATE-LATER-DRAFT')
        self.assertNotContains(response, 'Private draft body')
        self.assertNotContains(response, 'EDITOR-ONLY-DRAFT')
        soup = BeautifulSoup(response.content, 'html.parser')
        self.assertIsNone(soup.select_one('.manual-space-transfer form'))
        self.assertIsNone(soup.select_one('[draggable="true"]'))
        self.assertIsNone(soup.select_one(f'a[href="/o/space-ui/manuals/nodes/{self.node.pk}/edit/"]'))
        self.assertNotContains(response, f'/o/space-ui/manuals/spaces/{self.space.pk}/nodes/create/')
        self.assertNotContains(response, f'/o/space-ui/manuals/spaces/{self.space.pk}/trash/')
        self.assertContains(response, '게시 문서 ZIP 다운로드')

    def test_other_organization_cannot_access_space(self):
        response = self.response_for(self.other_user)
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, 'Published public title', status_code=403)
        self.assertNotContains(response, 'PRIVATE-LATER-DRAFT', status_code=403)

    def test_node_edit_denial_hides_row_controls_and_drag_but_keeps_public_link(self):
        with organization_scope(self.org):
            ManualPermissionAssignment.objects.create(node=self.node, user=self.editor, action='edit', effect='deny')
        response = self.response_for(self.editor)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Published public title')
        soup = BeautifulSoup(response.content, 'html.parser')
        self.assertIsNone(soup.select_one(f'[data-node-id="{self.node.pk}"][draggable="true"]'))
        self.assertIsNone(soup.find('form', action=f'/o/space-ui/manuals/nodes/{self.node.pk}/actions/copy/'))
        self.assertNotContains(response, f'/o/space-ui/manuals/nodes/{self.node.pk}/edit/')
        self.assertNotContains(response, f'/o/space-ui/manuals/nodes/{self.node.pk}/settings/')
