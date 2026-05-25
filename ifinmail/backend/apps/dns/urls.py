from django.urls import path

from .views import dns_config_page, dns_configure, dns_status

app_name = "dns"

urlpatterns = [
    path("", dns_config_page, name="config"),
    path("configure/", dns_configure, name="configure"),
    path("status/", dns_status, name="status"),
]
