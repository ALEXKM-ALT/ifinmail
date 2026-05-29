# ruff: noqa: F403,F405
import os

from .base import *

DEBUG = False

ALLOWED_HOSTS = [
    host.strip() for host in os.environ.get('ALLOWED_HOSTS', '').split(',') if host.strip()
]

if not ALLOWED_HOSTS:
    raise ValueError('ALLOWED_HOSTS environment variable must be set in production')

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]

# Database connection pooling
DATABASES['default']['CONN_MAX_AGE'] = int(os.environ.get('CONN_MAX_AGE', '300'))
DATABASES['default']['CONN_HEALTH_CHECKS'] = True
DATABASES['default']['OPTIONS'].update(
    {
        'sslmode': os.environ.get('DB_SSLMODE', 'require'),
        'application_name': os.environ.get('DB_APPLICATION_NAME', 'ifinmail-api'),
        'connect_timeout': int(os.environ.get('DB_CONNECT_TIMEOUT', '10')),
    }
)

# Static files — content-hashed filenames for cache busting (EC-35)
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# Security
SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True').lower() == 'true'
# Exempt internal health checks from SSL redirect
# (Docker healthcheck hits API directly on port 8000)
SECURE_REDIRECT_EXEMPT = [r'^health']
SECURE_PROXY_SSL_HEADER = (
    'HTTP_X_FORWARDED_PROTO',
    os.environ.get('SECURE_PROXY_HEADER_VALUE', 'https'),
)
USE_X_FORWARDED_HOST = os.environ.get('USE_X_FORWARDED_HOST', 'True').lower() == 'true'
SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '3600'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = (
    os.environ.get('SECURE_HSTS_INCLUDE_SUBDOMAINS', 'True').lower() == 'true'
)
SECURE_HSTS_PRELOAD = os.environ.get('SECURE_HSTS_PRELOAD', 'True').lower() == 'true'
SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'True').lower() == 'true'
CSRF_COOKIE_SECURE = os.environ.get('CSRF_COOKIE_SECURE', 'True').lower() == 'true'
SECURE_REFERRER_POLICY = os.environ.get('SECURE_REFERRER_POLICY', 'same-origin')
SECURE_CROSS_ORIGIN_OPENER_POLICY = os.environ.get(
    'SECURE_CROSS_ORIGIN_OPENER_POLICY', 'same-origin-allow-popups'
)

# Sentry
SENTRY_DSN = os.environ.get('SENTRY_DSN', '')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=float(os.environ.get('SENTRY_TRACES_RATE', '0.1')),
        send_default_pii=False,
        environment=os.environ.get('SENTRY_ENVIRONMENT', 'production'),
    )

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.environ.get('LOG_LEVEL_ROOT', 'WARNING'),
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.environ.get('LOG_LEVEL_DJANGO', 'WARNING'),
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': os.environ.get('LOG_LEVEL_DJANGO_REQUEST', 'WARNING'),
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console'],
            'level': os.environ.get('LOG_LEVEL_DJANGO_SECURITY', 'WARNING'),
            'propagate': False,
        },
        'backend': {
            'handlers': ['console'],
            'level': os.environ.get('LOG_LEVEL_BACKEND', 'INFO'),
            'propagate': False,
        },
    },
}
