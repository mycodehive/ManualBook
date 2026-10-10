from django.contrib.auth import get_user_model
from django.middleware.csrf import _get_new_csrf_string
from django.test import Client, TestCase, override_settings
from apps.organizations.models import Organization, Membership
from apps.organizations.scoping import organization_scope


@override_settings(ALLOWED_HOSTS=['testserver'], SECURE_SSL_REDIRECT=False)
class LogoutCsrfTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='WriteAday', slug='writeaday')
        self.user = get_user_model().objects.create_user(username='logout-test', password='test-password')
        with organization_scope(self.org):
            Membership.objects.create(user=self.user, role='admin')
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(self.user, backend='apps.organizations.backends.OrganizationBackend')
        self.path = '/o/writeaday/logout/'

    def token(self):
        response = self.client.get('/o/writeaday/home/')
        self.assertEqual(response.status_code, 200)
        return self.client.cookies['csrftoken'].value

    def assert_logged_in(self):
        self.assertEqual(self.client.session.get('_auth_user_id'), str(self.user.pk))

    def test_valid_logout_and_get_does_not_logout(self):
        token = self.token()
        self.assertEqual(self.client.get(self.path).status_code, 405)
        self.assert_logged_in()
        response = self.client.post(self.path, {'csrfmiddlewaretoken': token})
        self.assertRedirects(response, '/o/writeaday/login/', fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_stale_token_rejected_then_explicit_fresh_retry_logs_out(self):
        stale = self.token()
        self.client.cookies['csrftoken'] = _get_new_csrf_string()
        response = self.client.post(self.path, {'csrfmiddlewaretoken': stale})
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, '로그아웃 다시 시도', status_code=403)
        self.assertContains(response, 'action="/o/writeaday/logout/"', status_code=403)
        self.assertIn('no-store', response['Cache-Control'])
        self.assert_logged_in()
        fresh = self.client.cookies['csrftoken'].value
        retry = self.client.post(self.path, {'csrfmiddlewaretoken': fresh})
        self.assertRedirects(retry, '/o/writeaday/login/', fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_missing_token_or_foreign_origin_cannot_logout(self):
        token = self.token()
        response = self.client.post(self.path)
        self.assertEqual(response.status_code, 403)
        self.assert_logged_in()
        response = self.client.post(self.path, {'csrfmiddlewaretoken': token}, HTTP_ORIGIN='https://attacker.example')
        self.assertEqual(response.status_code, 403)
        self.assert_logged_in()

    def test_https_external_port_and_trusted_proxy_preserve_same_origin(self):
        token = self.token()
        with self.settings(SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https')):
            response = self.client.post(self.path, {'csrfmiddlewaretoken': token},
                HTTP_HOST='testserver:36980', HTTP_X_FORWARDED_PROTO='https', HTTP_ORIGIN='https://testserver:36980')
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)
