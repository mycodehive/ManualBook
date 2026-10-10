from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase
from config.database import database_config


class DatabaseConfigurationTests(SimpleTestCase):
    def test_unset_and_blank_url_default_to_sqlite(self):
        for url in (None, '', '  '):
            config = database_config(Path('/app'), url)
            self.assertEqual(config['ENGINE'], 'django.db.backends.sqlite3')
            self.assertEqual(config['NAME'], '/app/db.sqlite3')
            self.assertEqual(config['OPTIONS']['transaction_mode'], 'IMMEDIATE')

    def test_sqlite_paths_do_not_depend_on_working_directory(self):
        self.assertEqual(database_config('/app', 'sqlite:///data/db.sqlite3')['NAME'], '/app/data/db.sqlite3')
        self.assertEqual(database_config('/app', 'sqlite:////var/lib/manualbook/db.sqlite3')['NAME'], '/var/lib/manualbook/db.sqlite3')
        self.assertEqual(database_config('/app', 'sqlite:///:memory:')['NAME'], ':memory:')

    def test_postgres_has_no_sqlite_or_mysql_options(self):
        config = database_config('/app', 'postgresql://manualbook:test@localhost/manualbook')
        self.assertEqual(config['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(config['OPTIONS'], {})

    def test_mariadb_accepts_mysql_url_and_alias(self):
        for scheme in ('mysql', 'mariadb'):
            config = database_config('/app', f'{scheme}://manualbook:test@localhost/manualbook')
            self.assertEqual(config['ENGINE'], 'django.db.backends.mysql')
            self.assertEqual(config['OPTIONS']['charset'], 'utf8mb4')
            self.assertEqual(config['OPTIONS']['isolation_level'], 'read committed')
            self.assertNotIn('timeout', config['OPTIONS'])

    def test_unsupported_or_malformed_url_is_rejected_without_credentials(self):
        for url in ('oracle://user:private-password@localhost/db', 'invalid://user:private-password@localhost/db'):
            with self.assertRaises(ImproperlyConfigured) as error:
                database_config('/app', url)
            self.assertNotIn('private-password', str(error.exception))
