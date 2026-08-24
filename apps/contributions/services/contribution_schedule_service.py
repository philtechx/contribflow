from django.db import transaction

from apps.memberships.models import Membership

from ..models import (
    ContributionSchedule,
    ContributionType,
)


@transaction.atomic
def generate_monthly_schedules(period):
    """
    Generate contribution schedules for all active memberships
    and all active contribution types for a given month.
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