from django.apps import AppConfig


class DomainsConfig(AppConfig):
    default_auto_field: str = 'django.db.models.BigAutoField'
    name: str = 'backend.apps.domains'
    label: str = 'domains'
