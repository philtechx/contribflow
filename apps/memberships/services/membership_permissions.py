from apps.memberships.models import Membership


def can_manage_memberships(user, group):
    """
    Return True when the user is allowed to manage
    memberships belonging to the given group.
    """

    if not user or not user.is_authenticated:
        return False

    # System-level administrators can manage all groups.
    if user.is_superuser:
        return True

    return Membership.objects.filter(
        user=user,
        group=group,
        role__in=[
            Membership.Role.ADMIN,
            Membership.Role.CHAIRMAN,
        ],
        status=Membership.Status.ACTIVE,
    ).exists()