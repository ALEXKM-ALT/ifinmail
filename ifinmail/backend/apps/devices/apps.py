from django.apps import AppConfig


class DevicesConfig(AppConfig):
    default_auto_field: str = 'django.db.models.BigAutoField'
    name: str = 'backend.apps.devices'
    label: str = 'devices'
