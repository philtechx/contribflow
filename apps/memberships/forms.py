from django import forms

from apps.accounts.models import User
from apps.groups.models import Group
from apps.memberships.models import Membership


class MembershipForm(forms.ModelForm):

    class Meta:
        model = Membership
        fields = [
            "user",
            "group",
            "role",
            "status",
            "notes",
        ]

        widgets = {
            "user": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "group": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "role": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Optional notes...",
                }
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Only active users can become members.
        self.fields["user"].queryset = User.objects.filter(
            is_active=True
        )

        # Start with no groups.
        # Groups are added only when the current user
        # has permission to manage them.
        self.fields["group"].queryset = Group.objects.none()

        # No authenticated user.
        if not user or not user.is_authenticated:
            return

        # Superusers can manage memberships in all active groups.
        if user.is_superuser:
            self.fields["group"].queryset = Group.objects.filter(
                is_active=True
            )
            return

        # Find groups where the current user has
        # active Admin or Chairman membership.
        manageable_group_ids = (
            Membership.objects
            .filter(
                user=user,
                role__in=[
                    Membership.Role.ADMIN,
                    Membership.Role.CHAIRMAN,
                ],
                status=Membership.Status.ACTIVE,
            )
            .values_list("group_id", flat=True)
        )

        # Only show groups this user is authorized to manage.
        self.fields["group"].queryset = Group.objects.filter(
            id__in=manageable_group_ids,
            is_active=True,
        )