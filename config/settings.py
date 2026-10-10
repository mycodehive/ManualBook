from pathlib import Path
import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from .env import get_env

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = get_env('DJANGO_DEBUG', 'false').lower() == 'true'
SECRET_KEY = get_env('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('Set DJANGO_SECRET_KEY before production startup.')
    SECRET_KEY = 'manualbook-development-only-not-for-production-0123456789'
if not DEBUG and (len(SECRET_KEY) < 50 or SECRET_KEY.startswith('manualbook-development')):
    raise ImproperlyConfigured('Production requires a strong, unique DJANGO_SECRET_KEY of at least 50 characters.')
INTEGRATION_ENCRYPTION_KEY = get_env('INTEGRATION_ENCRYPTION_KEY', '')
if INTEGRATION_ENCRYPTION_KEY:
    from cryptography.fernet import Fernet
    try:
        Fernet(INTEGRATION_ENCRYPTION_KEY.encode())
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured('INTEGRATION_ENCRYPTION_KEY must be a valid Fernet key.') from exc
elif not DEBUG:
    raise ImproperlyConfigured('Set INTEGRATION_ENCRYPTION_KEY and keep a secure backup before production startup.')
ALLOWED_HOSTS = get_env('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
CSRF_TRUSTED_ORIGINS = [x.strip() for x in get_env('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if x.strip()]
INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'apps.core', 'apps.accounts', 'apps.menus', 'apps.integrations', 'apps.manuals',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware', 'apps.menus.middleware.MenuAccessMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request', 'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages', 'apps.menus.context_processors.navigation',
    ]}}]
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'
DATABASES = {'default': dj_database_url.config(default=f'sqlite:///{BASE_DIR / "db.sqlite3"}', conn_max_age=60)}
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE = 'ko-kr'
TIME_ZONE = 'Asia/Seoul'
USE_I18N = True
USE_TZ = True
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = Path(get_env('DJANGO_STATIC_ROOT', str(BASE_DIR / 'staticfiles')))
MEDIA_ROOT = Path(get_env('DJANGO_MEDIA_ROOT', str(BASE_DIR / 'private_media')))
MEDIA_URL = '/private-media/'
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'login'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = get_env('DJANGO_SECURE_SSL_REDIRECT', str(not DEBUG)).lower() == 'true'
SECURE_HSTS_SECONDS = int(get_env('DJANGO_SECURE_HSTS_SECONDS', '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
if get_env('DJANGO_TRUST_PROXY', 'false').lower() == 'true':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
MANUAL_ATTACHMENT_MAX_SIZE = 10 * 1024 * 1024
