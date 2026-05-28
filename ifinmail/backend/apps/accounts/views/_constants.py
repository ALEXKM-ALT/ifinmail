"""Module-level constants for accounts views."""
import os
import re

_IPIFY_URL = "https://api.ipify.org"
_LETSENCRYPT_DIR = os.environ.get("LETSENCRYPT_DIR", "/etc/letsencrypt")
_MAIL_VHOSTS_DIR = os.environ.get("MAIL_VHOSTS_DIR", "/var/mail/vhosts")
_APP_DIR = os.environ.get("APP_DIR", "/app")

# Domain name validation regex (RFC 952 / RFC 1123)
_DOMAIN_RE = re.compile(
    r"^(?!-)[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.?$"
)
_ALLOWED_HOST_NAMES = tuple(
    h.strip() for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h.strip()
)
