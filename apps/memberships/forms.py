from django import forms

from apps.accounts.models import User
from apps.groups.models import Group

from .models import Membership


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["user"].queryset = User.objects.filter(
            is_active=True
        )

        self.fields["group"].queryset = Group.objects.filter(
            is_active=True
        )