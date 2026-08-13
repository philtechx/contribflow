import uuid

from django.conf import settings
from django.db import models


class Membership(models.Model):

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        CHAIRMAN = "chairman", "Chairman"
        SECRETARY = "secretary", "Secretary"
        TREASURER = "treasurer", "Treasurer"
        MEMBER = "member", "Member"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        SUSPENDED = "suspended", "Suspended"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    group = models.ForeignKey(
        "groups.Group",
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    membership_number = models.CharField(
        max_length=50,
    )

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.MEMBER,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    joined_at = models.DateField(
        auto_now_add=True,
    )

    notes = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "group"],
                name="unique_user_group_membership",
            ),
            models.UniqueConstraint(
                fields=["group", "membership_number"],
                name="unique_group_membership_number",
            ),
        ]

    def __str__(self):
        return f"{self.membership_number} - {self.user.email}"