import importlib
from types import SimpleNamespace
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase


class IdentityDataMigrationTests(TestCase):
    def test_existing_accounts_backfill_without_changing_credentials_or_memberships(self):
        executor = MigrationExecutor(connection)
        state = executor.loader.project_state([('accounts', '0001_initial'), ('organizations', '0003_login_throttle')])
        User = state.apps.get_model('auth', 'User')
        Organization = state.apps.get_model('organizations', 'Organization')
        Membership = state.apps.get_model('organizations', 'Membership')
        Identity = state.apps.get_model('accounts', 'PublicIdentity')
        alpha = Organization.objects.create(name='Legacy Alpha', slug='legacy-alpha')
        beta = Organization.objects.create(name='Legacy Beta', slug='legacy-beta')
        users = []
        for org, local in [(alpha, 'unique'), (alpha, 'shared'), (beta, 'shared')]:
            user = User.objects.create(username=f'org{org.pk}__{local}', password='unchanged-password-hash')
            Membership.objects.create(organization=org, user=user, role='member', active=True)
            users.append(user)
        before = list(User.objects.values_list('pk', 'username', 'password'))
        members = list(Membership.objects.values_list('pk', 'user_id', 'organization_id'))
        migration = importlib.import_module('apps.accounts.migrations.0002_backfill_identities')
        migration.backfill(state.apps, SimpleNamespace(connection=connection))
        self.assertEqual(list(User.objects.values_list('pk', 'username', 'password')), before)
        self.assertEqual(list(Membership.objects.values_list('pk', 'user_id', 'organization_id')), members)
        self.assertEqual(Identity.objects.get(user_id=users[0].pk).public_username, 'unique')
        for user in users[1:]:
            self.assertEqual(Identity.objects.get(user_id=user.pk).public_username, user.username)
