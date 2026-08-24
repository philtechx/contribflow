from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.contributions.models import (
    ContributionPayment,
    ContributionSchedule,
)


def calculate_total_paid(schedule):
    """
    Return the total amount paid for a contribution schedule.
    """
    total = (
        ContributionPayment.objects
        .filter(schedule=schedule)
        .aggregate(total=Sum("amount"))
        .get("total")
    )

    return total or Decimal("0.00")


def calculate_remaining_balance(schedule):
    """
    Return the remaining balance for a contribution schedule.
    """
    expected_amount = Decimal(str(schedule.expected_amount))
    total_paid = calculate_total_paid(schedule)

    remaining = expected_amount - total_paid

    if remaining < Decimal("0.00"):
        return Decimal("0.00")

    return remaining


@transaction.atomic
def create_payment(
    *,
    schedule,
    amount,
    payment_date=None,
    payment_method="cash",
    reference="",
    notes="",
):
    """
    Create a contribution payment and update the schedule status.

    Business rules:
    - Payment amount must be greater than zero.
    - Waived schedules cannot receive payments.
    - Payment cannot exceed the remaining balance.
    - Multiple payments are supported.
    - Schedule status is updated automatically.
    """

    # ---------------------------------------------------------
    # Normalize values
    # ---------------------------------------------------------
    amount = Decimal(str(amount))

    if payment_date is None:
        payment_date = timezone.now().date()

    payment_method = payment_method or "cash"
    reference = reference or ""
    notes = notes or ""

    # ---------------------------------------------------------
    # Validate amount
    # ---------------------------------------------------------
    if amount <= Decimal("0.00"):
        raise ValueError(
            "Payment amount must be greater than zero."
        )

    # ---------------------------------------------------------
    # Validate waived schedule
    # ---------------------------------------------------------
    if schedule.status == ContributionSchedule.Status.WAIVED:
        raise ValueError(
            "A waived contribution schedule cannot receive payment."
        )

    # ---------------------------------------------------------
    # Calculate current totals
    # ---------------------------------------------------------
    total_paid = calculate_total_paid(schedule)
    remaining_balance = calculate_remaining_balance(schedule)

    # ---------------------------------------------------------
    # Validate remaining balance
    # ---------------------------------------------------------
    if amount > remaining_balance:
        raise ValueError(
            "Payment amount cannot exceed the remaining balance."
        )

    # ---------------------------------------------------------
    # Create payment
    # ---------------------------------------------------------
    payment = ContributionPayment.objects.create(
        schedule=schedule,
        amount=amount,
        payment_date=payment_date,
        payment_method=payment_method,
        reference=reference,
        notes=notes,
    )

    # ---------------------------------------------------------
    # Calculate new balance
    # ---------------------------------------------------------
    new_total_paid = total_paid + amount
    expected_amount = Decimal(str(schedule.expected_amount))

    new_remaining_balance = (
        expected_amount - new_total_paid
    )

    if new_remaining_balance < Decimal("0.00"):
        new_remaining_balance = Decimal("0.00")

    # ---------------------------------------------------------
    # Update schedule status
    # ---------------------------------------------------------
    if new_remaining_balance == Decimal("0.00"):
        schedule.status = ContributionSchedule.Status.PAID

    elif new_total_paid > Decimal("0.00"):
        schedule.status = ContributionSchedule.Status.PARTIAL

    else:
        schedule.status = ContributionSchedule.Status.PENDING

    schedule.save(
        update_fields=["status", "updated_at"]
    )

    return payment

