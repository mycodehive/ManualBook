import io
import tempfile
import uuid
from pathlib import Path
from PIL import Image, PngImagePlugin
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from apps.organizations.models import Organization, Membership
from apps.organizations.scoping import organization_scope
from .models import SEOConfiguration


@override_settings(SECURE_SSL_REDIRECT=False)
class SEOImageUploadTests(TestCase):
    def setUp(self):
        self.media = tempfile.TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        settings = override_settings(MEDIA_ROOT=self.media.name)
        settings.enable()
        self.addCleanup(settings.disable)
        User = get_user_model()
        self.owner = User.objects.create_superuser('image-owner', password='Image-password-734!')
        self.staff = User.objects.create_user('image-staff', is_staff=True)
        self.manager = User.objects.create_user('image-manager')
        self.member = User.objects.create_user('image-member')
        self.org = Organization.objects.create(name='Image tenant', slug='image-tenant')
        with organization_scope(self.org):
            Membership.objects.create(user=self.manager, role='admin')
            Membership.objects.create(user=self.member)
        self.data = {'site_url': 'https://manuals.example.test', 'title': 'Image introduction', 'description': 'Description', 'generator_content': 'ManualBook', 'og_site_name': 'ManualBook', 'twitter_card': 'summary_large_image', 'sitemap_enabled': 'on', 'sitemap_cache_seconds': 300}

    def png(self, size=(24, 12)):
        output = io.BytesIO()
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text('Secret', 'PRIVATE IMAGE METADATA')
        Image.new('RGB', size, '#123456').save(output, format='PNG', pnginfo=metadata)
        return SimpleUploadedFile('share.png', output.getvalue(), content_type='image/png')

    def upload(self):
        self.client.force_login(self.owner)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/organizations/seo/edit/', {**self.data, 'og_image': self.png()})
        self.assertEqual(response.status_code, 302)
        return SEOConfiguration.objects.get()

    def consume(self, response):
        self.assertEqual(response.status_code, 200)
        return b''.join(response.streaming_content)

    def test_upload_normalizes_image_and_publishes_only_shared_metadata_asset(self):
        configuration = self.upload()
        self.assertEqual((configuration.og_image_width, configuration.og_image_height), (24, 12))
        self.assertTrue(configuration.public_image_path.startswith('/seo-images/'))
        stored = Path(configuration.og_image.path).read_bytes()
        self.assertTrue(stored.startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertNotIn(b'PRIVATE IMAGE METADATA', stored)
        with Image.open(io.BytesIO(stored)) as image:
            self.assertEqual(image.info, {})
        self.client.logout()
        response = self.client.get(configuration.public_image_path)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(self.consume(response), stored)
        intro = self.client.get('/intro/')
        public_url = 'https://manuals.example.test' + configuration.public_image_path
        self.assertContains(intro, 'property="og:image" content="' + public_url + '"')
        self.assertContains(intro, 'name="twitter:image" content="' + public_url + '"')
        self.assertNotContains(intro, 'seo_public/')
        self.assertNotContains(intro, '/private-media/')
        self.assertEqual(self.client.get('/seo-images/' + str(uuid.uuid4()) + '/').status_code, 404)
        self.assertIn(self.client.get('/o/image-tenant' + configuration.public_image_path).status_code, (302, 403, 404))
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get('/o/image-tenant' + configuration.public_image_path).status_code, 404)
        self.assertEqual(self.client.post(configuration.public_image_path).status_code, 405)

    def test_upload_is_restricted_to_highest_admin_and_csrf_protected(self):
        for user in (self.staff, self.manager, self.member):
            self.client.force_login(user)
            response = self.client.post('/organizations/seo/edit/', {**self.data, 'og_image': self.png()})
            self.assertEqual(response.status_code, 403)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post('/organizations/seo/edit/', {**self.data, 'og_image': self.png()}).status_code, 403)
        self.assertFalse(SEOConfiguration.objects.exists())
        self.assertEqual(list(Path(self.media.name).rglob('*.png')), [])

    def test_jpeg_and_webp_are_decoded_and_served_as_png(self):
        self.client.force_login(self.owner)
        for image_format, extension, content_type in (('JPEG', 'jpg', 'image/jpeg'), ('WEBP', 'webp', 'image/webp')):
            with self.subTest(image_format=image_format):
                output = io.BytesIO()
                Image.new('RGB', (32, 18), '#654321').save(output, format=image_format)
                upload = SimpleUploadedFile('share.' + extension, output.getvalue(), content_type=content_type)
                with self.captureOnCommitCallbacks(execute=True):
                    response = self.client.post('/organizations/seo/edit/', {**self.data, 'og_image': upload})
                self.assertEqual(response.status_code, 302)
                configuration = SEOConfiguration.objects.get()
                self.assertEqual((configuration.og_image_width, configuration.og_image_height), (32, 18))
                response = self.client.get(configuration.public_image_path)
                self.assertEqual(response['Content-Type'], 'image/png')
                data = self.consume(response)
                self.assertTrue(data.startswith(b'\x89PNG\r\n\x1a\n'))
                with Image.open(io.BytesIO(data)) as image:
                    self.assertEqual(image.format, 'PNG')
                    self.assertEqual(image.size, (32, 18))

    def test_invalid_formats_oversized_bytes_and_dimensions_write_nothing(self):
        self.client.force_login(self.owner)
        uploads = [SimpleUploadedFile('bad.svg', b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', content_type='image/svg+xml'), SimpleUploadedFile('fake.png', b'not an image', content_type='image/png'), SimpleUploadedFile('large.png', b'x' * (5 * 1024 * 1024 + 1), content_type='image/png'), self.png((4097, 1))]
        for upload in uploads:
            with self.subTest(name=upload.name, size=upload.size):
                response = self.client.post('/organizations/seo/edit/', {**self.data, 'og_image': upload})
                self.assertEqual(response.status_code, 200)
                self.assertFalse(SEOConfiguration.objects.exists())
                self.assertEqual(list(Path(self.media.name).rglob('*.png')), [])

    def test_replacement_clear_and_delete_revoke_old_url_and_remove_files(self):
        configuration = self.upload()
        old_path, old_url = configuration.og_image.path, configuration.public_image_path
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/organizations/seo/edit/', {**self.data, 'og_image': self.png((30, 15))})
        self.assertEqual(response.status_code, 302)
        configuration.refresh_from_db()
        self.assertNotEqual(configuration.public_image_path, old_url)
        self.assertFalse(Path(old_path).exists())
        self.assertEqual(self.client.get(old_url).status_code, 404)
        replacement_path, replacement_url = configuration.og_image.path, configuration.public_image_path
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/organizations/seo/edit/', {**self.data, 'og_image-clear': 'on'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Path(replacement_path).exists())
        self.assertEqual(self.client.get(replacement_url).status_code, 404)
        configuration = self.upload()
        deleted_path, deleted_url = configuration.og_image.path, configuration.public_image_path
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/organizations/seo/delete/')
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SEOConfiguration.objects.exists())
        self.assertFalse(Path(deleted_path).exists())
        self.assertEqual(self.client.get(deleted_url).status_code, 404)
