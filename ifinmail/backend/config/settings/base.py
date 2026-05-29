"""
Base Django settings for ifinmail.
"""

import os
import re
from pathlib import Path
from typing import Any

from django.core.checks import Error, register

from backend.config.branding import BrandingConfig

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
DEBUG = False
ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'corsheaders',
    'axes',
    # ifinmail core (cross-cutting foundation)
    'backend.apps.core.apps.CoreConfig',
    'backend.apps.core.storage.apps.StorageConfig',
    # ifinmail services (audit trail, etc.)
    'backend.services.apps.ServicesConfig',
    # ifinmail apps
    'backend.apps.accounts.apps.AccountsConfig',
    'backend.apps.devices.apps.DevicesConfig',
    'backend.apps.dns.apps.DNSConfig',
    'backend.apps.domains.apps.DomainsConfig',
    'backend.apps.mail.apps.MailConfig',
]

AUTH_USER_MODEL = 'accounts.MailUser'
LOGIN_REDIRECT_URL = '/accounts/dashboard/'
LOGIN_URL = '/accounts/login/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.gzip.GZipMiddleware',
    'django.middleware.http.ConditionalGetMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'axes.middleware.AxesMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

ROOT_URLCONF = 'backend.config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'frontend' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'backend.config.branding.brand_context',
                'backend.config.server_context.server_context',
                'backend.config.user_context.user_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.config.wsgi.application'

DATABASES: dict[str, dict[str, Any]] = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ['DB_NAME'],
        'USER': os.environ['DB_USER'],
        'PASSWORD': os.environ['DB_PASSWORD'],
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'CONN_MAX_AGE': int(os.environ.get('CONN_MAX_AGE', '0')),
        'CONN_HEALTH_CHECKS': True,
        'OPTIONS': {
            'sslmode': os.environ.get('DB_SSLMODE', 'prefer'),
            'application_name': os.environ.get('DB_APPLICATION_NAME', 'ifinmail-api'),
            'connect_timeout': int(os.environ.get('DB_CONNECT_TIMEOUT', '10')),
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = os.environ.get('LANGUAGE_CODE', 'en-us')
TIME_ZONE = os.environ.get('TIME_ZONE', 'UTC')
USE_I18N = os.environ.get('USE_I18N', 'True').lower() == 'true'
USE_L10N = os.environ.get('USE_L10N', 'True').lower() == 'true'
USE_TZ = os.environ.get('USE_TZ', 'True').lower() == 'true'

LOCALE_PATHS = [BASE_DIR / 'frontend' / 'locale']

STATIC_URL = os.environ.get('STATIC_URL', '/static/')
STATICFILES_DIRS = [BASE_DIR / 'frontend' / 'static']
STATIC_ROOT = Path(os.environ.get('STATIC_ROOT', BASE_DIR / 'staticfiles'))
CSS_VERSION = os.environ.get('CSS_VERSION') or os.environ.get('APP_VERSION', 'dev')

MEDIA_URL = os.environ.get('MEDIA_URL', '/media/')
MEDIA_ROOT = Path(os.environ.get('MEDIA_ROOT', BASE_DIR / 'media'))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Security
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get('DATA_UPLOAD_MAX_MEMORY_SIZE', '2621440'))
DATA_UPLOAD_MAX_NUMBER_FIELDS = int(os.environ.get('DATA_UPLOAD_MAX_NUMBER_FIELDS', '1000'))

# Redis / Cache
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'retry_on_timeout': True,
            'socket_connect_timeout': 5,
        },
    }
}

# Session engine — use cache + DB for resilience
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'

# Celery
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/1')
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', CELERY_BROKER_URL)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_ACKS_LATE = True

# Axes — brute-force protection
AXES_FAILURE_LIMIT = int(os.environ.get('AXES_FAILURE_LIMIT', '5'))
AXES_COOLOFF_TIME = float(os.environ.get('AXES_COOLOFF_TIME', '1'))
AXES_LOCK_OUT_AT_FAILURE = True
AXES_RESET_ON_SUCCESS = True

# CORS
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get('CORS_ALLOWED_ORIGINS', '').split(',')
    if origin.strip()
]

# Email
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '25'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'False').lower() == 'true'
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'False').lower() == 'true'
_domain = os.environ.get('DOMAIN', os.environ.get('MAIL_DOMAIN', ''))
DEFAULT_FROM_EMAIL = os.environ.get(
    'DEFAULT_FROM_EMAIL', f'noreply@{_domain}' if _domain else 'noreply@localhost'
)

# Branding (self-hosted customization)
BRAND_CONFIG = BrandingConfig.from_env()


# ── Startup validation ──────────────────────────────────────────────────────


@register()
def check_critical_env_vars(app_configs, **kwargs) -> list[Error]:
    """Validate critical environment variables at startup."""
    errors: list[Error] = []

    required_vars = {
        'DJANGO_SECRET_KEY': 'Secret key must be set for cryptographic signing',
        'DB_NAME': 'Database name must be set',
        'DB_USER': 'Database user must be set',
        'DB_PASSWORD': 'Database password must be set',
    }
    for var, hint in required_vars.items():
        if not os.environ.get(var):
            errors.append(
                Error(
                    f'Environment variable {var} is not set',
                    hint=hint,
                    id='ifinmail.E001',
                )
            )

    return errors


@register()
def check_email_config(app_configs, **kwargs) -> list[Error]:
    """Validate email configuration."""
    errors: list[Error] = []

    tls = os.environ.get('EMAIL_USE_TLS', 'False').lower() == 'true'
    ssl = os.environ.get('EMAIL_USE_SSL', 'False').lower() == 'true'
    if tls and ssl:
        errors.append(
            Error(
                'EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be enabled',
                hint='Set only one of EMAIL_USE_TLS or EMAIL_USE_SSL to True',
                id='ifinmail.E002',
            )
        )

    from_email = os.environ.get('DEFAULT_FROM_EMAIL', '')
    if from_email:
        match = re.match(r'^[^@]+@([^@]+)$', from_email)
        if not match:
            errors.append(
                Error(
                    f"DEFAULT_FROM_EMAIL '{from_email}' is not a valid email address",
                    hint=(
                        'Set DEFAULT_FROM_EMAIL to a valid email address '
                        '(e.g. noreply@example.com)'
                    ),
                    id='ifinmail.E003',
                )
            )

    return errors
