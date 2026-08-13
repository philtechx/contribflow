from django.contrib import admin

from .models import Membership


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = (
        "membership_number",
        "user",
        "group",
        "role",
        "status",
        "joined_at",
    )

    list_filter = (
        "role",
        "status",
        "group",
    )

    search_fields = (
        "membership_number",
        "user__email",
        "user__first_name",
        "user__last_name",
        "group__name",
    )

    readonly_fields = (
        "id",
        "joined_at",
        "created_at",
        "updated_at",
    )

    autocomplete_fields = (
        "user",
        "group",
    )

    ordering = (
        "group",
        "membership_number",
    )