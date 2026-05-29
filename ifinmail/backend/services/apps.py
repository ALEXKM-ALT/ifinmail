from django.apps import AppConfig


class ServicesConfig(AppConfig):
    default_auto_field: str = 'django.db.models.BigAutoField'
    name: str = 'backend.services'
    label: str = 'ifinmail_services'
