from django.contrib import admin

from .models import Group


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "phone",
        "email",
        "city",
        "country",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
        "country",
        "city",
    )

    search_fields = (
        "name",
        "code",
        "phone",
        "email",
        "tin",
        "registration_number",
    )

    readonly_fields = (
        "id",
        "code",
        "created_at",
        "updated_at",
    )

    ordering = (
        "name",
    )