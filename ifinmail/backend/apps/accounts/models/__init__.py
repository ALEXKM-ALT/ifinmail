import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models


class MailUserManager(BaseUserManager["MailUser"]):
    def create_user(self, email: str, password: str | None = None, **extra_fields: object) -> "MailUser":
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if user.id is None:
            user.id = uuid.uuid4()
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields: object) -> "MailUser":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(email, password, **extra_fields)


class MailUser(AbstractBaseUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.CharField(max_length=255, unique=True)
    password_hash = models.CharField(max_length=512, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = MailUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        managed = False
        db_table = "users"

    def __str__(self) -> str:
        return self.email

    def has_perm(self, perm: str, obj: object = None) -> bool:
        return self.is_superuser

    def has_module_perms(self, app_label: str) -> bool:
        return self.is_superuser
