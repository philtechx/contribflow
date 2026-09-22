from decimal import Decimal

from django import forms

from .models import (
    ContributionCategory,
    ContributionPayment,
    ContributionSchedule,
    ContributionType,
)
from .services.contribution_payment_service import (
    calculate_remaining_balance,
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

    def __init__(
        self,
        *args,
        schedule=None,
        payment=None,
        **kwargs,
    ):
        super().__init__(
            *args,
            **kwargs,
        )

        self.schedule = schedule

        # If editing, store the current payment.
        # If creating, this remains None.
        self.payment = payment

    def clean_amount(self):

        amount = self.cleaned_data.get(
            "amount"
        )

        if amount is None:
            return amount

        amount = Decimal(
            str(amount)
        )

        # -------------------------------------------------
        # Validate positive amount
        # -------------------------------------------------

        if amount <= Decimal("0.00"):
            raise forms.ValidationError(
                "Payment amount must be greater than zero."
            )

        # -------------------------------------------------
        # Schedule is required
        # -------------------------------------------------

        if self.schedule is None:
            raise forms.ValidationError(
                "Contribution schedule is required."
            )

        # -------------------------------------------------
        # Waived schedules cannot receive payments
        # -------------------------------------------------

        if (
            self.schedule.status
            == ContributionSchedule.Status.WAIVED
        ):
            raise forms.ValidationError(
                "A waived contribution schedule cannot receive payment."
            )

        # -------------------------------------------------
        # Get all payments for this schedule
        # -------------------------------------------------

        payments = ContributionPayment.objects.filter(
            schedule=self.schedule
        )

        # -------------------------------------------------
        # When editing, exclude the current payment
        # -------------------------------------------------

        if self.payment is not None:
            payments = payments.exclude(
                pk=self.payment.pk
            )

        # -------------------------------------------------
        # Calculate total of other payments
        # -------------------------------------------------

        total_other_payments = Decimal("0.00")

        for payment in payments:
            total_other_payments += Decimal(
                str(payment.amount)
            )

        # -------------------------------------------------
        # Calculate maximum amount allowed
        # -------------------------------------------------

        expected_amount = Decimal(
            str(self.schedule.expected_amount)
        )

        remaining_balance = (
            expected_amount
            - total_other_payments
        )

        if remaining_balance < Decimal("0.00"):
            remaining_balance = Decimal("0.00")

        # -------------------------------------------------
        # Prevent overpayment
        # -------------------------------------------------

        if amount > remaining_balance:
            raise forms.ValidationError(
                (
                    "Payment amount cannot exceed the "
                    f"remaining balance of "
                    f"{remaining_balance:.2f}."
                )
            )

        return amount


class ContributionWaiverForm(forms.Form):

    reason = forms.CharField(
        label="Waiver Reason",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": (
                    "Enter the reason for waiving this contribution..."
                ),
            }
        ),
        max_length=1000,
    )

    def clean_reason(self):
        reason = self.cleaned_data["reason"].strip()

        if not reason:
            raise forms.ValidationError(
                "A reason is required."
            )

        return reason