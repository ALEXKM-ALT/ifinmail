"""Domain management service layer."""
import logging

from django.db import transaction
from django.db.utils import OperationalError

from .models import DKIMKey, Domain

logger = logging.getLogger("backend")

# EC-20: Maximum allowed domain name length (RFC 1035)
_MAX_DOMAIN_NAME_LENGTH = 254
_MAX_EMAIL_LENGTH = 254


class DomainService:
    @staticmethod
    def get_all_domains():
        return Domain.objects.order_by("name")

    @staticmethod
    def get_domain_by_name(name: str):
        # EC-20: Validate input length before DB query
        if name and len(name) > _MAX_DOMAIN_NAME_LENGTH:
            logger.warning("Domain name too long (%d chars): %s...", len(name), name[:50])
            return None
        try:
            return Domain.objects.get(name=name)
        except Domain.DoesNotExist:
            return None

    @staticmethod
    def get_domain_stats():
        try:
            with transaction.atomic():
                return {
                    "total": Domain.objects.count(),
                    "verified": Domain.objects.filter(verified=True).count(),
                    "mx_ok": Domain.objects.filter(mx_verified=True).count(),
                    "spf_ok": Domain.objects.filter(spf_verified=True).count(),
                    "dkim_ok": Domain.objects.filter(dkim_verified=True).count(),
                    "dmarc_ok": Domain.objects.filter(dmarc_verified=True).count(),
                }
        except OperationalError:
            logger.exception("Failed to fetch domain stats")
            return None

    @staticmethod
    def get_dkim_keys(domain_name: str):
        # EC-20: Validate input length before DB query
        if domain_name and len(domain_name) > _MAX_DOMAIN_NAME_LENGTH:
            return []
        domain = DomainService.get_domain_by_name(domain_name)
        if domain is None:
            return []
        return DKIMKey.objects.filter(domain=domain, active=True)

    @staticmethod
    def create_domain(name: str):
        # EC-20: Validate input length
        if not name or len(name) > _MAX_DOMAIN_NAME_LENGTH:
            raise ValueError(f"Domain name must be 1-{_MAX_DOMAIN_NAME_LENGTH} characters")
        return Domain.objects.create(name=name)

    @staticmethod
    def delete_domain(domain_name: str):
        """Delete a domain and cascade all related records.
        EC-18: Wrapped in transaction.atomic() for atomicity.
        """
        # EC-20: Validate input length
        if domain_name and len(domain_name) > _MAX_DOMAIN_NAME_LENGTH:
            raise ValueError(f"Domain name too long ({len(domain_name)} chars)")
        with transaction.atomic():
            try:
                domain = Domain.objects.get(name=domain_name)
            except Domain.DoesNotExist:
                return False
            domain.delete()
            return True
