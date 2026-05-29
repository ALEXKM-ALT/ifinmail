from django.urls import path

from .api import dns_configure, dns_status  # API flow (JSON endpoints)
from .web import (  # web flow (template-rendering)
    dns_config_page,
    dns_export_records,
    dns_register_domain,
    dns_set_hop_count,
    dns_toggle_proxy,
    dns_toggle_relay,
)

app_name = 'dns'

urlpatterns = [
    path('', dns_config_page, name='config'),
    path('configure/', dns_configure, name='configure'),
    path('status/', dns_status, name='status'),
    path('register/', dns_register_domain, name='register'),
    path('export/', dns_export_records, name='export'),
    path('toggle-proxy/', dns_toggle_proxy, name='toggle_proxy'),
    path('toggle-relay/', dns_toggle_relay, name='toggle_relay'),
    path('set-hop-count/', dns_set_hop_count, name='set_hop_count'),
]
