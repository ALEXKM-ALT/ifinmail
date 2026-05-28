import uuid

from django.db import models


class Domain(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    verified = models.BooleanField(default=False)
    mx_verified = models.BooleanField(default=False)
    spf_verified = models.BooleanField(default=False)
    dkim_verified = models.BooleanField(default=False)
    dmarc_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "domains"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class DKIMKey(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey(
        Domain, on_delete=models.CASCADE, db_column="domain_id"
    )
    selector = models.CharField(max_length=64, default="default")
    private_key = models.TextField()
    public_key = models.TextField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = "dkim_keys"
        unique_together = [("domain", "selector")]
