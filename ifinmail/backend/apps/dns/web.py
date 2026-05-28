"""dns — web.py: re-export layer for web-flow views (urls.py → web.py → views/)."""
from .views import (
    dns_config_page,
    dns_export_records,
    dns_register_domain,
    dns_set_hop_count,
    dns_toggle_proxy,
    dns_toggle_relay,
)

__all__ = [
    "dns_config_page",
    "dns_export_records",
    "dns_register_domain",
    "dns_set_hop_count",
    "dns_toggle_proxy",
    "dns_toggle_relay",
]
