from django.urls import path

from . import views


app_name = "contributions"


urlpatterns = [
    path(
        "",
        views.contribution_dashboard,
        name="dashboard",
    ),

    # Generate schedules
    path(
        "schedules/generate/",
        views.generate_schedules_view,
        name="generate_schedules",
    ),

    # Backward-compatible alias
    path(
        "schedules/generate/",
        views.generate_schedules_view,
        name="generate-schedules",
    ),

    # Schedule list
    path(
        "schedules/",
        views.schedule_list_view,
        name="schedule-list",
    ),

    # Create payment
    path(
        "schedules/<int:schedule_id>/payment/create/",
        views.create_payment_view,
        name="create-payment",
    ),
    path(
        "schedules/<int:schedule_id>/",
        views.schedule_detail_view,
        name="schedule-detail",
    ),
    path(
        "schedules/<int:schedule_id>/payments/",
        views.payment_list_view,
        name="payment-list",
    ),
    path(
        "payments/<int:payment_id>/",
        views.payment_detail_view,
        name="payment-detail",
    ),
    path(
        "payments/<int:payment_id>/edit/",
        views.edit_payment_view,
        name="payment-edit",
    ),
    path(
        "payments/<int:payment_id>/delete/",
        views.delete_payment_view,
        name="payment-delete",
    ),
    path(
        "schedules/<int:schedule_id>/waive/",
        views.waive_contribution_view,
        name="waive-contribution",
    ),
        path(
        "schedules/<int:schedule_id>/restore/",
        views.restore_contribution_view,
        name="restore-contribution",
    ),
]