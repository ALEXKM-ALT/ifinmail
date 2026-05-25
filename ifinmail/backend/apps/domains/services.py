"""Domain management service layer."""
import logging

from django.db import transaction
from django.db.utils import OperationalError

from .models import DKIMKey, Domain

logger = logging.getLogger("backend")


class DomainService:
    @staticmethod
    def get_all_domains():
        return Domain.objects.order_by("name")

    @staticmethod
    def get_domain_by_name(name: str):
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
        domain = DomainService.get_domain_by_name(domain_name)
        if domain is None:
            return []
        return DKIMKey.objects.filter(domain=domain, active=True)

    @staticmethod
    def create_domain(name: str):
        return Domain.objects.create(name=name)
