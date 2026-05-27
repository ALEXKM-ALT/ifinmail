from django.apps import AppConfig


class StorageConfig(AppConfig):
    name = "backend.apps.core.storage"
    label = "ifinmail_storage"
    verbose_name = "ifinmail Storage"

    def ready(self):
        import backend.apps.core.storage.signals  # noqa: F401 — register signal handlers (EC-77)
