from django.db import models

from backend.apps.core.base.models.base import CoreModel


class DNSProviderConfig(CoreModel):
    """Encrypted DNS provider credentials."""
    id = models.BigAutoField(primary_key=True)
    provider = models.CharField(max_length=32, unique=True, choices=[
        ("cloudflare", "Cloudflare"),
        ("porkbun", "Porkbun"),
        ("digitalocean", "DigitalOcean"),
    ])
    credentials = models.JSONField(default=dict)

    class Meta:
        managed = False
        db_table = "dns_provider_config"

    def __str__(self) -> str:
        return f"DNS: {self.provider}"
