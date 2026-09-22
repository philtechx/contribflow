from django.db import transaction

from apps.memberships.models import Membership

from ..models import (
    ContributionSchedule,
    ContributionType,
)


@transaction.atomic
def generate_monthly_schedules(period, group=None):
    """
    Generate contribution schedules for active memberships.

    If a group is provided, schedules are generated only for
    active memberships belonging to that group.

    If no group is provided, schedules are generated for all
    active memberships. This preserves the existing service
    behavior for existing callers.
    """

    period = period.replace(day=1)

    memberships = (
        Membership.objects
        .filter(
            status=Membership.Status.ACTIVE,
            user__is_active=True,
            group__is_active=True,
        )
        .select_related("user", "group")
    )

    # ---------------------------------------------------------
    # Security: restrict generation to the selected group
    # ---------------------------------------------------------
    if group is not None:
        memberships = memberships.filter(
            group=group,
        )

    contribution_types = (
        ContributionType.objects
        .filter(
            status=ContributionType.Status.ACTIVE,
        )
    )

    schedules = []

    for membership in memberships:

        for contribution_type in contribution_types:

            schedule, created = (
                ContributionSchedule.objects.get_or_create(
                    membership=membership,
                    contribution_type=contribution_type,
                    period=period,
                    defaults={
                        "expected_amount": (
                            contribution_type.amount
                        ),
                    },
                )
            )

            if created:
                schedules.append(schedule)

    return schedules