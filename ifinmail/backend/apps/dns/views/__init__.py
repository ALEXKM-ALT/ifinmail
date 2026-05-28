"""dns views package — re-exports all public view functions."""
from .api import dns_configure, dns_status
from .web import (
    dns_config_page,
    dns_export_records,
    dns_register_domain,
    dns_set_hop_count,
    dns_toggle_proxy,
    dns_toggle_relay,
)

__all__ = [
    "dns_config_page",
    "dns_configure",
    "dns_export_records",
    "dns_register_domain",
    "dns_set_hop_count",
    "dns_status",
    "dns_toggle_proxy",
    "dns_toggle_relay",
]
