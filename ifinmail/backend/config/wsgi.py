"""
WSGI config for ifinmail.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.config.settings.production')
application = get_wsgi_application()
