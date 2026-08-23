from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .services.membership_permissions import can_manage_memberships
from django.db import IntegrityError, models
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
            .filter(
                group_id__in=manageable_group_ids,
            )
        )

    # Search
    search = request.GET.get("q", "").strip()

    if search:
        memberships = memberships.filter(
            models.Q(
                membership_number__icontains=search
            )
            | models.Q(
                user__email__icontains=search
            )
            | models.Q(
                user__first_name__icontains=search
            )
            | models.Q(
                user__last_name__icontains=search
            )
        )

    # Filter by status
    status = request.GET.get("status", "").strip()

    if status in dict(Membership.Status.choices):
        memberships = memberships.filter(
            status=status
        )

    # Filter by role
    role = request.GET.get("role", "").strip()

    if role in dict(Membership.Role.choices):
        memberships = memberships.filter(
            role=role
        )

    memberships = memberships.order_by("-joined_at")

    return render(
        request,
        "memberships/list.html",
        {
            "memberships": memberships,
            "search": search,
            "selected_status": status,
            "selected_role": role,
            "status_choices": Membership.Status.choices,
            "role_choices": Membership.Role.choices,
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


@login_required
def membership_detail(request, pk):
    try:
        membership = (
            Membership.objects
            .select_related("user", "group")
            .get(pk=pk)
        )
    except Membership.DoesNotExist:
        raise PermissionDenied

    if not can_manage_memberships(
        request.user,
        membership.group,
    ):
        raise PermissionDenied

    return render(
        request,
        "memberships/detail.html",
        {
            "membership": membership,
        },
    )

@login_required
def membership_update(request, pk):
    try:
        membership = (
            Membership.objects
            .select_related("user", "group")
            .get(pk=pk)
        )
    except Membership.DoesNotExist:
        raise PermissionDenied

    # User must be allowed to manage the membership's
    # current group.
    if not can_manage_memberships(
        request.user,
        membership.group,
    ):
        raise PermissionDenied

    if request.method == "POST":

        group_id = request.POST.get("group")

        if not group_id:
            raise PermissionDenied

        try:
            new_group = Group.objects.get(
                pk=group_id,
                is_active=True,
            )
        except Group.DoesNotExist:
            raise PermissionDenied

        # IMPORTANT:
        # Check permission for the NEW group as well.
        #
        # This prevents an Admin/Chairman of Group A
        # from moving a membership into Group B.
        if not can_manage_memberships(
            request.user,
            new_group,
        ):
            raise PermissionDenied

        form = MembershipForm(
            request.POST,
            instance=membership,
            user=request.user,
        )

        if form.is_valid():

            # Extra protection:
            # Make sure the group selected in the form
            # is exactly the group we already authorized.
            if form.cleaned_data["group"] != new_group:
                raise PermissionDenied

            form.save()

            messages.success(
                request,
                "Membership updated successfully.",
            )

            return redirect(
                "memberships:detail",
                pk=membership.pk,
            )

    else:
        form = MembershipForm(
            instance=membership,
            user=request.user,
        )

    return render(
        request,
        "memberships/form.html",
        {
            "form": form,
            "membership": membership,
            "is_update": True,
        },
    )