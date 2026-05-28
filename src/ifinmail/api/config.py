import os
import sys


class Settings:
    database_url: str = os.environ.get(
        "IFINMAIL_DATABASE_URL",
        "sqlite:////home/alex/.ifinmail/admin.db",
    )
    redis_url: str = os.environ.get(
        "IFINMAIL_REDIS_URL",
        "redis://localhost:6379/0",
    )
    secret_key: str = os.environ.get(
        "IFINMAIL_SECRET_KEY",
        "dev-secret-key-change-in-production",
    )
    access_token_expire_minutes: int = int(os.environ.get("IFINMAIL_ACCESS_TOKEN_EXPIRE", "1440"))
    refresh_token_expire_days: int = int(os.environ.get("IFINMAIL_REFRESH_TOKEN_EXPIRE", "7"))
    algorithm: str = "HS256"
    default_domain: str = os.environ.get(
        "IFINMAIL_DEFAULT_DOMAIN",
        "ifinmail.local",
    )
    app_url: str = os.environ.get("IFINMAIL_APP_URL", "http://localhost:8000")
    smtp_host: str = os.environ.get("IFINMAIL_SMTP_HOST", "")
    smtp_port: int = int(os.environ.get("IFINMAIL_SMTP_PORT", "587"))
    smtp_tls: bool = os.environ.get("IFINMAIL_SMTP_TLS", "true").lower() == "true"
    smtp_user: str = os.environ.get("IFINMAIL_SMTP_USER", "")
    smtp_password: str = os.environ.get("IFINMAIL_SMTP_PASSWORD", "")
    smtp_timeout: int = int(os.environ.get("IFINMAIL_SMTP_TIMEOUT", "30"))
    attachment_storage: str = os.environ.get(
        "IFINMAIL_ATTACHMENT_STORAGE",
        os.path.expanduser("~/.ifinmail/attachments"),
    )

    def validate(self) -> None:
        env = os.environ.get("IFINMAIL_ENV", "development")
        if env != "production":
            return

        errors: list[str] = []
        if self.secret_key == "dev-secret-key-change-in-production":
            errors.append("IFINMAIL_SECRET_KEY must be changed from the default in production")

        if not self.smtp_host:
            errors.append("IFINMAIL_SMTP_HOST is required in production")

        if not self.smtp_user:
            errors.append("IFINMAIL_SMTP_USER is required in production")

        if not self.smtp_password:
            errors.append("IFINMAIL_SMTP_PASSWORD is required in production")

        if errors:
            print("FATAL: Production configuration errors:", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            sys.exit(1)


settings = Settings()
