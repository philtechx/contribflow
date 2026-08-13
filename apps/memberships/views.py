from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import redirect, render

from .forms import MembershipForm
from .models import Membership
from .services.membership_service import create_membership


@login_required
def membership_list(request):
    memberships = (
        Membership.objects
        .select_related("user", "group")
        .all()
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
        form = MembershipForm(request.POST)

        if form.is_valid():
            try:
                membership = create_membership(
                    user=form.cleaned_data["user"],
                    group=form.cleaned_data["group"],
                    role=form.cleaned_data["role"],
                    status=form.cleaned_data["status"],
                    notes=form.cleaned_data["notes"],
                )

            except ValueError as error:
                form.add_error(None, str(error))

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

                return redirect("memberships:list")

    else:
        form = MembershipForm()

    return render(
        request,
        "memberships/form.html",
        {
            "form": form,
        },
    )