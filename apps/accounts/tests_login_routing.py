"""Account switching must preserve tenant isolation and rotate the session."""
from importlib import import_module

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.accounts.identity import create_identity_user
from apps.core.bootstrap import seed_platform
from apps.organizations.models import Membership, Organization
from apps.organizations.scoping import organization_scope


@override_settings(SECURE_SSL_REDIRECT=False)
class LoginSessionRoutingTests(TestCase):
    password = 'Unique-session-password-947!'

    def setUp(self):
        self.alpha = Organization.objects.create(name='Alpha', slug='alpha')
        self.beta = Organization.objects.create(name='Beta', slug='beta')
        self.alpha_user = create_identity_user('alpha-reader', password=self.password)
        self.beta_user = create_identity_user('beta-reader', password=self.password)
        self.highest = get_user_model().objects.create_superuser('platform-owner', password=self.password)
        for organization, user in [(self.alpha, self.alpha_user), (self.beta, self.beta_user)]:
            with organization_scope(organization):
                seed_platform()
                Membership.objects.create(user=user)

    def submit(self, path, username, **extra):
        return self.client.post(path, {'username': username, 'password': self.password, **extra})

    def assert_login_form(self, response):
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="login-form"')
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')

    def test_highest_admin_tenant_login_always_returns_global_organization_selection(self):
        for target in ['', '/o/alpha/home/', '/o/beta/home/', '/organizations/identity-policy/']:
            with self.subTest(next=target):
                self.client.logout()
                response = self.submit('/o/alpha/login/', 'platform-owner', next=target)
                self.assertRedirects(response, '/organizations/', fetch_redirect_response=False)
                self.assertEqual(int(self.client.session['_auth_user_id']), self.highest.pk)

    def test_highest_admin_global_login_ignores_workspace_next(self):
        response = self.submit('/login/', 'platform-owner', next='/o/beta/home/')
        self.assertRedirects(response, '/organizations/', fetch_redirect_response=False)

    def test_existing_other_organization_session_can_open_login_form(self):
        self.client.force_login(self.beta_user)
        response = self.client.get('/o/alpha/login/')
        self.assert_login_form(response)
        self.assertIn('no-store', response.headers.get('Cache-Control', ''))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.beta_user.pk)

    def test_successful_account_switch_invalidates_old_session(self):
        self.client.force_login(self.beta_user)
        old_key = self.client.session.session_key
        self.assert_login_form(self.client.get('/o/alpha/login/'))
        response = self.submit('/o/alpha/login/', 'alpha-reader')
        self.assertRedirects(response, '/o/alpha/home/', fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.alpha_user.pk)
        self.assertNotEqual(self.client.session.session_key, old_key)
        session_store = import_module(settings.SESSION_ENGINE).SessionStore
        self.assertFalse(session_store(session_key=old_key).exists(old_key))
        self.assertEqual(self.client.get('/o/alpha/home/').status_code, 200)
        self.assertEqual(self.client.get('/o/beta/home/').status_code, 403)

    def test_failed_account_switch_retains_prior_session_without_tenant_access(self):
        self.client.force_login(self.beta_user)
        old_key = self.client.session.session_key
        response = self.client.post('/o/alpha/login/', {'username': 'alpha-reader', 'password': 'wrong-password'})
        self.assert_login_form(response)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.beta_user.pk)
        self.assertEqual(self.client.session.session_key, old_key)
        self.assertEqual(self.client.get('/o/alpha/home/').status_code, 403)
        self.assertEqual(self.client.get('/o/beta/home/').status_code, 200)

    def test_ordinary_member_cannot_authenticate_at_foreign_organization(self):
        response = self.submit('/o/beta/login/', 'alpha-reader')
        self.assert_login_form(response)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_ordinary_member_cannot_follow_forged_cross_organization_next(self):
        for target in ['/o/beta/home/', 'https://attacker.example/o/alpha/home/']:
            with self.subTest(next=target):
                self.client.logout()
                response = self.submit('/o/alpha/login/', 'alpha-reader', next=target)
                self.assertRedirects(response, '/o/alpha/home/', fetch_redirect_response=False)
                self.assertEqual(self.client.get('/o/beta/home/').status_code, 403)

    def test_authenticated_global_login_page_remains_visible_and_uncached(self):
        self.client.force_login(self.beta_user)
        response = self.client.get('/login/')
        self.assert_login_form(response)
        self.assertIn('no-store', response.headers.get('Cache-Control', ''))
