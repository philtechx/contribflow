from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .services.membership_permissions import can_manage_memberships
from django.db import IntegrityError
from django.shortcuts import redirect, render
from apps.groups.models import Group

from .forms import MembershipForm
from .models import Membership
from .services.membership_service import create_membership


@login_required
def membership_list(request):
    if request.user.is_superuser:
        memberships = (
            Membership.objects
            .select_related("user", "group")
            .all()
        )
    else:
        manageable_group_ids = (
            Membership.objects
            .filter(
                user=request.user,
                role__in=[
                    Membership.Role.ADMIN,
                    Membership.Role.CHAIRMAN,
                ],
                status=Membership.Status.ACTIVE,
            )
            .values_list("group_id", flat=True)
        )

        if not manageable_group_ids:
            raise PermissionDenied

        memberships = (
            Membership.objects
            .select_related("user", "group")
            .filter(group_id__in=manageable_group_ids)
        )

    return render(
        request,
        "memberships/list.html",
        {
            "memberships": memberships,
        },
    )


@login_required
def membership_create(request):

    if request.method == "POST":

        group_id = request.POST.get("group")

        if not group_id:
            form = MembershipForm(
                request.POST,
                user=request.user,
            )

        else:
            try:
                group = Group.objects.get(
                    pk=group_id,
                    is_active=True,
                )
            except Group.DoesNotExist:
                raise PermissionDenied

            if not can_manage_memberships(
                request.user,
                group,
            ):
                raise PermissionDenied

            form = MembershipForm(
                request.POST,
                user=request.user,
            )

            if form.is_valid():

                try:
                    membership = create_membership(
                        user=form.cleaned_data["user"],
                        group=group,
                        role=form.cleaned_data["role"],
                        status=form.cleaned_data["status"],
                        notes=form.cleaned_data["notes"],
                    )

                except ValueError as error:
                    form.add_error(
                        None,
                        str(error),
                    )

                except IntegrityError:
                    form.add_error(
                        None,
                        "Unable to create membership. "
                        "Please try again.",
                    )

                else:
                    messages.success(
                        request,
                        (
                            "Membership created successfully. "
                            f"Membership number: "
                            f"{membership.membership_number}"
                        ),
                    )

                    return redirect(
                        "memberships:list"
                    )

    else:
        form = MembershipForm(
            user=request.user,
        )

    return render(
        request,
        "memberships/form.html",
        {
            "form": form,
        },
    )