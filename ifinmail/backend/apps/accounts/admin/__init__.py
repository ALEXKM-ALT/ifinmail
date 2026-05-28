from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from ..models import MailUser


@admin.register(MailUser)
class MailUserAdmin(BaseUserAdmin):
    list_display: list[str] = ["email", "is_active", "is_staff", "created_at"]
    list_filter: list[str] = ["is_active", "is_staff", "is_superuser"]
    search_fields: list[str] = ["email"]
    ordering: list[str] = ["email"]
    filter_horizontal: list[str] = []
    fieldsets: tuple = (
        (None, {"fields": ("email", "password")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser")}),
        ("Dates", {"fields": ("created_at",)}),
    )
    add_fieldsets: tuple = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2"),
        }),
    )
    readonly_fields: list[str] = ["created_at"]
