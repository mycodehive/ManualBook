from importlib import import_module
from types import SimpleNamespace
from django.contrib.auth import authenticate, get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from apps.organizations.models import Organization, Membership
from apps.organizations.scoping import organization_scope
from .identity import create_identity_user, RESERVED_MESSAGE
from .models import IdentityPolicy, PublicIdentity


class GlobalIdentityBackendTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name='Login A', slug='login-a')
        self.other = Organization.objects.create(name='Login B', slug='login-b')
        self.user = create_identity_user('Owner.A', password='valid-login-password')
        with organization_scope(self.org):
            Membership.objects.create(user=self.user, role='admin')

    def test_global_and_tenant_authentication_resolve_one_identity(self):
        for org in (None, self.org):
            self.assertEqual(authenticate(SimpleNamespace(organization=org), username='OWNER.a', password='valid-login-password'), self.user)
        self.assertIsNone(authenticate(SimpleNamespace(organization=self.other), username='owner.a', password='valid-login-password'))
        Membership.all_objects.filter(user=self.user).update(active=False)
        self.assertIsNone(authenticate(SimpleNamespace(organization=None), username='owner.a', password='valid-login-password'))

    def test_superuser_reserved_id_is_not_locked_out(self):
        admin = get_user_model().objects.create_superuser('admin', password='valid-admin-password')
        for org in (None, self.other):
            self.assertEqual(authenticate(SimpleNamespace(organization=org), username='ADMIN', password='valid-admin-password'), admin)

    def test_direct_creation_policy_and_username_immutability(self):
        with self.assertRaisesMessage(ValidationError, RESERVED_MESSAGE):
            get_user_model().objects.create_user('manager', password='password')
        self.assertFalse(get_user_model().objects.filter(username='manager').exists())
        self.user.username = 'renamed'
        with self.assertRaisesMessage(ValidationError, '기존 계정의 아이디는 변경할 수 없습니다.'):
            self.user.save()
        self.assertEqual(PublicIdentity.objects.get(user=self.user).public_username, 'owner.a')

    def test_policy_is_mutable_and_normalized(self):
        policy = IdentityPolicy.objects.get(pk=1)
        policy.reserved_usernames = ['Custom', ' custom ']
        policy.save()
        self.assertEqual(policy.reserved_usernames, ['custom'])
        with self.assertRaisesMessage(ValidationError, RESERVED_MESSAGE):
            create_identity_user('CUSTOM')
        self.assertEqual(create_identity_user('manager').username, 'manager')


class IdentityBackfillMappingTests(TestCase):
    def mapping(self, users, memberships):
        return import_module('apps.accounts.migrations.0002_backfill_identities').identity_mapping(users, set(memberships))

    def test_unique_legacy_alias_preserves_account_and_conflicts_retain_canonical(self):
        self.assertEqual(self.mapping([(1, 'org2__unique'), (2, 'admin')], [(1, 2)]), {1: 'unique', 2: 'admin'})
        self.assertEqual(self.mapping([(1, 'org2__same'), (2, 'org3__Same')], [(1, 2), (2, 3)]), {1: 'org2__same', 2: 'org3__Same'})
        self.assertEqual(self.mapping([(1, 'org2__bob'), (2, 'bob')], [(1, 2)]), {1: 'org2__bob', 2: 'bob'})

    def test_raw_casefold_collision_is_explicit_error(self):
        with self.assertRaisesMessage(RuntimeError, '로그인 아이디 충돌'):
            self.mapping([(1, 'Bob'), (2, 'bob')], [])
