from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.memberships.models import Membership

from .forms import (
    ContributionPaymentForm,
    ScheduleGenerationForm,
)
from .models import (
    ContributionPayment,
    ContributionSchedule,
    ContributionType,
)
from .services.contribution_payment_service import (
    calculate_remaining_balance,
    calculate_total_paid,
    create_payment,
)
from .services.contribution_schedule_service import (
    generate_monthly_schedules,
)


@login_required
def generate_schedules_view(request):

    if request.method != "POST":
        raise PermissionDenied

    if not request.user.is_superuser:

        can_manage = Membership.objects.filter(
            user=request.user,
            role__in=[
                Membership.Role.ADMIN,
                Membership.Role.CHAIRMAN,
                Membership.Role.TREASURER,
            ],
            status=Membership.Status.ACTIVE,
        ).exists()

        if not can_manage:
            raise PermissionDenied

    form = ScheduleGenerationForm(
        request.POST,
    )

    if not form.is_valid():
        messages.error(
            request,
            "Please select a valid month.",
        )

        return redirect(
            "contributions:dashboard"
        )

    period = form.cleaned_data["month"]

    schedules = generate_monthly_schedules(
        period
    )

    if schedules:

        messages.success(
            request,
            (
                f"{len(schedules)} contribution "
                f"schedule(s) generated successfully."
            ),
        )

    else:

        messages.info(
            request,
            "No new contribution schedules were generated.",
        )

    return redirect(
        "contributions:dashboard"
    )


@login_required
def contribution_dashboard(request):

    if request.user.is_superuser:

        memberships = Membership.objects.filter(
            status=Membership.Status.ACTIVE,
            user__is_active=True,
            group__is_active=True,
        )

    else:

        manageable_group_ids = (
            Membership.objects
            .filter(
                user=request.user,
                role__in=[
                    Membership.Role.ADMIN,
                    Membership.Role.CHAIRMAN,
                    Membership.Role.TREASURER,
                ],
                status=Membership.Status.ACTIVE,
            )
            .values_list(
                "group_id",
                flat=True,
            )
        )

        if not manageable_group_ids:
            raise PermissionDenied

        memberships = Membership.objects.filter(
            group_id__in=manageable_group_ids,
            status=Membership.Status.ACTIVE,
            user__is_active=True,
            group__is_active=True,
        )

    today = timezone.now().date()

    period = today.replace(
        day=1,
    )

    schedules = (
        ContributionSchedule.objects
        .filter(
            membership__in=memberships,
            period=period,
        )
        .select_related(
            "membership",
            "membership__user",
            "membership__group",
            "contribution_type",
        )
        .order_by(
            "membership__user__first_name",
            "membership__user__last_name",
            "contribution_type__name",
        )
    )

    total_expected = (
        schedules.aggregate(
            total=Sum("expected_amount"),
        )["total"]
        or Decimal("0.00")
    )

    pending_count = schedules.filter(
        status=ContributionSchedule.Status.PENDING,
    ).count()

    paid_count = schedules.filter(
        status=ContributionSchedule.Status.PAID,
    ).count()

    contribution_types = ContributionType.objects.filter(
        status=ContributionType.Status.ACTIVE,
    )

    context = {
        "schedules": schedules,
        "period": period,
        "contribution_types": contribution_types,
        "member_count": memberships.count(),
        "schedule_count": schedules.count(),
        "total_expected": total_expected,
        "pending_count": pending_count,
        "paid_count": paid_count,
    }

    return render(
        request,
        "contributions/dashboard.html",
        context,
    )


@login_required
def schedule_list_view(request):

    if request.user.is_superuser:

        memberships = Membership.objects.filter(
            status=Membership.Status.ACTIVE,
            user__is_active=True,
            group__is_active=True,
        )

    else:

        manageable_group_ids = (
            Membership.objects
            .filter(
                user=request.user,
                role__in=[
                    Membership.Role.ADMIN,
                    Membership.Role.CHAIRMAN,
                    Membership.Role.TREASURER,
                ],
                status=Membership.Status.ACTIVE,
            )
            .values_list(
                "group_id",
                flat=True,
            )
        )

        if not manageable_group_ids:
            raise PermissionDenied

        memberships = Membership.objects.filter(
            group_id__in=manageable_group_ids,
            status=Membership.Status.ACTIVE,
            user__is_active=True,
            group__is_active=True,
        )

    month = request.GET.get(
        "month",
        "",
    ).strip()

    if month:

        try:

            period = datetime.strptime(
                month,
                "%Y-%m",
            ).date().replace(
                day=1,
            )

        except ValueError:

            period = timezone.now().date().replace(
                day=1,
            )

    else:

        period = timezone.now().date().replace(
            day=1,
        )

    schedules = (
        ContributionSchedule.objects
        .filter(
            membership__in=memberships,
            period=period,
        )
        .select_related(
            "membership",
            "membership__user",
            "membership__group",
            "contribution_type",
        )
        .order_by(
            "membership__user__first_name",
            "membership__user__last_name",
            "contribution_type__name",
        )
    )

    total_expected = (
        schedules.aggregate(
            total=Sum("expected_amount"),
        )["total"]
        or Decimal("0.00")
    )

    pending_count = schedules.filter(
        status=ContributionSchedule.Status.PENDING,
    ).count()

    partial_count = schedules.filter(
        status=ContributionSchedule.Status.PARTIAL,
    ).count()

    paid_count = schedules.filter(
        status=ContributionSchedule.Status.PAID,
    ).count()

    waived_count = schedules.filter(
        status=ContributionSchedule.Status.WAIVED,
    ).count()

    context = {
        "schedules": schedules,
        "period": period,
        "total_expected": total_expected,
        "pending_count": pending_count,
        "partial_count": partial_count,
        "paid_count": paid_count,
        "waived_count": waived_count,
    }

    return render(
        request,
        "contributions/schedules/list.html",
        context,
    )


@login_required
def create_payment_view(
    request,
    schedule_id,
):
    """
    Create a payment for a contribution schedule.

    Access:
    - Superuser: any active schedule.
    - Group Admin: schedules in their group.
    - Chairman: schedules in their group.
    - Treasurer: schedules in their group.
    """

    schedule = get_object_or_404(
        ContributionSchedule.objects.select_related(
            "membership",
            "membership__user",
            "membership__group",
            "contribution_type",
        ),
        pk=schedule_id,
    )

    # ---------------------------------------------------------
    # Permission check
    # ---------------------------------------------------------

    if request.user.is_superuser:

        allowed = (
            schedule.membership.status
            == Membership.Status.ACTIVE
            and schedule.membership.user.is_active
            and schedule.membership.group.is_active
        )

    else:

        allowed = Membership.objects.filter(
            user=request.user,
            group=schedule.membership.group,
            role__in=[
                Membership.Role.ADMIN,
                Membership.Role.CHAIRMAN,
                Membership.Role.TREASURER,
            ],
            status=Membership.Status.ACTIVE,
        ).exists()

    if not allowed:
        raise PermissionDenied

    # ---------------------------------------------------------
    # Prevent payment on waived schedule
    # ---------------------------------------------------------

    if schedule.status == ContributionSchedule.Status.WAIVED:

        messages.error(
            request,
            "A waived contribution schedule cannot receive payment.",
        )

        return redirect(
            "contributions:schedule-list",
        )

    # ---------------------------------------------------------
    # Handle form
    # ---------------------------------------------------------

    if request.method == "POST":

        form = ContributionPaymentForm(
            request.POST,
            schedule=schedule,
        )

        if form.is_valid():

            try:

                create_payment(
                    schedule=schedule,
                    amount=form.cleaned_data["amount"],
                    payment_date=form.cleaned_data[
                        "payment_date"
                    ],
                    payment_method=form.cleaned_data[
                        "payment_method"
                    ],
                    reference=form.cleaned_data[
                        "reference"
                    ],
                    notes=form.cleaned_data[
                        "notes"
                    ],
                )

            except (ValueError, ValidationError) as exc:

                if hasattr(exc, "message_dict"):

                    form.add_error(
                        None,
                        exc,
                    )

                else:

                    form.add_error(
                        "amount",
                        str(exc),
                    )

            else:

                messages.success(
                    request,
                    "Contribution payment recorded successfully.",
                )

                return redirect(
                    "contributions:schedule-list",
                )

    else:

        form = ContributionPaymentForm(
            schedule=schedule,
        )

    # ---------------------------------------------------------
    # Payment information
    # ---------------------------------------------------------

    total_paid = calculate_total_paid(
        schedule,
    )

    remaining_balance = calculate_remaining_balance(
        schedule,
    )

    context = {
        "form": form,
        "schedule": schedule,
        "total_paid": total_paid,
        "remaining_balance": remaining_balance,
    }

    return render(
        request,
        "contributions/payments/create.html",
        context,
    )



@login_required
def schedule_detail_view(request, schedule_id):
    """
    Display contribution schedule details and payment history.
    """

    schedule = get_object_or_404(
        ContributionSchedule.objects.select_related(
            "membership",
            "membership__user",
            "membership__group",
            "contribution_type",
        ),
        pk=schedule_id,
    )

    # ---------------------------------------------------------
    # Permission check
    # ---------------------------------------------------------
    if request.user.is_superuser:

        allowed = (
            schedule.membership.status
            == Membership.Status.ACTIVE
            and schedule.membership.user.is_active
            and schedule.membership.group.is_active
        )

    else:

        allowed = Membership.objects.filter(
            user=request.user,
            group=schedule.membership.group,
            role__in=[
                Membership.Role.ADMIN,
                Membership.Role.CHAIRMAN,
                Membership.Role.TREASURER,
            ],
            status=Membership.Status.ACTIVE,
        ).exists()

    if not allowed:
        raise PermissionDenied

    # ---------------------------------------------------------
    # Payment history
    # ---------------------------------------------------------
    payments = (
        schedule.payments
        .all()
        .order_by(
            "-payment_date",
            "-created_at",
        )
    )

    # ---------------------------------------------------------
    # Payment summary
    # ---------------------------------------------------------
    from .services.contribution_payment_service import (
        calculate_remaining_balance,
        calculate_total_paid,
    )

    total_paid = calculate_total_paid(
        schedule
    )

    remaining_balance = calculate_remaining_balance(
        schedule
    )

    context = {
        "schedule": schedule,
        "payments": payments,
        "total_paid": total_paid,
        "remaining_balance": remaining_balance,
    }

    return render(
        request,
        "contributions/schedules/detail.html",
        context,
    )


@login_required
def payment_list_view(request, schedule_id):

    schedule = get_object_or_404(
        ContributionSchedule.objects.select_related(
            "membership",
            "membership__user",
            "membership__group",
            "contribution_type",
        ),
        pk=schedule_id,
    )

    # ---------------------------------------------------------
    # Permission check
    # ---------------------------------------------------------
    if request.user.is_superuser:

        allowed = (
            schedule.membership.status
            == Membership.Status.ACTIVE
            and schedule.membership.user.is_active
            and schedule.membership.group.is_active
        )

    else:

        allowed = Membership.objects.filter(
            user=request.user,
            group=schedule.membership.group,
            role__in=[
                Membership.Role.ADMIN,
                Membership.Role.CHAIRMAN,
                Membership.Role.TREASURER,
            ],
            status=Membership.Status.ACTIVE,
        ).exists()

    if not allowed:
        raise PermissionDenied

    # ---------------------------------------------------------
    # Get payments
    # ---------------------------------------------------------
    payments = (
        schedule.payments
        .all()
        .order_by(
            "-payment_date",
            "-created_at",
        )
    )

    # ---------------------------------------------------------
    # Calculate totals
    # ---------------------------------------------------------
    from .services.contribution_payment_service import (
        calculate_remaining_balance,
        calculate_total_paid,
    )

    total_paid = calculate_total_paid(
        schedule
    )

    remaining_balance = calculate_remaining_balance(
        schedule
    )

    context = {
        "schedule": schedule,
        "payments": payments,
        "total_paid": total_paid,
        "remaining_balance": remaining_balance,
    }

    return render(
        request,
        "contributions/payments/list.html",
        context,
    )



@login_required
def payment_detail_view(request, payment_id):

    payment = get_object_or_404(
        ContributionPayment.objects.select_related(
            "schedule",
            "schedule__membership",
            "schedule__membership__user",
            "schedule__membership__group",
            "schedule__contribution_type",
        ),
        pk=payment_id,
    )

    schedule = payment.schedule

    # ---------------------------------------------------------
    # Permission check
    # ---------------------------------------------------------
    if request.user.is_superuser:

        allowed = (
            schedule.membership.status
            == Membership.Status.ACTIVE
            and schedule.membership.user.is_active
            and schedule.membership.group.is_active
        )

    else:

        allowed = Membership.objects.filter(
            user=request.user,
            group=schedule.membership.group,
            role__in=[
                Membership.Role.ADMIN,
                Membership.Role.CHAIRMAN,
                Membership.Role.TREASURER,
            ],
            status=Membership.Status.ACTIVE,
        ).exists()

    if not allowed:
        raise PermissionDenied

    context = {
        "payment": payment,
        "schedule": schedule,
    }

    return render(
        request,
        "contributions/payments/detail.html",
        context,
    )

