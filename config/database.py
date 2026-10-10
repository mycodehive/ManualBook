"""SQLite by default; database drivers are installed through optional extras."""
from pathlib import Path
import dj_database_url
from django.core.exceptions import ImproperlyConfigured


def database_config(base_dir, url=None):
    url = (url or '').strip()
    if not url:
        url = f'sqlite:///{Path(base_dir) / "db.sqlite3"}'
    if url.startswith('mariadb://'):
        url = 'mysql://' + url[len('mariadb://'):]
    try:
        config = dj_database_url.parse(url, conn_max_age=60)
    except (ValueError, KeyError):
        raise ImproperlyConfigured('Invalid DATABASE_URL; choose SQLite, PostgreSQL or MariaDB.') from None
    engine = config['ENGINE']
    options = config.setdefault('OPTIONS', {})
    if engine == 'django.db.backends.sqlite3':
        if config['NAME'] != ':memory:':
            path = Path(config['NAME'])
            config['NAME'] = str(path if path.is_absolute() else Path(base_dir) / path)
        options.setdefault('timeout', 20)
        options.setdefault('transaction_mode', 'IMMEDIATE')
    elif engine == 'django.db.backends.mysql':
        config['TEST'] = {'CHARSET': 'utf8mb4', 'COLLATION': 'utf8mb4_bin'}
        options.setdefault('charset', 'utf8mb4')
        options.setdefault('init_command', "SET sql_mode='STRICT_TRANS_TABLES'")
        options.setdefault('isolation_level', 'read committed')
    elif engine != 'django.db.backends.postgresql':
        raise ImproperlyConfigured('DATABASE_URL must use SQLite, PostgreSQL or MariaDB.')
    return config
