from django.db import models

from django.conf import settings


class ContributionCategory(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    name = models.CharField(
        max_length=100,
        unique=True,
    )

    description = models.TextField(
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Contribution Category"
        verbose_name_plural = "Contribution Categories"

    def __str__(self):
        return self.name


class ContributionType(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    category = models.ForeignKey(
        ContributionCategory,
        on_delete=models.PROTECT,
        related_name="contribution_types",
    )

    name = models.CharField(
        max_length=100,
    )

    description = models.TextField(
        blank=True,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["category", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["category", "name"],
                name="unique_contribution_type_per_category",
            ),
        ]
        verbose_name = "Contribution Type"
        verbose_name_plural = "Contribution Types"

    def __str__(self):
        return self.name


class ContributionSchedule(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PARTIAL = "partial", "Partial"
        PAID = "paid", "Paid"
        WAIVED = "waived", "Waived"

    membership = models.ForeignKey(
        "memberships.Membership",
        on_delete=models.PROTECT,
        related_name="contribution_schedules",
    )

    contribution_type = models.ForeignKey(
        ContributionType,
        on_delete=models.PROTECT,
        related_name="schedules",
    )

    period = models.DateField(
        help_text="First day of the contribution month.",
    )

    expected_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    waived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="waived_contribution_schedules",
    )

    waived_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    waived_reason = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-period",
            "membership",
            "contribution_type",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "membership",
                    "contribution_type",
                    "period",
                ],
                name="unique_schedule_per_membership_type_period",
            ),
        ]

        verbose_name = "Contribution Schedule"
        verbose_name_plural = "Contribution Schedules"

    def __str__(self):
        return (
            f"{self.membership} - "
            f"{self.contribution_type} - "
            f"{self.period:%B %Y}"
        )


class ContributionPayment(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        MPESA = "mpesa", "M-Pesa"
        BANK = "bank", "Bank"
        OTHER = "other", "Other"

    schedule = models.ForeignKey(
        ContributionSchedule,
        on_delete=models.PROTECT,
        related_name="payments",
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    payment_date = models.DateField()

    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )

    reference = models.CharField(
        max_length=100,
        blank=True,
    )

    notes = models.TextField(
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-payment_date",
            "-created_at",
        ]

        verbose_name = "Contribution Payment"
        verbose_name_plural = "Contribution Payments"

    def __str__(self):
        return (
            f"{self.schedule} - "
            f"{self.amount} - "
            f"{self.payment_date}"
        )


class ContributionWaiver(models.Model):

    class Action(models.TextChoices):
        WAIVED = "waived", "Waived"
        RESTORED = "restored", "Restored"

    schedule = models.ForeignKey(
        ContributionSchedule,
        on_delete=models.PROTECT,
        related_name="waiver_history",
    )

    action = models.CharField(
        max_length=20,
        choices=Action.choices,
    )

    reason = models.TextField()

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="contribution_waiver_actions",
    )

    performed_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "-performed_at",
        ]
        verbose_name = "Contribution Waiver History"
        verbose_name_plural = (
            "Contribution Waiver Histories"
        )

    def __str__(self):
        return (
            f"{self.schedule} - "
            f"{self.get_action_display()}"
        )