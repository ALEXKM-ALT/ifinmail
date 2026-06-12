import os
import sys
from pathlib import Path


def _load_dotenv() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        env_path = Path(os.path.expanduser("~/.ifinmail/.env"))
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip("\"'")
                if not os.environ.get(key):
                    os.environ.setdefault(key, val)


class Settings:
    def __init__(self) -> None:
        _load_dotenv()

        self.database_url: str = os.environ.get(
            "IFINMAIL_DATABASE_URL",
            "sqlite:////home/alex/.ifinmail/admin.db",
        )
        self.redis_url: str = os.environ.get(
            "IFINMAIL_REDIS_URL",
            "redis://localhost:6379/0",
        )
        self.secret_key: str = os.environ.get(
            "IFINMAIL_SECRET_KEY",
            "dev-secret-key-change-in-production",
        )
        self.access_token_expire_minutes: int = int(os.environ.get("IFINMAIL_ACCESS_TOKEN_EXPIRE", "1440"))
        self.refresh_token_expire_days: int = int(os.environ.get("IFINMAIL_REFRESH_TOKEN_EXPIRE", "7"))
        self.algorithm: str = "HS256"
        self.default_domain: str = os.environ.get(
            "IFINMAIL_DEFAULT_DOMAIN",
            "ifinmail.local",
        )
        self.app_url: str = os.environ.get("IFINMAIL_APP_URL", "http://localhost:8000")
        self.smtp_host: str = os.environ.get("IFINMAIL_SMTP_HOST", "")
        self.smtp_port: int = int(os.environ.get("IFINMAIL_SMTP_PORT", "587"))
        self.smtp_tls: bool = os.environ.get("IFINMAIL_SMTP_TLS", "true").lower() == "true"
        self.smtp_user: str = os.environ.get("IFINMAIL_SMTP_USER", "")
        self.smtp_password: str = os.environ.get("IFINMAIL_SMTP_PASSWORD", "")
        self.smtp_timeout: int = int(os.environ.get("IFINMAIL_SMTP_TIMEOUT", "30"))
        self.attachment_storage: str = os.environ.get(
            "IFINMAIL_ATTACHMENT_STORAGE",
            os.path.expanduser("~/.ifinmail/attachments"),
        )
        self.openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")
        self.openai_model: str = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self.sso_google_client_id: str = os.environ.get("SSO_GOOGLE_CLIENT_ID", "")
        self.sso_google_client_secret: str = os.environ.get("SSO_GOOGLE_CLIENT_SECRET", "")
        self.sso_microsoft_client_id: str = os.environ.get("SSO_MICROSOFT_CLIENT_ID", "")
        self.sso_microsoft_client_secret: str = os.environ.get("SSO_MICROSOFT_CLIENT_SECRET", "")
        self.mpesa_consumer_key: str = os.environ.get("MPESA_CONSUMER_KEY", "")
        self.mpesa_consumer_secret: str = os.environ.get("MPESA_CONSUMER_SECRET", "")
        self.mpesa_passkey: str = os.environ.get("MPESA_PASSKEY", "")
        self.mpesa_shortcode: str = os.environ.get("MPESA_SHORTCODE", "")
        self.mpesa_environment: str = os.environ.get("MPESA_ENVIRONMENT", "sandbox")
        self.env: str = os.environ.get("IFINMAIL_ENV", "development")

    def _is_default_secret(self) -> bool:
        defaults = [
            "dev-secret-key-change-in-production",
            "change-me-to-a-long-random-string",
            "change-me",
        ]
        return self.secret_key in defaults

    def validate(self) -> None:
        errors: list[str] = []

        if self.env == "production":
            if self._is_default_secret():
                errors.append("IFINMAIL_SECRET_KEY must be changed from the default in production")
            if not self.smtp_host:
                errors.append("IFINMAIL_SMTP_HOST is required in production")
            if not self.smtp_user:
                errors.append("IFINMAIL_SMTP_USER is required in production")
            if not self.smtp_password:
                errors.append("IFINMAIL_SMTP_PASSWORD is required in production")
            if not self.database_url.startswith("postgresql"):
                errors.append("IFINMAIL_DATABASE_URL must use PostgreSQL in production")
            if self.redis_url == "redis://localhost:6379/0":
                errors.append("IFINMAIL_REDIS_URL should point to a managed Redis in production")

        if self._is_default_secret():
            import logging

            logging.warning("WARNING: IFINMAIL_SECRET_KEY is using a default value. Set a secure secret in production.")

        if self.database_url.startswith("sqlite"):
            if self.env == "production":
                errors.append("SQLite is not suitable for production. Use PostgreSQL.")

        if errors:
            print("FATAL: Configuration errors:", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
            sys.exit(1)


settings = Settings()
