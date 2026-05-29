from django.apps import AppConfig


class MailConfig(AppConfig):
    default_auto_field: str = 'django.db.models.BigAutoField'
    name: str = 'backend.apps.mail'
    label: str = 'mail'
