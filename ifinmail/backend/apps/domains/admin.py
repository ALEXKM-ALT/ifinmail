from django.contrib import admin

from .models import DKIMKey, Domain


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ["name", "verified", "mx_verified", "spf_verified", "dkim_verified", "dmarc_verified"]
    list_filter = ["verified", "mx_verified", "spf_verified", "dkim_verified", "dmarc_verified"]
    search_fields = ["name"]
    ordering = ["name"]


@admin.register(DKIMKey)
class DKIMKeyAdmin(admin.ModelAdmin):
    list_display = ["domain", "selector", "active", "created_at"]
    list_filter = ["active"]
    search_fields = ["domain__name", "selector"]
