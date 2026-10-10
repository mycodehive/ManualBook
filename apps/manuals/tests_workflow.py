from django.contrib.auth.models import Group, User
from django.test import TestCase, Client
from django.urls import reverse
from .models import ManualNode, ManualSpace
from .services import save_revision, request_review, decide, publish

class WorkflowHttpTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('admin-http', 'admin@example.test', 'test-only-password')
        self.reader = User.objects.create_user('reader-http')
        readers = Group.objects.create(name='http-readers')
        self.reader.groups.add(readers)
        self.space = ManualSpace.objects.create(name='문서 플랫폼', allow_self_approval=True)
        self.space.view_groups.add(readers)
        self.node = ManualNode.objects.create(space=self.space, title='게시 제목')
        save_revision(self.admin, self.node.pk, '게시 제목', '# 업무 기준\n\n게시 내용', 0)
        self.node.refresh_from_db()
        review = request_review(self.admin, self.node)
        decide(self.admin, review.pk, True, '검토 완료')
        publish(self.admin, self.node)
        self.node.refresh_from_db()
    def test_admin_pages_render_with_common_shell(self):
        self.client.force_login(self.admin)
        paths = ['/home/', '/settings/', '/settings/audit/', '/settings/integrations/', '/menus/',
                 '/accounts/', '/accounts/profile/', '/accounts/password/', '/manuals/',
                 '/manuals/spaces/', '/manuals/reviews/', '/admin/']
        for path in paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
        for name in ['space', 'space_settings', 'page', 'edit', 'node_settings', 'history', 'trash']:
            pk = self.space.pk if name in ['space', 'space_settings', 'trash'] else self.node.pk
            response = self.client.get(reverse(f'manuals:{name}', args=[pk]))
            self.assertEqual(response.status_code, 200, name)
        response = self.client.get(reverse('manuals:edit', args=[self.node.pk]))
        self.assertContains(response, 'editor-initial-html')
        self.assertContains(response, 'data-block-editor')
    def test_anonymous_login_renders_fields_and_accepts_credentials(self):
        response = self.client.get('/login/')
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
        response = self.client.post('/login/', {'username': 'admin-http', 'password': 'test-only-password'})
        self.assertRedirects(response, '/home/')
    def test_readers_never_see_later_draft_title_or_content(self):
        save_revision(self.admin, self.node.pk, '비밀 초안 제목', '# 비밀 초안 내용', 1)
        self.client.force_login(self.reader)
        for path in ['/manuals/', reverse('manuals:space', args=[self.space.pk]), reverse('manuals:page', args=[self.node.pk])]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, '비밀 초안 제목')
            self.assertNotContains(response, '비밀 초안 내용')
        response = self.client.get('/manuals/?q=비밀')
        self.assertNotContains(response, '게시 제목')
        response = self.client.get(reverse('manuals:edit', args=[self.node.pk]))
        self.assertEqual(response.status_code, 403)
    def test_csrf_is_enforced_on_mutation(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        response = client.post(reverse('manuals:action', args=[self.node.pk, 'delete']))
        self.assertEqual(response.status_code, 403)
        self.node.refresh_from_db()
        self.assertFalse(self.node.deleted)
    def test_inline_images_keep_stable_links_after_new_publication(self):
        import io
        import tempfile
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .models import ManualAttachment
        with tempfile.TemporaryDirectory() as media, self.settings(MEDIA_ROOT=media):
            stream = io.BytesIO()
            Image.new('RGB', (1, 1), 'white').save(stream, format='PNG')
            image = ManualAttachment.objects.create(node=self.node, revision=self.node.draft, author=self.admin,
                name='guide.png', file=SimpleUploadedFile('guide.png', stream.getvalue(), content_type='image/png'))
            fake = ManualAttachment.objects.create(node=self.node, revision=self.node.draft, author=self.admin,
                name='fake.png', file=SimpleUploadedFile('fake.png', b'<script>alert(1)</script>', content_type='image/png'))
            save_revision(self.admin, self.node.pk, '게시 제목', 'Updated image publication', 1)
            self.node.refresh_from_db()
            review = request_review(self.admin, self.node)
            decide(self.admin, review.pk, True, '검토 완료')
            publish(self.admin, self.node)
            self.client.force_login(self.reader)
            response = self.client.get(reverse('manuals:download', args=[image.pk]) + '?inline=1')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'image/png')
            response.close()
            response = self.client.get(reverse('manuals:download', args=[fake.pk]) + '?inline=1')
            self.assertEqual(response.status_code, 404)
