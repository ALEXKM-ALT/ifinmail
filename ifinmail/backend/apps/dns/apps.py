from django.apps import AppConfig


class DNSConfig(AppConfig):
    default_auto_field: str = "django.db.models.BigAutoField"
    name: str = "backend.apps.dns"
    label: str = "dns"
