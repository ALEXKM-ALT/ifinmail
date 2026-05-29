# ruff: noqa: F403,F405
import os

os.environ.setdefault('DJANGO_SECRET_KEY', 'dev-insecure-key-change-in-production')
os.environ.setdefault('DB_NAME', 'ifinmail')
os.environ.setdefault('DB_USER', 'ifinmail')
os.environ.setdefault('DB_PASSWORD', 'ifinmail')

from .base import *

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

INSTALLED_APPS += [
    'django_extensions',
]

# Use SQLite for local development when Postgres is unavailable
if os.environ.get('USE_SQLITE') or not os.environ.get('DB_HOST'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }

LOGIN_REDIRECT_URL = '/accounts/dashboard/'
LOGIN_URL = '/accounts/login/'
LOGOUT_REDIRECT_URL = '/accounts/login/'
