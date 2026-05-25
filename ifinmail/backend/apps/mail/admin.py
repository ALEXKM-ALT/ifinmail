from django.contrib import admin

from .models import Alias, Mailbox


@admin.register(Mailbox)
class MailboxAdmin(admin.ModelAdmin):
    list_display = ["local_part", "domain", "quota_bytes", "created_at"]
    search_fields = ["local_part", "domain__name"]
    list_filter = ["domain"]


@admin.register(Alias)
class AliasAdmin(admin.ModelAdmin):
    list_display = ["source", "destination", "domain"]
    search_fields = ["source", "destination", "domain__name"]
    list_filter = ["domain"]
