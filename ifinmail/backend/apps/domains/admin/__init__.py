from django.contrib import admin

from ..models import DKIMKey, Domain


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display: list[str] = ["name", "verified", "mx_verified", "spf_verified", "dkim_verified", "dmarc_verified"]
    list_filter: list[str] = ["verified", "mx_verified", "spf_verified", "dkim_verified", "dmarc_verified"]
    search_fields: list[str] = ["name"]
    ordering: list[str] = ["name"]


@admin.register(DKIMKey)
class DKIMKeyAdmin(admin.ModelAdmin):
    list_display: list[str] = ["domain", "selector", "active", "created_at"]
    list_filter: list[str] = ["active"]
    search_fields: list[str] = ["domain__name", "selector"]
