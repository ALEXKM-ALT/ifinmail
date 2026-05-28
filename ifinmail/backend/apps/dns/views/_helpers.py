"""Shared helpers for DNS views — re-exports from DNS service layer."""
from backend.apps.dns.services import PROVIDER_MAP, DNSService

build_records = DNSService.build_records
get_server_ip = DNSService.get_server_ip
get_provider = DNSService.get_provider

# Maintain backward-compatible private aliases for internal DNS view imports
_build_records = build_records
_get_server_ip = get_server_ip
_get_provider = get_provider


def _is_staff(user: object) -> bool:
    return user.is_authenticated and (user.is_staff or user.is_superuser)
