from django.db import transaction

from apps.accounts.models import User
from apps.groups.models import Group

from ..models import Membership


def generate_membership_number(group: Group) -> str:
    """
    Generate the next membership number for a group.

    Example:
        UMJ-0001
        UMJ-0002
        UMJ-0003
    """

    prefix = f"{group.code}-"

    membership_numbers = (
        Membership.objects
        .filter(
            group=group,
            membership_number__startswith=prefix,
        )
        .values_list("membership_number", flat=True)
    )

    numbers = []

    for membership_number in membership_numbers:
        suffix = membership_number[len(prefix):]

        if suffix.isdigit():
            numbers.append(int(suffix))

    next_number = max(numbers, default=0) + 1

    return f"{prefix}{next_number:04d}"


@transaction.atomic
def create_membership(
    *,
    user: User,
    group: Group,
    role: str = Membership.Role.MEMBER,
    status: str = Membership.Status.ACTIVE,
    notes: str = "",
) -> Membership:
    """
    Create a new membership for a user in a group.
    """

    if Membership.objects.filter(
        user=user,
        group=group,
    ).exists():
        raise ValueError(
            "This user is already a member of this group."
        )

    membership_number = generate_membership_number(group)

    return Membership.objects.create(
        user=user,
        group=group,
        membership_number=membership_number,
        role=role,
        status=status,
        notes=notes,
    )