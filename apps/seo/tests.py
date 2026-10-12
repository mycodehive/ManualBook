from django.contrib.auth import get_user_model
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from apps.organizations.models import Organization, Membership
from apps.organizations.scoping import organization_scope
from .models import SEOConfiguration


@override_settings(SECURE_SSL_REDIRECT=False)
class SEOSettingsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_superuser('seo-owner', password='SEO-password-752!')
        self.staff = User.objects.create_user('seo-staff', is_staff=True)
        self.manager = User.objects.create_user('seo-manager')
        self.member = User.objects.create_user('seo-member')
        self.org = Organization.objects.create(name='SEO tenant', slug='seo-tenant')
        with organization_scope(self.org):
            Membership.objects.create(user=self.manager, role='admin')
            Membership.objects.create(user=self.member)
        self.data = {'site_url': 'https://manuals.example.test', 'title': 'Configured title', 'description': 'Configured description', 'keywords': 'manual,book', 'generator_content': 'ManualBook', 'og_site_name': 'ManualBook', 'twitter_card': 'summary_large_image', 'sitemap_enabled': 'on', 'sitemap_cache_seconds': 300}

    def test_global_management_requires_active_site_superuser(self):
        self.assertEqual(self.client.get('/organizations/seo/').status_code, 302)
        for user in (self.staff, self.manager, self.member):
            self.client.force_login(user)
            for route in ('', 'edit/', 'delete/'):
                for method in ('get', 'post'):
                    with self.subTest(user=user, route=route, method=method):
                        response = getattr(self.client, method)('/organizations/seo/' + route, self.data if method == 'post' else {})
                        self.assertEqual(response.status_code, 403)
        self.assertFalse(SEOConfiguration.objects.exists())
        self.owner.is_active = False
        self.owner.save(update_fields=['is_active'])
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post('/organizations/seo/edit/', self.data).status_code, 302)
        self.assertFalse(SEOConfiguration.objects.exists())

    def test_superuser_can_create_update_and_delete_global_configuration(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get('/organizations/seo/').status_code, 200)
        response = self.client.post('/organizations/seo/edit/', self.data)
        self.assertEqual(response.status_code, 302)
        configuration = SEOConfiguration.objects.get()
        self.assertEqual(configuration.title, self.data['title'])
        response = self.client.post('/organizations/seo/edit/', {**self.data, 'title': 'Updated title'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SEOConfiguration.objects.get().title, 'Updated title')
        response = self.client.get('/organizations/seo/delete/')
        self.assertIn(response.status_code, (200, 405))
        self.assertTrue(SEOConfiguration.objects.exists())
        self.assertEqual(self.client.post('/organizations/seo/delete/').status_code, 302)
        self.assertFalse(SEOConfiguration.objects.exists())
        self.assertEqual(list(LogEntry.objects.filter(user=self.owner).order_by('pk').values_list('action_flag', flat=True)), [ADDITION, CHANGE, DELETION])

    def test_tenant_paths_cannot_read_or_modify_global_configuration(self):
        configuration = SEOConfiguration.objects.create(**{k: v for k, v in self.data.items() if k != 'sitemap_enabled'})
        for user in (self.owner, self.manager, self.member):
            self.client.force_login(user)
            for route in ('', 'edit/', 'delete/'):
                for method in ('get', 'post'):
                    response = getattr(self.client, method)('/o/seo-tenant/organizations/seo/' + route, self.data if method == 'post' else {})
                    self.assertEqual(response.status_code, 404)
        configuration.refresh_from_db()
        self.assertEqual(configuration.title, self.data['title'])

    def test_delete_enforces_csrf_and_preserves_configuration_on_rejection(self):
        SEOConfiguration.objects.create(title='Keep configuration')
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post('/organizations/seo/delete/').status_code, 403)
        self.assertTrue(SEOConfiguration.objects.exists())
        response = client.get('/organizations/seo/edit/')
        self.assertEqual(response.status_code, 200)
        token = client.cookies['csrftoken'].value
        self.assertEqual(client.post('/organizations/seo/delete/', {'csrfmiddlewaretoken': token}).status_code, 302)
        self.assertFalse(SEOConfiguration.objects.exists())

    def test_external_url_validation_rejects_unsafe_schemes_and_credentials(self):
        for field in ('site_url', 'og_image_url'):
            for url in ('javascript:alert(1)', 'http://example.test', 'https://user:password@example.test/image.png'):
                with self.subTest(field=field, url=url):
                    configuration = SEOConfiguration(**{field: url})
                    with self.assertRaises(ValidationError):
                        configuration.full_clean()
        self.client.force_login(self.owner)
        response = self.client.post('/organizations/seo/edit/', {**self.data, 'site_url': 'https://user:password@example.test'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SEOConfiguration.objects.exists())

    def test_intro_metadata_is_escaped_and_sitemap_excludes_tenant_urls(self):
        default = self.client.get('/intro/')
        self.assertEqual(default.status_code, 200)
        self.assertContains(default, 'name="description"')
        configuration = SEOConfiguration.objects.create(site_url='https://manuals.example.test', title='Title <script>bad</script>', description='Description "quoted" <tag>', generator_enabled=True, generator_content='Builder "quoted"', og_image_url='https://images.example.test/share.png', og_image_width=1200, og_image_height=630, twitter_handle='@manualbook', sitemap_enabled=True, sitemap_cache_seconds=300)
        response = self.client.get('/intro/')
        self.assertContains(response, 'Title &lt;script&gt;bad&lt;/script&gt;')
        self.assertNotContains(response, '<script>bad</script>')
        self.assertContains(response, 'https://manuals.example.test/intro/')
        self.assertContains(response, 'Description &quot;quoted&quot; &lt;tag&gt;')
        self.assertContains(response, 'Builder &quot;quoted&quot;')
        self.assertContains(response, 'https://images.example.test/share.png')
        self.assertContains(response, 'content="1200"')
        self.assertContains(response, 'content="630"')
        self.assertContains(response, '@manualbook')
        self.assertIn('noindex', self.client.get('/login/')['X-Robots-Tag'])
        sitemap = self.client.get('/sitemap.xml')
        self.assertEqual(sitemap.status_code, 200)
        self.assertContains(sitemap, 'https://manuals.example.test/intro/')
        self.assertEqual(sitemap.content.count(b'<loc>'), 1)
        self.assertIn('max-age=300', sitemap['Cache-Control'])
        self.assertNotContains(sitemap, '/o/')
        robots = self.client.get('/robots.txt')
        self.assertEqual(robots.status_code, 200)
        self.assertContains(robots, 'Sitemap: https://manuals.example.test/sitemap.xml')
        configuration.sitemap_enabled = False
        configuration.save()
        self.assertEqual(self.client.get('/sitemap.xml').status_code, 404)
        self.assertNotContains(self.client.get('/robots.txt'), 'Sitemap:')

    def test_slashless_entry_and_highest_admin_sidebar_link(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get('/organizations/seo').status_code, 200)
        for url in ('/organizations/', '/organizations/seo/', '/o/seo-tenant/home/'):
            self.assertContains(self.client.get(url), 'href="/organizations/seo/"')
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get('/organizations/seo').status_code, 403)
        self.assertNotContains(self.client.get('/o/seo-tenant/home/'), 'href="/organizations/seo/"')
