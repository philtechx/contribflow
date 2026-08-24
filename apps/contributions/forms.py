from decimal import Decimal

from django import forms
from django.db.models import Sum

from .models import (
    ContributionCategory,
    ContributionPayment,
    ContributionSchedule,
    ContributionType,
)


class ContributionCategoryForm(forms.ModelForm):

    class Meta:
        model = ContributionCategory
        fields = [
            "name",
        ]

        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Contribution category name",
                }
            ),
        }


class ContributionTypeForm(forms.ModelForm):

    class Meta:
        model = ContributionType
        fields = [
            "category",
            "name",
            "description",
            "amount",
            "status",
        ]

        widgets = {
            "category": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Contribution type name",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Description",
                }
            ),
            "amount": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "0.00",
                }
            ),
            "status": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
        }


class ScheduleGenerationForm(forms.Form):

    month = forms.DateField(
        input_formats=["%Y-%m"],
        widget=forms.DateInput(
            format="%Y-%m",
            attrs={
                "class": "form-control",
                "type": "month",
            },
        ),
    )

    def clean_month(self):
        month = self.cleaned_data["month"]

        return month.replace(day=1)


class ContributionPaymentForm(forms.ModelForm):

    class Meta:
        model = ContributionPayment
        fields = [
            "amount",
            "payment_date",
            "payment_method",
            "reference",
            "notes",
        ]

        widgets = {
            "amount": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0.01",
                    "placeholder": "0.00",
                }
            ),
            "payment_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={
                    "class": "form-control",
                    "type": "date",
                },
            ),
            "payment_method": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "reference": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. MPESA123456",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Additional notes...",
                }
            ),
        }

    def __init__(self, *args, schedule=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.schedule = schedule

    def clean_amount(self):
        amount = self.cleaned_data.get("amount")

        if amount is None:
            return amount

        if amount <= Decimal("0.00"):
            raise forms.ValidationError(
                "Payment amount must be greater than zero."
            )

        if self.schedule is None:
            return amount

        if self.schedule.status == ContributionSchedule.Status.WAIVED:
            raise forms.ValidationError(
                "A waived contribution schedule cannot receive payment."
            )

        total_paid = (
            ContributionPayment.objects
            .filter(schedule=self.schedule)
            .aggregate(total=Sum("amount"))
            .get("total")
            or Decimal("0.00")
        )

        total_paid = Decimal(str(total_paid))

        remaining_balance = (
            Decimal(str(self.schedule.expected_amount))
            - total_paid
        )

        if remaining_balance < Decimal("0.00"):
            remaining_balance = Decimal("0.00")

        if amount > remaining_balance:
            raise forms.ValidationError(
                (
                    "Payment amount cannot exceed the remaining "
                    f"balance of {remaining_balance:.2f}."
                )
            )

        return amount