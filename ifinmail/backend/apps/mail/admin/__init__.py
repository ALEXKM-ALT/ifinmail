from django.contrib import admin

from ..models import Alias, Mailbox


@admin.register(Mailbox)
class MailboxAdmin(admin.ModelAdmin):
    list_display: list[str] = ["local_part", "domain", "quota_bytes", "created_at"]
    search_fields: list[str] = ["local_part", "domain__name"]
    list_filter: list[str] = ["domain"]


@admin.register(Alias)
class AliasAdmin(admin.ModelAdmin):
    list_display: list[str] = ["source", "destination", "domain"]
    search_fields: list[str] = ["source", "destination", "domain__name"]
    list_filter: list[str] = ["domain"]
