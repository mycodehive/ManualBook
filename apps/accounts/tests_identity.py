"""Global login identity and organization creation boundaries."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.core.bootstrap import seed_platform
from apps.organizations.forms import MembershipForm, OrganizationForm
from apps.organizations.models import Membership, Organization
from apps.organizations.scoping import organization_scope
from .identity import create_identity_user
from .models import IdentityPolicy, PublicIdentity


@override_settings(SECURE_SSL_REDIRECT=False)
class GlobalIdentityIntegrationTests(TestCase):
    password = 'Unique-account-password-731!'

    def setUp(self):
        self.alpha = Organization.objects.create(name='Alpha', slug='alpha')
        self.beta = Organization.objects.create(name='Beta', slug='beta')
        self.admin = create_identity_user('alpha-owner', password=self.password)
        self.member = create_identity_user('reader-one', password=self.password)
        self.highest = get_user_model().objects.create_superuser('highest-owner', password=self.password)
        with organization_scope(self.alpha):
            seed_platform()
            Membership.objects.create(user=self.admin, role='admin')
            self.membership = Membership.objects.create(user=self.member)
        with organization_scope(self.beta):
            seed_platform()

    def login(self, username='reader-one', path='/login/', **extra):
        return self.client.post(path, {'username': username, 'password': self.password, **extra})

    def new_member_data(self, username):
        return {'username': username, 'role': 'member', 'active': 'on', 'password': self.password, 'password_confirm': self.password}

    def new_organization_data(self, username):
        return {'name': 'New Company', 'slug': 'new-company', 'active': 'on', 'admin_username': username, 'admin_password': self.password, 'confirmation': self.password}

    def test_global_login_routes_single_active_membership_to_workspace(self):
        response = self.login('READER-ONE')
        self.assertRedirects(response, '/o/alpha/home/', fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.member.pk)

    def test_global_login_routes_multiple_memberships_to_selection(self):
        with organization_scope(self.beta):
            Membership.objects.create(user=self.member)
        self.assertRedirects(self.login(), '/organizations/', fetch_redirect_response=False)

    def test_highest_administrator_global_login_routes_to_selection(self):
        self.assertRedirects(self.login('highest-owner'), '/organizations/', fetch_redirect_response=False)

    def test_tenant_login_uses_same_id_and_rejects_other_organization(self):
        self.assertEqual(self.login(path='/o/beta/login/').status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertRedirects(self.login(path='/o/alpha/login/'), '/o/alpha/home/', fetch_redirect_response=False)

    def test_global_login_refuses_account_without_active_organization(self):
        with organization_scope(self.alpha):
            self.membership.active = False
            self.membership.save()
        self.assertEqual(self.login().status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_global_login_refuses_inactive_organization(self):
        self.alpha.active = False
        self.alpha.save()
        self.assertEqual(self.login().status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_global_login_ignores_external_next(self):
        self.assertRedirects(self.login(next='https://attacker.example/'), '/o/alpha/home/', fetch_redirect_response=False)

    def test_global_login_ignores_foreign_organization_next(self):
        self.assertRedirects(self.login(next='/o/beta/home/'), '/o/alpha/home/', fetch_redirect_response=False)

    def test_duplicate_case_insensitive_member_id_cannot_cross_organizations(self):
        with organization_scope(self.beta):
            form = MembershipForm(self.new_member_data('READER-ONE'), organization=self.beta)
            self.assertFalse(form.is_valid())
            self.assertIn('username', form.errors)

    def test_reserved_policy_applies_to_both_creation_forms(self):
        IdentityPolicy.objects.update_or_create(pk=1, defaults={'reserved_usernames': ['protected-name']})
        with organization_scope(self.alpha):
            member = MembershipForm(self.new_member_data('PROTECTED-NAME'), organization=self.alpha)
            self.assertFalse(member.is_valid())
            self.assertIn('username', member.errors)
        organization = OrganizationForm(self.new_organization_data('protected-name'))
        self.assertFalse(organization.is_valid())
        self.assertIn('admin_username', organization.errors)

    def test_reserved_first_administrator_leaves_no_organization_or_user(self):
        self.client.force_login(self.highest)
        counts = (Organization.objects.count(), get_user_model().objects.count(), PublicIdentity.objects.count(), Membership.all_objects.count())
        response = self.client.post('/organizations/create/', self.new_organization_data('admin'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(counts, (Organization.objects.count(), get_user_model().objects.count(), PublicIdentity.objects.count(), Membership.all_objects.count()))
        self.assertFalse(Organization.objects.filter(slug='new-company').exists())

    def test_duplicate_first_administrator_leaves_no_organization(self):
        self.client.force_login(self.highest)
        response = self.client.post('/organizations/create/', self.new_organization_data('READER-ONE'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Organization.objects.filter(slug='new-company').exists())

    def test_rejected_member_registration_leaves_no_partial_records(self):
        self.client.force_login(self.admin)
        IdentityPolicy.objects.update_or_create(pk=1, defaults={'reserved_usernames': ['protected-member']})
        counts = (get_user_model().objects.count(), PublicIdentity.objects.count(), Membership.all_objects.count())
        for username in ['protected-member', 'READER-ONE']:
            with self.subTest(username=username):
                response = self.client.post('/o/alpha/organization/members/create/', self.new_member_data(username))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(counts, (get_user_model().objects.count(), PublicIdentity.objects.count(), Membership.all_objects.count()))

    def test_member_creation_publishes_normalized_global_id_without_privileges(self):
        self.client.force_login(self.admin)
        response = self.client.post('/o/alpha/organization/members/create/', {**self.new_member_data('NEW-READER'), 'is_staff': 'on', 'is_superuser': 'on'})
        self.assertRedirects(response, '/o/alpha/organization/members/', fetch_redirect_response=False)
        user = get_user_model().objects.get(username='new-reader')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(PublicIdentity.objects.get(user=user).public_username, 'new-reader')
        self.assertEqual(Membership.all_objects.get(user=user).display_username, 'new-reader')
        self.client.logout()
        self.assertRedirects(self.login('new-reader'), '/o/alpha/home/', fetch_redirect_response=False)

    def test_identity_policy_is_only_available_to_global_highest_administrator(self):
        self.assertEqual(self.client.get('/organizations/identity-policy/').status_code, 302)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/organizations/identity-policy/').status_code, 403)
        self.assertEqual(self.client.post('/organizations/identity-policy/', {'reserved_usernames': 'forbidden-change'}).status_code, 403)
        self.client.force_login(self.highest)
        self.assertEqual(self.client.get('/o/alpha/organizations/identity-policy/').status_code, 403)
        self.assertEqual(self.client.get('/organizations/identity-policy/').status_code, 200)
        response = self.client.post('/organizations/identity-policy/', {'reserved_usernames': 'admin\nNEWRESERVED\nnewreserved'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(IdentityPolicy.objects.get(pk=1).reserved_usernames, ['admin', 'newreserved'])

    def test_reserved_policy_does_not_lock_existing_account_out(self):
        IdentityPolicy.objects.update_or_create(pk=1, defaults={'reserved_usernames': ['reader-one']})
        self.assertRedirects(self.login(), '/o/alpha/home/', fetch_redirect_response=False)

    def test_global_root_routes_authenticated_account_using_active_memberships(self):
        self.assertRedirects(self.client.get('/'), '/login/', fetch_redirect_response=False)
        self.client.force_login(self.member)
        self.assertRedirects(self.client.get('/'), '/o/alpha/home/', fetch_redirect_response=False)
        with organization_scope(self.beta):
            Membership.objects.create(user=self.member)
        self.assertRedirects(self.client.get('/'), '/organizations/', fetch_redirect_response=False)
