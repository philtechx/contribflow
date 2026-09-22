from django.db import transaction
from decimal import Decimal
from django.db.models import Sum
from django.utils import timezone

from apps.contributions.models import (
    ContributionSchedule,
    ContributionWaiver,
)


@transaction.atomic
def waive_contribution(
    *,
    schedule,
    waived_by,
    reason,
):
    """
    Waive a contribution schedule.

    Business rules:
    - Schedule must not already be waived.
    - Schedule must not be fully paid.
    - A reason is required.
    - The user performing the waiver is recorded.
    - A waiver history record is created.
    """

    if schedule.status == ContributionSchedule.Status.WAIVED:
        raise ValueError(
            "This contribution schedule is already waived."
        )

    if schedule.status == ContributionSchedule.Status.PAID:
        raise ValueError(
            "A fully paid contribution cannot be waived."
        )

    reason = (reason or "").strip()

    if not reason:
        raise ValueError(
            "A reason is required when waiving a contribution."
        )

    schedule.status = (
        ContributionSchedule.Status.WAIVED
    )

    schedule.waived_by = waived_by
    schedule.waived_at = timezone.now()
    schedule.waived_reason = reason

    schedule.save(
        update_fields=[
            "status",
            "waived_by",
            "waived_at",
            "waived_reason",
            "updated_at",
        ]
    )

    ContributionWaiver.objects.create(
        schedule=schedule,
        action=ContributionWaiver.Action.WAIVED,
        reason=reason,
        performed_by=waived_by,
    )

    return schedule


@transaction.atomic
def restore_contribution(
    *,
    schedule,
    restored_by,
    reason,
):
    """
    Restore a waived contribution schedule.

    Business rules:
    - Schedule must currently be waived.
    - A reason is required.
    - Status is recalculated from existing payments.
    - A restore history record is created.
    """

    if schedule.status != ContributionSchedule.Status.WAIVED:
        raise ValueError(
            "Only a waived contribution can be restored."
        )

    reason = (reason or "").strip()

    if not reason:
        raise ValueError(
            "A reason is required when restoring a contribution."
        )

    total_paid = (
        schedule.payments.aggregate(
            total=Sum("amount")
        ).get("total")
        or Decimal("0.00")
    )

    total_paid = Decimal(str(total_paid))
    expected_amount = Decimal(
        str(schedule.expected_amount)
    )

    if total_paid == Decimal("0.00"):
        new_status = ContributionSchedule.Status.PENDING

    elif total_paid < expected_amount:
        new_status = ContributionSchedule.Status.PARTIAL

    else:
        new_status = ContributionSchedule.Status.PAID

    schedule.status = new_status

    schedule.save(
        update_fields=[
            "status",
            "updated_at",
        ]
    )

    ContributionWaiver.objects.create(
        schedule=schedule,
        action=ContributionWaiver.Action.RESTORED,
        reason=reason,
        performed_by=restored_by,
    )

    return schedule



