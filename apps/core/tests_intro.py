"""The supplied introduction is global and preserves its image assets."""
from pathlib import Path
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.test import TestCase, override_settings
from apps.organizations.models import Organization, Membership
from apps.organizations.scoping import organization_scope


@override_settings(SECURE_SSL_REDIRECT=False)
class IntroductionPageTests(TestCase):
    ASSETS = ('manualbook_hero.png', 'manualbook_features.png', 'manualbook_usecases.png')

    def setUp(self):
        User = get_user_model()
        self.member = User.objects.create_user('intro-member', password='Intro-password-952!')
        self.admin = User.objects.create_superuser('intro-owner', password='Intro-password-952!')
        self.organization = Organization.objects.create(name='Intro company', slug='intro-company')
        with organization_scope(self.organization):
            Membership.objects.create(user=self.member)

    def test_global_intro_works_for_anonymous_members_and_superusers(self):
        for user in (None, self.member, self.admin):
            self.client.logout()
            if user:
                self.client.force_login(user)
            for url in ('/intro', '/intro/'):
                with self.subTest(user=user, url=url):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 200)
                    self.assertTemplateUsed(response, 'core/intro.html')
                    self.assertContains(response, '팀의 업무 지식을,')
                    self.assertNotContains(response, 'name="username"')
                    self.assertEqual(self.client.head(url).status_code, 200)
                    self.assertEqual(self.client.post(url).status_code, 405)

    def test_static_images_are_available_at_rendered_paths(self):
        response = self.client.get('/intro/')
        for name in self.ASSETS:
            asset = 'intro/images/' + name
            path = finders.find(asset)
            self.assertIsNotNone(path)
            data = Path(path).read_bytes()
            self.assertTrue(data.startswith(b'\x89PNG\r\n\x1a\n'))
            self.assertContains(response, '/static/' + asset)
        self.assertNotContains(response, 'src="images/')
        self.assertContains(response, 'content="/static/intro/images/manualbook_hero.png"')

    def test_intro_exemption_is_exact_and_not_available_in_tenant(self):
        for user in (None, self.member, self.admin):
            self.client.logout()
            if user:
                self.client.force_login(user)
            for url in ('/intro-extra', '/intro/private/', '/o/intro-company/intro', '/o/intro-company/intro/'):
                with self.subTest(user=user, url=url):
                    response = self.client.get(url)
                    self.assertIn(response.status_code, (302, 403, 404))
                    self.assertTemplateNotUsed(response, 'core/intro.html')
                    self.assertNotIn(b'hero-grid', response.content)
                    if user and url.startswith('/o/'):
                        self.assertEqual(response.status_code, 404)

    def test_root_entry_keeps_existing_login_routing(self):
        response = self.client.get('/')
        self.assertRedirects(response, '/login/', fetch_redirect_response=False)
        self.client.force_login(self.member)
        response = self.client.get('/')
        self.assertRedirects(response, '/o/intro-company/home/', fetch_redirect_response=False)
        self.client.force_login(self.admin)
        response = self.client.get('/')
        self.assertRedirects(response, '/organizations/', fetch_redirect_response=False)
