from django.db import models


class DNSProviderConfig(models.Model):
    """Encrypted DNS provider credentials."""
    provider = models.CharField(max_length=32, unique=True, choices=[
        ("cloudflare", "Cloudflare"),
        ("porkbun", "Porkbun"),
        ("digitalocean", "DigitalOcean"),
    ])
    credentials = models.JSONField(default=dict)  # {api_token: "...", api_key: "...", secret_key: "..."}
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dns_provider_config"

    def __str__(self):
        return f"DNS: {self.provider}"
