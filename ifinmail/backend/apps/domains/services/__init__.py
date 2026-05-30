"""Domain management service layer."""

import logging

from django.db import transaction
from django.db.models import QuerySet
from django.db.utils import OperationalError

from ..models import DKIMKey, Domain

logger = logging.getLogger('backend')

# EC-20: Maximum allowed domain name length (RFC 1035)
_MAX_DOMAIN_NAME_LENGTH = 254
_MAX_EMAIL_LENGTH = 254


class DomainService:
    @staticmethod
    def get_all_domains() -> QuerySet[Domain]:
        return Domain.objects.order_by('name')

    @staticmethod
    def get_domain_by_name(name: str) -> Domain | None:
        if name and len(name) > _MAX_DOMAIN_NAME_LENGTH:
            logger.warning('Domain name too long (%d chars): %s...', len(name), name[:50])
            return None
        try:
            return Domain.objects.get(name=name)
        except Domain.DoesNotExist:
            return None

    @staticmethod
    def get_domain_count() -> int:
        try:
            return Domain.objects.count()
        except OperationalError:
            return 0

    @staticmethod
    def get_domain_stats() -> dict[str, int] | None:
        try:
            with transaction.atomic():
                return {
                    'total': Domain.objects.count(),
                    'verified': Domain.objects.filter(verified=True).count(),
                    'mx_ok': Domain.objects.filter(mx_verified=True).count(),
                    'spf_ok': Domain.objects.filter(spf_verified=True).count(),
                    'dkim_ok': Domain.objects.filter(dkim_verified=True).count(),
                    'dmarc_ok': Domain.objects.filter(dmarc_verified=True).count(),
                }
        except OperationalError:
            logger.exception('Failed to fetch domain stats')
            return None

    @staticmethod
    def get_domains_paginated(page_number: int, per_page: int = 25) -> tuple[list[Domain], bool]:
        try:
            qs = Domain.objects.order_by('name')
            offset = (page_number - 1) * per_page
            domains = list(qs[offset : offset + per_page])
            has_next = qs[offset + per_page : offset + per_page + 1].exists()
            return domains, has_next
        except OperationalError:
            return [], False

    @staticmethod
    def get_domain_verification_rows(domain_names: list[str]) -> list[tuple]:
        try:
            return list(
                Domain.objects.filter(name__in=domain_names).values_list(
                    'name',
                    'verified',
                    'mx_verified',
                    'spf_verified',
                    'dkim_verified',
                    'dmarc_verified',
                )
            )
        except OperationalError:
            return []

    @staticmethod
    def get_dkim_keys(domain_name: str) -> list[DKIMKey]:
        if domain_name and len(domain_name) > _MAX_DOMAIN_NAME_LENGTH:
            return []
        domain = DomainService.get_domain_by_name(domain_name)
        if domain is None:
            return []
        return list(DKIMKey.objects.filter(domain=domain, active=True))

    @staticmethod
    def create_domain(name: str, ip_address: str | None = None) -> Domain:
        if not name or len(name) > _MAX_DOMAIN_NAME_LENGTH:
            raise ValueError(f'Domain name must be 1-{_MAX_DOMAIN_NAME_LENGTH} characters')
        return Domain.objects.create(name=name, ip_address=ip_address or None)

    @staticmethod
    def get_or_create_domain(
        name: str,
        ip_address: str | None = None,
    ) -> tuple[Domain, bool]:
        try:
            with transaction.atomic():
                domain, created = Domain.objects.get_or_create(name=name)
                if created and ip_address:
                    domain.ip_address = ip_address
                    domain.save(update_fields=['ip_address'])
                return domain, created
        except OperationalError:
            logger.exception('Failed to get_or_create domain %s', name)
            raise

    @staticmethod
    def delete_domain(domain_name: str) -> bool:
        if domain_name and len(domain_name) > _MAX_DOMAIN_NAME_LENGTH:
            raise ValueError(f'Domain name too long ({len(domain_name)} chars)')
        with transaction.atomic():
            try:
                domain = Domain.objects.get(name=domain_name)
            except Domain.DoesNotExist:
                return False
            domain.delete()
            return True
