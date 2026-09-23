from datetime import date
from decimal import Decimal

from django.db import IntegrityError
from django.db.models import Sum
from django.test import TestCase
from django.utils import timezone

from apps.contributions.services.contribution_payment_service import (
    calculate_remaining_balance,
    calculate_total_paid,
    create_payment,
    recalculate_schedule_status,
)
from apps.contributions.services.contribution_waiver_service import restore_contribution, waive_contribution

from .services.contribution_schedule_service import (
    generate_monthly_schedules,
)
from django.urls import reverse
from django.contrib.messages import get_messages
from django.contrib.auth import get_user_model
from apps.accounts.models import User
from apps.groups.models import Group
from apps.memberships.models import Membership

from apps.contributions.forms import (
    ContributionCategoryForm,
    ContributionTypeForm,
    ScheduleGenerationForm,)
from .models import (
    ContributionCategory,
    ContributionPayment,
    ContributionType,
    ContributionSchedule,
    ContributionWaiver,
)
User = get_user_model()


class ContributionCategoryModelTests(TestCase):

    def test_category_can_be_created(self):
        category = ContributionCategory.objects.create(
            name="Monthly Contribution",
        )

        self.assertEqual(
            category.name,
            "Monthly Contribution",
        )

    def test_category_defaults_to_active(self):
        category = ContributionCategory.objects.create(
            name="Development Fund",
        )

        self.assertEqual(
            category.status,
            ContributionCategory.Status.ACTIVE,
        )

    def test_category_string_representation(self):
        category = ContributionCategory.objects.create(
            name="Emergency Fund",
        )

        self.assertEqual(
            str(category),
            "Emergency Fund",
        )

    def test_category_name_is_unique(self):
        ContributionCategory.objects.create(
            name="Monthly Contribution",
        )

        with self.assertRaises(IntegrityError):
            ContributionCategory.objects.create(
                name="Monthly Contribution",
            )


class ContributionTypeModelTests(TestCase):

    def setUp(self):
        self.category = ContributionCategory.objects.create(
            name="Monthly Contribution",
        )

    def test_contribution_type_can_be_created(self):
        contribution_type = ContributionType.objects.create(
            category=self.category,
            name="July Contribution",
            amount="10000.00",
        )

        contribution_type.refresh_from_db()

        self.assertEqual(
            contribution_type.name,
            "July Contribution",
        )

        self.assertEqual(
            contribution_type.amount,
            Decimal("10000.00"),
        )

        self.assertEqual(
            contribution_type.category,
            self.category,
        )

    def test_contribution_type_defaults_to_active(self):
        contribution_type = ContributionType.objects.create(
            category=self.category,
            name="July Contribution",
            amount="10000.00",
        )

        self.assertEqual(
            contribution_type.status,
            ContributionType.Status.ACTIVE,
        )

    def test_contribution_type_string_representation(self):
        contribution_type = ContributionType.objects.create(
            category=self.category,
            name="July Contribution",
            amount="10000.00",
        )

        self.assertEqual(
            str(contribution_type),
            "July Contribution",
        )

    def test_same_name_can_exist_in_different_categories(self):
        second_category = ContributionCategory.objects.create(
            name="Development Fund",
        )

        ContributionType.objects.create(
            category=self.category,
            name="Monthly Payment",
            amount="10000.00",
        )

        contribution_type = ContributionType.objects.create(
            category=second_category,
            name="Monthly Payment",
            amount="20000.00",
        )

        self.assertEqual(
            contribution_type.name,
            "Monthly Payment",
        )

    def test_same_name_cannot_exist_in_same_category(self):
        ContributionType.objects.create(
            category=self.category,
            name="Monthly Payment",
            amount="10000.00",
        )

        with self.assertRaises(IntegrityError):
            ContributionType.objects.create(
                category=self.category,
                name="Monthly Payment",
                amount="10000.00",
            )



class ContributionScheduleModelTests(TestCase):

    def setUp(self):
        self.category = ContributionCategory.objects.create(
            name="Monthly Contribution",
        )

        self.contribution_type = ContributionType.objects.create(
            category=self.category,
            name="Monthly Payment",
            amount="10000.00",
        )

        self.user = User.objects.create_user(
            email="member@example.com",
            password="TestPassword123!",
            first_name="Test",
            last_name="Member",
        )

        self.group = Group.objects.create(
            name="Test Group",
            code="TST",
        )

        self.membership = Membership.objects.create(
            user=self.user,
            group=self.group,
            membership_number="TST-0001",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

    def test_schedule_can_be_created(self):
        schedule = ContributionSchedule.objects.create(
            membership=self.membership,
            contribution_type=self.contribution_type,
            period=date(2026, 8, 1),
            expected_amount="10000.00",
        )

        schedule.refresh_from_db()

        self.assertEqual(
            schedule.membership,
            self.membership,
        )

        self.assertEqual(
            schedule.contribution_type,
            self.contribution_type,
        )

        self.assertEqual(
            schedule.period,
            date(2026, 8, 1),
        )

        self.assertEqual(
            schedule.expected_amount,
            Decimal("10000.00"),
        )

    def test_schedule_defaults_to_pending(self):
        schedule = ContributionSchedule.objects.create(
            membership=self.membership,
            contribution_type=self.contribution_type,
            period=date(2026, 8, 1),
            expected_amount="10000.00",
        )

        self.assertEqual(
            schedule.status,
            ContributionSchedule.Status.PENDING,
        )

    def test_schedule_string_representation(self):
        schedule = ContributionSchedule.objects.create(
            membership=self.membership,
            contribution_type=self.contribution_type,
            period=date(2026, 8, 1),
            expected_amount="10000.00",
        )

        self.assertEqual(
            str(schedule),
            (
                "TST-0001 - member@example.com - "
                "Monthly Payment - August 2026"
            ),
        )

    def test_duplicate_schedule_for_same_period_is_not_allowed(self):
        ContributionSchedule.objects.create(
            membership=self.membership,
            contribution_type=self.contribution_type,
            period=date(2026, 8, 1),
            expected_amount="10000.00",
        )

        with self.assertRaises(IntegrityError):
            ContributionSchedule.objects.create(
                membership=self.membership,
                contribution_type=self.contribution_type,
                period=date(2026, 8, 1),
                expected_amount="10000.00",
            )

    def test_same_membership_can_have_different_months(self):
        august = ContributionSchedule.objects.create(
            membership=self.membership,
            contribution_type=self.contribution_type,
            period=date(2026, 8, 1),
            expected_amount="10000.00",
        )

        september = ContributionSchedule.objects.create(
            membership=self.membership,
            contribution_type=self.contribution_type,
            period=date(2026, 9, 1),
            expected_amount="10000.00",
        )

        self.assertNotEqual(
            august.period,
            september.period,
        )

        self.assertEqual(
            ContributionSchedule.objects.filter(
                membership=self.membership,
                contribution_type=self.contribution_type,
            ).count(),
            2,
        )



class ContributionScheduleServiceTests(TestCase):

    def setUp(self):
        self.group = Group.objects.create(
            name="Schedule Group",
            code="SCH",
        )

        self.user1 = User.objects.create_user(
            email="member1@example.com",
            password="TestPassword123!",
        )

        self.user2 = User.objects.create_user(
            email="member2@example.com",
            password="TestPassword123!",
        )

        self.membership1 = Membership.objects.create(
            user=self.user1,
            group=self.group,
            membership_number="SCH-0001",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

        self.membership2 = Membership.objects.create(
            user=self.user2,
            group=self.group,
            membership_number="SCH-0002",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

        self.category = ContributionCategory.objects.create(
            name="Monthly Contribution",
        )

        self.contribution_type = ContributionType.objects.create(
            category=self.category,
            name="Monthly Contribution",
            description="Monthly member contribution",
            amount=Decimal("10000.00"),
            status=ContributionType.Status.ACTIVE,
        )

        self.period = date(
            2026,
            8,
            15,
        )

    def test_generates_schedule_for_active_members(self):
        schedules = generate_monthly_schedules(
            self.period
        )

        self.assertEqual(
            len(schedules),
            2,
        )

        self.assertEqual(
            ContributionSchedule.objects.count(),
            2,
        )

    def test_period_is_normalized_to_first_day_of_month(self):
        generate_monthly_schedules(
            self.period
        )

        self.assertTrue(
            ContributionSchedule.objects.filter(
                period=date(2026, 8, 1)
            ).exists()
        )

    def test_expected_amount_comes_from_contribution_type(self):
        generate_monthly_schedules(
            self.period
        )

        schedule = (
            ContributionSchedule.objects
            .get(
                membership=self.membership1,
                contribution_type=self.contribution_type,
            )
        )

        self.assertEqual(
            schedule.expected_amount,
            Decimal("10000.00"),
        )

    def test_new_schedule_defaults_to_pending(self):
        generate_monthly_schedules(
            self.period
        )

        schedule = (
            ContributionSchedule.objects
            .get(
                membership=self.membership1,
                contribution_type=self.contribution_type,
            )
        )

        self.assertEqual(
            schedule.status,
            ContributionSchedule.Status.PENDING,
        )

    def test_running_service_twice_does_not_create_duplicates(self):
        first_result = generate_monthly_schedules(
            self.period
        )

        second_result = generate_monthly_schedules(
            self.period
        )

        self.assertEqual(
            len(first_result),
            2,
        )

        self.assertEqual(
            len(second_result),
            0,
        )

        self.assertEqual(
            ContributionSchedule.objects.count(),
            2,
        )

    def test_inactive_membership_is_not_scheduled(self):
        self.membership2.status = (
            Membership.Status.INACTIVE
        )

        self.membership2.save(
            update_fields=["status"]
        )

        schedules = generate_monthly_schedules(
            self.period
        )

        self.assertEqual(
            len(schedules),
            1,
        )

        self.assertEqual(
            ContributionSchedule.objects.count(),
            1,
        )

        self.assertTrue(
            ContributionSchedule.objects.filter(
                membership=self.membership1,
            ).exists()
        )

        self.assertFalse(
            ContributionSchedule.objects.filter(
                membership=self.membership2,
            ).exists()
        )

    def test_inactive_contribution_type_is_not_scheduled(self):
        self.contribution_type.status = (
            ContributionType.Status.INACTIVE
        )

        self.contribution_type.save(
            update_fields=["status"]
        )

        schedules = generate_monthly_schedules(
            self.period
        )

        self.assertEqual(
            len(schedules),
            0,
        )

        self.assertEqual(
            ContributionSchedule.objects.count(),
            0,
        )

        # ---------------------------------------------------------
    # Security: Group isolation
    # ---------------------------------------------------------

    def test_generation_can_be_scoped_to_selected_group(self):
        """
        A group-scoped generation must create schedules only
        for memberships belonging to the selected group.
        """

        # Create a second group.
        group2 = Group.objects.create(
            name="Second Group",
            code="SEC",
        )

        # Create a member belonging to the second group.
        user3 = User.objects.create_user(
            email="member3@example.com",
            password="TestPassword123!",
        )

        membership3 = Membership.objects.create(
            user=user3,
            group=group2,
            membership_number="SEC-0001",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

        # Generate schedules for the first group only.
        schedules = generate_monthly_schedules(
            self.period,
            group=self.group,
        )

        # Only the first group's memberships should receive schedules.
        self.assertEqual(
            len(schedules),
            2,
        )

        self.assertTrue(
            ContributionSchedule.objects.filter(
                membership=self.membership1,
            ).exists()
        )

        self.assertTrue(
            ContributionSchedule.objects.filter(
                membership=self.membership2,
            ).exists()
        )

        # The second group's member must not receive a schedule.
        self.assertFalse(
            ContributionSchedule.objects.filter(
                membership=membership3,
            ).exists()
        )


    def test_generation_does_not_create_schedules_for_other_groups(self):
        """
        A group manager must never cause schedule generation
        for memberships belonging to another group.
        """

        # Create another group.
        group2 = Group.objects.create(
            name="Other Group",
            code="OTH",
        )

        # Create an active member in the other group.
        user3 = User.objects.create_user(
            email="othermember@example.com",
            password="TestPassword123!",
        )

        membership3 = Membership.objects.create(
            user=user3,
            group=group2,
            membership_number="OTH-0001",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

        # Generate schedules only for the first group.
        generate_monthly_schedules(
            self.period,
            group=self.group,
        )

        # First group should have schedules.
        self.assertEqual(
            ContributionSchedule.objects.filter(
                membership__group=self.group,
            ).count(),
            2,
        )

        # Other group must have zero schedules.
        self.assertEqual(
            ContributionSchedule.objects.filter(
                membership__group=group2,
            ).count(),
            0,
        )


    def test_generation_for_second_group_does_not_affect_first_group(self):
        """
        Generating schedules for one group must not create or
        modify schedules belonging to another group.
        """

        # Create a second group.
        group2 = Group.objects.create(
            name="Third Group",
            code="THI",
        )

        user3 = User.objects.create_user(
            email="member4@example.com",
            password="TestPassword123!",
        )

        membership3 = Membership.objects.create(
            user=user3,
            group=group2,
            membership_number="THI-0001",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

        # Generate schedules for the second group only.
        schedules = generate_monthly_schedules(
            self.period,
            group=group2,
        )

        # Only the second group's member should receive a schedule.
        self.assertEqual(
            len(schedules),
            1,
        )

        self.assertTrue(
            ContributionSchedule.objects.filter(
                membership=membership3,
            ).exists()
        )

        # First group must remain untouched.
        self.assertEqual(
            ContributionSchedule.objects.filter(
                membership__group=self.group,
            ).count(),
            0,
        )

class ContributionScheduleViewTests(TestCase):

    def setUp(self):
        self.category = ContributionCategory.objects.create(
            name="Monthly Contribution",
        )

        self.contribution_type = ContributionType.objects.create(
            category=self.category,
            name="Monthly Payment",
            amount="10000.00",
        )

        self.group = Group.objects.create(
            name="Test Group",
            code="TST",
        )

        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="TestPassword123!",
        )

        self.member = User.objects.create_user(
            email="member@example.com",
            password="TestPassword123!",
        )

        self.outsider = User.objects.create_user(
            email="outsider@example.com",
            password="TestPassword123!",
        )

        self.admin_membership = Membership.objects.create(
            user=self.admin,
            group=self.group,
            membership_number="TST-0001",
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )

        self.member_membership = Membership.objects.create(
            user=self.member,
            group=self.group,
            membership_number="TST-0002",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

        self.url = reverse(
            "contributions:generate_schedules"
        )

    def test_admin_can_generate_schedules(self):
        """
        An active group admin can generate contribution
        schedules for their own group.
        """

        self.client.login(
            email="admin@example.com",
            password="TestPassword123!",
        )

        response = self.client.post(
            reverse(
                "contributions:generate-schedules"
            ),
            {
                "month": "2026-08",
                "group_id": str(self.group.pk),
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "contributions:dashboard"
            ),
        )

        self.assertEqual(
            ContributionSchedule.objects.count(),
            2,
        )

        self.assertEqual(
            ContributionSchedule.objects.filter(
                membership__group=self.group,
            ).count(),
            2,
        )

    def test_member_cannot_generate_schedules(self):
        """
        A normal group member must not be allowed to
        generate contribution schedules.
        """

        self.client.login(
            email="member@example.com",
            password="TestPassword123!",
        )

        response = self.client.post(
            reverse(
                "contributions:generate-schedules"
            ),
            {
                "month": "2026-08",
                "group_id": str(self.group.pk),
            },
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.assertEqual(
            ContributionSchedule.objects.count(),
            0,
        )

    def test_unrelated_user_cannot_generate_schedules(self):
        """
        A user who has no active membership in the group
        must not be allowed to generate schedules.
        """

        self.client.login(
            email="outsider@example.com",
            password="TestPassword123!",
        )

        response = self.client.post(
            reverse(
                "contributions:generate-schedules"
            ),
            {
                "month": "2026-08",
                "group_id": str(self.group.pk),
            },
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.assertEqual(
            ContributionSchedule.objects.count(),
            0,
        )

    def test_generate_requires_month(self):
        """
        Schedule generation requires a valid month.
        """

        self.client.login(
            email="admin@example.com",
            password="TestPassword123!",
        )

        response = self.client.post(
            reverse(
                "contributions:generate-schedules"
            ),
            {
                "group_id": str(self.group.pk),
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "contributions:dashboard"
            ),
        )

        self.assertEqual(
            ContributionSchedule.objects.count(),
            0,
        )

    def test_invalid_month_is_rejected(self):
        """
        An invalid month must not generate schedules.
        """

        self.client.login(
            email="admin@example.com",
            password="TestPassword123!",
        )

        response = self.client.post(
            reverse(
                "contributions:generate-schedules"
            ),
            {
                "month": "invalid-month",
                "group_id": str(self.group.pk),
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "contributions:dashboard"
            ),
        )

        self.assertEqual(
            ContributionSchedule.objects.count(),
            0,
        )

    # ---------------------------------------------------------
    # Security: Group isolation
    # ---------------------------------------------------------

    def test_admin_cannot_generate_schedules_for_other_group(self):
        """
        An admin must not cause contribution schedules to be
        generated for members belonging to another group.
        """

        # Create a second group.
        other_group = Group.objects.create(
            name="Other Group",
            code="OTH",
        )

        # Create an active member in the other group.
        other_user = User.objects.create_user(
            email="othermember@example.com",
            password="TestPassword123!",
        )

        other_membership = Membership.objects.create(
            user=other_user,
            group=other_group,
            membership_number="OTH-0001",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

        # Log in as admin of the first group.
        self.client.login(
            email="admin@example.com",
            password="TestPassword123!",
        )

        # Try to generate schedules for the other group.
        response = self.client.post(
            reverse(
                "contributions:generate-schedules"
            ),
            {
                "month": "2026-08",
                "group_id": str(other_group.pk),
            },
        )

        # The admin must not be allowed to access
        # another group's schedules.
        self.assertEqual(
            response.status_code,
            404,
        )

        # The other group's member must NOT receive a schedule.
        self.assertFalse(
            ContributionSchedule.objects.filter(
                membership=other_membership,
            ).exists()
        )

        # No schedules should have been generated.
        self.assertEqual(
            ContributionSchedule.objects.count(),
            0,
        )

    def test_generation_only_affects_admin_group(self):
        """
        Schedule generation from a group admin must affect
        only memberships belonging to that admin's group.
        """

        # Create another group.
        other_group = Group.objects.create(
            name="Second Group",
            code="SEC",
        )

        # Create a member in the second group.
        other_user = User.objects.create_user(
            email="secondmember@example.com",
            password="TestPassword123!",
        )

        other_membership = Membership.objects.create(
            user=other_user,
            group=other_group,
            membership_number="SEC-0001",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

        # Log in as the admin of the first group.
        self.client.login(
            email="admin@example.com",
            password="TestPassword123!",
        )

        # Generate schedules for the admin's own group.
        response = self.client.post(
            reverse(
                "contributions:generate-schedules"
            ),
            {
                "month": "2026-08",
                "group_id": str(self.group.pk),
            },
        )

        self.assertRedirects(
            response,
            reverse(
                "contributions:dashboard"
            ),
        )

        # First group should receive schedules for its two members.
        self.assertEqual(
            ContributionSchedule.objects.filter(
                membership__group=self.group,
            ).count(),
            2,
        )

        # Second group must not be affected.
        self.assertEqual(
            ContributionSchedule.objects.filter(
                membership__group=other_group,
            ).count(),
            0,
        )

        # Explicitly verify that the second group's membership
        # has no generated schedule.
        self.assertFalse(
            ContributionSchedule.objects.filter(
                membership=other_membership,
            ).exists()
        )

class ContributionDashboardTests(TestCase):

    def setUp(self):
        self.category = ContributionCategory.objects.create(
            name="Monthly Contribution",
        )

        self.contribution_type = ContributionType.objects.create(
            category=self.category,
            name="Monthly Payment",
            amount="10000.00",
        )

        self.group = Group.objects.create(
            name="Dashboard Group",
            code="DASH",
        )

        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="TestPassword123!",
        )

        self.chairman = User.objects.create_user(
            email="chairman@example.com",
            password="TestPassword123!",
        )

        self.treasurer = User.objects.create_user(
            email="treasurer@example.com",
            password="TestPassword123!",
        )

        self.member = User.objects.create_user(
            email="member@example.com",
            password="TestPassword123!",
        )

        self.outsider = User.objects.create_user(
            email="outsider@example.com",
            password="TestPassword123!",
        )

        Membership.objects.create(
            user=self.admin,
            group=self.group,
            membership_number="DASH-0001",
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )

        Membership.objects.create(
            user=self.chairman,
            group=self.group,
            membership_number="DASH-0002",
            role=Membership.Role.CHAIRMAN,
            status=Membership.Status.ACTIVE,
        )

        Membership.objects.create(
            user=self.treasurer,
            group=self.group,
            membership_number="DASH-0003",
            role=Membership.Role.TREASURER,
            status=Membership.Status.ACTIVE,
        )

        Membership.objects.create(
            user=self.member,
            group=self.group,
            membership_number="DASH-0004",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

    def test_admin_can_access_dashboard(self):
        self.client.login(
            email="admin@example.com",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse("contributions:dashboard")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_chairman_can_access_dashboard(self):
        self.client.login(
            email="chairman@example.com",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse("contributions:dashboard")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_treasurer_can_access_dashboard(self):
        self.client.login(
            email="treasurer@example.com",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse("contributions:dashboard")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_member_cannot_access_dashboard(self):
        self.client.login(
            email="member@example.com",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse("contributions:dashboard")
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_outsider_cannot_access_dashboard(self):
        self.client.login(
            email="outsider@example.com",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse("contributions:dashboard")
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_dashboard_shows_active_members(self):
        self.client.login(
            email="admin@example.com",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse("contributions:dashboard")
        )

        self.assertEqual(
            response.context["member_count"],
            4,
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(
            reverse("contributions:dashboard")
        )

        self.assertNotEqual(
            response.status_code,
            200,
        )

    # ---------------------------------------------------------
    # Security: Cross-group isolation
    # ---------------------------------------------------------

    def test_dashboard_does_not_include_members_from_other_group(self):
        """
        An admin must only see members belonging to their own group.
        Members from another group must not appear in dashboard data.
        """

        # Create another group.
        other_group = Group.objects.create(
            name="Other Dashboard Group",
            code="ODASH",
        )

        # Create a member in the other group.
        other_user = User.objects.create_user(
            email="other-dashboard-member@example.com",
            password="TestPassword123!",
        )

        Membership.objects.create(
            user=other_user,
            group=other_group,
            membership_number="ODASH-0001",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

        # Login as Group A admin.
        self.client.login(
            email="admin@example.com",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse("contributions:dashboard")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        # Dashboard must still show only Group A members.
        self.assertEqual(
            response.context["member_count"],
            4,
        )


class GenerateSchedulesViewTests(TestCase):

    def setUp(self):
        self.group = Group.objects.create(
            name="View Test Group",
            code="VIEW",
        )

        self.admin = User.objects.create_user(
            email="admin-view@example.com",
            password="TestPassword123!",
        )

        self.chairman = User.objects.create_user(
            email="chairman-view@example.com",
            password="TestPassword123!",
        )

        self.treasurer = User.objects.create_user(
            email="treasurer-view@example.com",
            password="TestPassword123!",
        )

        self.member = User.objects.create_user(
            email="member-view@example.com",
            password="TestPassword123!",
        )

        self.membership_admin = Membership.objects.create(
            user=self.admin,
            group=self.group,
            membership_number="VIEW-0001",
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )

        self.membership_chairman = Membership.objects.create(
            user=self.chairman,
            group=self.group,
            membership_number="VIEW-0002",
            role=Membership.Role.CHAIRMAN,
            status=Membership.Status.ACTIVE,
        )

        self.membership_treasurer = Membership.objects.create(
            user=self.treasurer,
            group=self.group,
            membership_number="VIEW-0003",
            role=Membership.Role.TREASURER,
            status=Membership.Status.ACTIVE,
        )

        self.membership_member = Membership.objects.create(
            user=self.member,
            group=self.group,
            membership_number="VIEW-0004",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

        self.category = ContributionCategory.objects.create(
            name="View Contribution",
        )

        self.contribution_type = ContributionType.objects.create(
            category=self.category,
            name="Monthly Contribution",
            description="Monthly contribution",
            amount=Decimal("10000.00"),
            status=ContributionType.Status.ACTIVE,
        )

        self.url = reverse(
            "contributions:generate_schedules"
        )

    def test_admin_can_generate_schedules(self):
        self.client.login(
            email="admin-view@example.com",
            password="TestPassword123!",
        )

        response = self.client.post(
            self.url,
            {
                "month": "2026-08",
                "group_id": str(self.group.pk),
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertEqual(
            ContributionSchedule.objects.count(),
            4,
        )

    def test_chairman_can_generate_schedules(self):
        self.client.login(
            email="chairman-view@example.com",
            password="TestPassword123!",
        )

        response = self.client.post(
            self.url,
            {
                "month": "2026-08",
                "group_id": str(self.group.pk),
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertEqual(
            ContributionSchedule.objects.count(),
            4,
        )

    def test_treasurer_can_generate_schedules(self):
        self.client.login(
            email="treasurer-view@example.com",
            password="TestPassword123!",
        )

        response = self.client.post(
            self.url,
            {
                "month": "2026-08",
                "group_id": str(self.group.pk),
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertEqual(
            ContributionSchedule.objects.count(),
            4,
        )

    def test_normal_member_cannot_generate_schedules(self):
        self.client.login(
            email="member-view@example.com",
            password="TestPassword123!",
        )

        response = self.client.post(
            self.url,
            {
                "month": "2026-08",
                "group_id": str(self.group.pk),
            },
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.assertEqual(
            ContributionSchedule.objects.count(),
            0,
        )

    def test_get_request_is_not_allowed(self):
        self.client.login(
            email="admin-view@example.com",
            password="TestPassword123!",
        )

        response = self.client.get(
            self.url,
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_missing_month_does_not_generate_schedules(self):
        self.client.login(
            email="admin-view@example.com",
            password="TestPassword123!",
        )

        response = self.client.post(
            self.url,
            {}

        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertEqual(
            ContributionSchedule.objects.count(),
            0,
        )

    def test_invalid_month_does_not_generate_schedules(self):
        self.client.login(
            email="admin-view@example.com",
            password="TestPassword123!",
        )

        response = self.client.post(
            self.url,
            {
                "month": "invalid-month",
                "group_id": str(self.group.pk),
            },
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertEqual(
            ContributionSchedule.objects.count(),
            0,
        )

    def test_generating_same_month_twice_does_not_duplicate(self):
        self.client.login(
            email="admin-view@example.com",
            password="TestPassword123!",
        )

        first_response = self.client.post(
            self.url,
            {
                "month": "2026-08",
                "group_id": str(self.group.pk),
            },
        )

        second_response = self.client.post(
            self.url,
            {
                "month": "2026-08",
                "group_id": str(self.group.pk),
            },
        )

        self.assertEqual(
            first_response.status_code,
            302,
        )

        self.assertEqual(
            second_response.status_code,
            302,
        )

        self.assertEqual(
            ContributionSchedule.objects.count(),
            4,
        )


class ContributionCategoryFormTests(TestCase):

    def test_valid_category_form(self):
        form = ContributionCategoryForm(
            data={
                "name": "Monthly Contribution",
            }
        )

        self.assertTrue(form.is_valid())

    def test_category_name_is_required(self):
        form = ContributionCategoryForm(
            data={
                "name": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_category_form_can_create_category(self):
        form = ContributionCategoryForm(
            data={
                "name": "Development Fund",
            }
        )

        self.assertTrue(form.is_valid())

        category = form.save()

        self.assertEqual(
            category.name,
            "Development Fund",
        )

        self.assertTrue(
            ContributionCategory.objects.filter(
                name="Development Fund"
            ).exists()
        )

    def test_duplicate_category_name_is_rejected(self):
        ContributionCategory.objects.create(
            name="Emergency Fund",
        )

        form = ContributionCategoryForm(
            data={
                "name": "Emergency Fund",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)



class ContributionTypeFormTests(TestCase):

    def setUp(self):
        self.category = ContributionCategory.objects.create(
            name="Monthly Contribution",
        )

    def test_valid_contribution_type_form(self):
        form = ContributionTypeForm(
            data={
                "category": self.category.id,
                "name": "August Contribution",
                "description": "Monthly contribution",
                "amount": "10000.00",
                "status": ContributionType.Status.ACTIVE,
            }
        )

        self.assertTrue(form.is_valid())

    def test_contribution_type_name_is_required(self):
        form = ContributionTypeForm(
            data={
                "category": self.category.id,
                "name": "",
                "description": "",
                "amount": "10000.00",
                "status": ContributionType.Status.ACTIVE,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_contribution_type_amount_is_required(self):
        form = ContributionTypeForm(
            data={
                "category": self.category.id,
                "name": "August Contribution",
                "description": "",
                "amount": "",
                "status": ContributionType.Status.ACTIVE,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("amount", form.errors)

    def test_contribution_type_amount_is_decimal(self):
        form = ContributionTypeForm(
            data={
                "category": self.category.id,
                "name": "August Contribution",
                "description": "",
                "amount": "10000.00",
                "status": ContributionType.Status.ACTIVE,
            }
        )

        self.assertTrue(form.is_valid())

        contribution_type = form.save()

        contribution_type.refresh_from_db()

        self.assertEqual(
            contribution_type.amount,
            Decimal("10000.00"),
        )

    def test_duplicate_type_name_in_same_category_is_rejected(self):
        ContributionType.objects.create(
            category=self.category,
            name="August Contribution",
            amount=Decimal("10000.00"),
        )

        form = ContributionTypeForm(
            data={
                "category": self.category.id,
                "name": "August Contribution",
                "description": "",
                "amount": "10000.00",
                "status": ContributionType.Status.ACTIVE,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)


class ScheduleGenerationFormTests(TestCase):

    def test_valid_month_is_accepted(self):
        form = ScheduleGenerationForm(
            data={
                "month": "2026-08",
            }
        )

        self.assertTrue(form.is_valid())

    def test_month_is_normalized_to_first_day(self):
        form = ScheduleGenerationForm(
            data={
                "month": "2026-08",
            }
        )

        self.assertTrue(form.is_valid())

        self.assertEqual(
            form.cleaned_data["month"],
            date(2026, 8, 1),
        )

    def test_month_is_required(self):
        form = ScheduleGenerationForm(
            data={}
        )

        self.assertFalse(form.is_valid())
        self.assertIn("month", form.errors)

    def test_invalid_month_is_rejected(self):
        form = ScheduleGenerationForm(
            data={
                "month": "invalid-month",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("month", form.errors)


class ContributionPaymentModelTests(TestCase):

    def setUp(self):
        self.group = Group.objects.create(
            name="Payment Group",
            code="PAY",
        )

        self.user = User.objects.create_user(
            email="paymentmember@example.com",
            password="TestPassword123!",
        )

        self.membership = Membership.objects.create(
            user=self.user,
            group=self.group,
            membership_number="PAY-0001",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

        self.category = ContributionCategory.objects.create(
            name="Monthly Contribution",
        )

        self.contribution_type = ContributionType.objects.create(
            category=self.category,
            name="Monthly Contribution",
            amount=Decimal("10000.00"),
            status=ContributionType.Status.ACTIVE,
        )

        self.schedule = ContributionSchedule.objects.create(
            membership=self.membership,
            contribution_type=self.contribution_type,
            period=date(2026, 8, 1),
            expected_amount=Decimal("10000.00"),
            status=ContributionSchedule.Status.PENDING,
        )

    def test_payment_can_be_created(self):
        payment = ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=date(2026, 8, 15),
            payment_method=ContributionPayment.PaymentMethod.CASH,
        )

        self.assertIsNotNone(
            payment.pk
        )

        self.assertEqual(
            payment.schedule,
            self.schedule,
        )

    def test_payment_amount_is_decimal(self):
        payment = ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=date(2026, 8, 15),
        )

        payment.refresh_from_db()

        self.assertEqual(
            payment.amount,
            Decimal("5000.00"),
        )

        self.assertIsInstance(
            payment.amount,
            Decimal,
        )

    def test_payment_method_defaults_to_cash(self):
        payment = ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=date(2026, 8, 15),
        )

        self.assertEqual(
            payment.payment_method,
            ContributionPayment.PaymentMethod.CASH,
        )

    def test_payment_method_choices_are_available(self):
        self.assertEqual(
            ContributionPayment.PaymentMethod.CASH,
            "cash",
        )

        self.assertEqual(
            ContributionPayment.PaymentMethod.MPESA,
            "mpesa",
        )

        self.assertEqual(
            ContributionPayment.PaymentMethod.BANK,
            "bank",
        )

        self.assertEqual(
            ContributionPayment.PaymentMethod.OTHER,
            "other",
        )

    def test_multiple_payments_can_be_created_for_same_schedule(self):
        payment1 = ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("4000.00"),
            payment_date=date(2026, 8, 10),
        )

        payment2 = ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("6000.00"),
            payment_date=date(2026, 8, 20),
        )

        self.assertEqual(
            self.schedule.payments.count(),
            2,
        )

        self.assertEqual(
            payment1.schedule,
            self.schedule,
        )

        self.assertEqual(
            payment2.schedule,
            self.schedule,
        )

    def test_reference_is_optional(self):
        payment = ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=date(2026, 8, 15),
        )

        self.assertEqual(
            payment.reference,
            "",
        )

    def test_reference_can_be_stored(self):
        payment = ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=date(2026, 8, 15),
            payment_method=ContributionPayment.PaymentMethod.MPESA,
            reference="MPESA123456789",
        )

        self.assertEqual(
            payment.reference,
            "MPESA123456789",
        )

    def test_notes_are_optional(self):
        payment = ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=date(2026, 8, 15),
        )

        self.assertEqual(
            payment.notes,
            "",
        )

    def test_notes_can_be_stored(self):
        payment = ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=date(2026, 8, 15),
            notes="Payment received in cash.",
        )

        self.assertEqual(
            payment.notes,
            "Payment received in cash.",
        )

    def test_payment_date_is_stored(self):
        payment = ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=date(2026, 8, 20),
        )

        self.assertEqual(
            payment.payment_date,
            date(2026, 8, 20),
        )

    def test_payment_is_protected_when_schedule_is_deleted(self):
        from django.db.models.deletion import ProtectedError

        ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=date(2026, 8, 15),
        )

        with self.assertRaises(ProtectedError):
            self.schedule.delete()


class ContributionPaymentServiceTests(TestCase):

    def setUp(self):
        self.group = Group.objects.create(
            name="Payment Service Group",
            code="PSG",
        )

        self.user = User.objects.create_user(
            email="paymentservice@example.com",
            password="TestPassword123!",
        )

        self.membership = Membership.objects.create(
            user=self.user,
            group=self.group,
            membership_number="PSG-0001",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

        self.category = ContributionCategory.objects.create(
            name="Monthly Contribution",
        )

        self.contribution_type = ContributionType.objects.create(
            category=self.category,
            name="Monthly Contribution",
            amount=Decimal("10000.00"),
            status=ContributionType.Status.ACTIVE,
        )

        self.schedule = ContributionSchedule.objects.create(
            membership=self.membership,
            contribution_type=self.contribution_type,
            period=date(2026, 8, 1),
            expected_amount=Decimal("10000.00"),
            status=ContributionSchedule.Status.PENDING,
        )

        self.payment_date = date(2026, 8, 20)

    def test_create_payment_creates_payment(self):
        from apps.contributions.services.contribution_payment_service import (
            create_payment,
        )

        payment = create_payment(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=self.payment_date,
        )

        self.assertIsNotNone(payment.pk)

        self.assertEqual(
            payment.schedule,
            self.schedule,
        )

        self.assertEqual(
            payment.amount,
            Decimal("5000.00"),
        )

    def test_create_payment_updates_schedule_to_partial(self):
        from apps.contributions.services.contribution_payment_service import (
            create_payment,
        )

        create_payment(
            schedule=self.schedule,
            amount=Decimal("4000.00"),
            payment_date=self.payment_date,
        )

        self.schedule.refresh_from_db()

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.PARTIAL,
        )

    def test_create_payment_updates_schedule_to_paid(self):
        from apps.contributions.services.contribution_payment_service import (
            create_payment,
        )

        create_payment(
            schedule=self.schedule,
            amount=Decimal("10000.00"),
            payment_date=self.payment_date,
        )

        self.schedule.refresh_from_db()

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.PAID,
        )

    def test_multiple_payments_update_status_correctly(self):
        from apps.contributions.services.contribution_payment_service import (
            create_payment,
        )

        create_payment(
            schedule=self.schedule,
            amount=Decimal("4000.00"),
            payment_date=self.payment_date,
        )

        self.schedule.refresh_from_db()

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.PARTIAL,
        )

        create_payment(
            schedule=self.schedule,
            amount=Decimal("6000.00"),
            payment_date=self.payment_date,
        )

        self.schedule.refresh_from_db()

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.PAID,
        )

    def test_payment_cannot_be_zero(self):
        from apps.contributions.services.contribution_payment_service import (
            create_payment,
        )

        with self.assertRaises(ValueError):
            create_payment(
                schedule=self.schedule,
                amount=Decimal("0.00"),
                payment_date=self.payment_date,
            )

    def test_payment_cannot_be_negative(self):
        from apps.contributions.services.contribution_payment_service import (
            create_payment,
        )

        with self.assertRaises(ValueError):
            create_payment(
                schedule=self.schedule,
                amount=Decimal("-100.00"),
                payment_date=self.payment_date,
            )

    def test_payment_cannot_exceed_expected_amount(self):
        from apps.contributions.services.contribution_payment_service import (
            create_payment,
        )

        with self.assertRaises(ValueError):
            create_payment(
                schedule=self.schedule,
                amount=Decimal("10001.00"),
                payment_date=self.payment_date,
            )

    def test_second_payment_cannot_exceed_remaining_balance(self):
        from apps.contributions.services.contribution_payment_service import (
            create_payment,
        )

        create_payment(
            schedule=self.schedule,
            amount=Decimal("7000.00"),
            payment_date=self.payment_date,
        )

        with self.assertRaises(ValueError):
            create_payment(
                schedule=self.schedule,
                amount=Decimal("4000.00"),
                payment_date=self.payment_date,
            )

    def test_waived_schedule_cannot_receive_payment(self):
        from apps.contributions.services.contribution_payment_service import (
            create_payment,
        )

        self.schedule.status = ContributionSchedule.Status.WAIVED

        self.schedule.save(
            update_fields=["status"]
        )

        with self.assertRaises(ValueError):
            create_payment(
                schedule=self.schedule,
                amount=Decimal("5000.00"),
                payment_date=self.payment_date,
            )

    def test_total_paid_is_calculated_correctly(self):
        from apps.contributions.services.contribution_payment_service import (
            create_payment,
        )

        create_payment(
            schedule=self.schedule,
            amount=Decimal("3000.00"),
            payment_date=self.payment_date,
        )

        create_payment(
            schedule=self.schedule,
            amount=Decimal("2000.00"),
            payment_date=self.payment_date,
        )

        total_paid = (
            ContributionPayment.objects
            .filter(schedule=self.schedule)
            .aggregate(
                total=Sum("amount")
            )
            .get("total")
            or Decimal("0.00")
        )

        self.assertEqual(
            Decimal(str(total_paid)),
            Decimal("5000.00"),
        )

    def test_remaining_balance_is_calculated_correctly(self):
        from apps.contributions.services.contribution_payment_service import (
            create_payment,
        )

        create_payment(
            schedule=self.schedule,
            amount=Decimal("3500.00"),
            payment_date=self.payment_date,
        )

        total_paid = (
            ContributionPayment.objects
            .filter(schedule=self.schedule)
            .aggregate(
                total=Sum("amount")
            )
            .get("total")
            or Decimal("0.00")
        )

        remaining_balance = (
            Decimal(str(self.schedule.expected_amount))
            - Decimal(str(total_paid))
        )

        self.assertEqual(
            remaining_balance,
            Decimal("6500.00"),
        )

    def test_remaining_balance_is_zero_when_fully_paid(self):
        from apps.contributions.services.contribution_payment_service import (
            create_payment,
        )

        create_payment(
            schedule=self.schedule,
            amount=Decimal("10000.00"),
            payment_date=self.payment_date,
        )

        total_paid = (
            ContributionPayment.objects
            .filter(schedule=self.schedule)
            .aggregate(
                total=Sum("amount")
            )
            .get("total")
            or Decimal("0.00")
        )

        remaining_balance = (
            Decimal(str(self.schedule.expected_amount))
            - Decimal(str(total_paid))
        )

        self.assertEqual(
            remaining_balance,
            Decimal("0.00"),
        )

    def test_payment_accepts_payment_method(self):
        from apps.contributions.services.contribution_payment_service import (
            create_payment,
        )

        payment = create_payment(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=self.payment_date,
            payment_method=ContributionPayment.PaymentMethod.MPESA,
            reference="MPESA123456",
        )

        self.assertEqual(
            payment.payment_method,
            ContributionPayment.PaymentMethod.MPESA,
        )

        self.assertEqual(
            payment.reference,
            "MPESA123456",
        )

    def test_payment_accepts_notes(self):
        from apps.contributions.services.contribution_payment_service import (
            create_payment,
        )

        payment = create_payment(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=self.payment_date,
            notes="Received through mobile money.",
        )

        self.assertEqual(
            payment.notes,
            "Received through mobile money.",
        )

    # ---------------------------------------------------------
    # calculate_total_paid() Tests
    # ---------------------------------------------------------

    def test_calculate_total_paid_returns_zero_when_no_payments_exist(self):
        """
        Verify that a schedule with no payments has a total
        paid amount of exactly zero.
        """

        total_paid = calculate_total_paid(
            self.schedule
        )

        self.assertEqual(
            total_paid,
            Decimal("0.00"),
        )


    def test_calculate_total_paid_returns_sum_of_all_payments(self):
        """
        Verify that calculate_total_paid() correctly sums
        all payments belonging to the schedule.
        """

        ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("3000.00"),
            payment_date=self.payment_date,
        )

        ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("2500.00"),
            payment_date=self.payment_date,
        )

        total_paid = calculate_total_paid(
            self.schedule
        )

        self.assertEqual(
            total_paid,
            Decimal("5500.00"),
        )


    def test_calculate_total_paid_ignores_payments_from_other_schedules(self):
        """
        Verify that payments belonging to another schedule
        are not included in the total.
        """

        other_schedule = ContributionSchedule.objects.create(
            membership=self.membership,
            contribution_type=self.contribution_type,
            period=date(2026, 9, 1),
            expected_amount=Decimal("10000.00"),
            status=ContributionSchedule.Status.PENDING,
        )

        ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("3000.00"),
            payment_date=self.payment_date,
        )

        ContributionPayment.objects.create(
            schedule=other_schedule,
            amount=Decimal("7000.00"),
            payment_date=self.payment_date,
        )

        total_paid = calculate_total_paid(
            self.schedule
        )

        self.assertEqual(
            total_paid,
            Decimal("3000.00"),
        )


    # ---------------------------------------------------------
    # calculate_remaining_balance() Tests
    # ---------------------------------------------------------

    def test_calculate_remaining_balance_returns_full_amount_when_unpaid(self):
        """
        Verify that an unpaid schedule has its full expected
        amount as the remaining balance.
        """

        remaining_balance = calculate_remaining_balance(
            self.schedule
        )

        self.assertEqual(
            remaining_balance,
            Decimal("10000.00"),
        )


    def test_calculate_remaining_balance_returns_correct_partial_balance(self):
        """
        Verify that the remaining balance is reduced correctly
        after a partial payment.
        """

        ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("3500.00"),
            payment_date=self.payment_date,
        )

        remaining_balance = calculate_remaining_balance(
            self.schedule
        )

        self.assertEqual(
            remaining_balance,
            Decimal("6500.00"),
        )


    def test_calculate_remaining_balance_returns_zero_when_paid_in_full(self):
        """
        Verify that the remaining balance becomes zero when
        the expected contribution has been fully paid.
        """

        ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("10000.00"),
            payment_date=self.payment_date,
        )

        remaining_balance = calculate_remaining_balance(
            self.schedule
        )

        self.assertEqual(
            remaining_balance,
            Decimal("0.00"),
        )


    def test_calculate_remaining_balance_never_returns_negative(self):
        """
        Verify that the remaining balance is never negative,
        even if existing database payments exceed the expected
        contribution amount.
        """

        ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("12000.00"),
            payment_date=self.payment_date,
        )

        remaining_balance = calculate_remaining_balance(
            self.schedule
        )

        self.assertEqual(
            remaining_balance,
            Decimal("0.00"),
        )


    # ---------------------------------------------------------
    # recalculate_schedule_status() Tests
    # ---------------------------------------------------------

    def test_recalculate_status_sets_pending_when_no_payment_exists(self):
        """
        Verify that a schedule with no payments is marked
        as PENDING.
        """

        self.schedule.status = (
            ContributionSchedule.Status.PARTIAL
        )

        self.schedule.save(
            update_fields=["status"]
        )

        recalculate_schedule_status(
            self.schedule
        )

        self.schedule.refresh_from_db()

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.PENDING,
        )


    def test_recalculate_status_sets_partial_after_partial_payment(self):
        """
        Verify that a schedule with payments below the expected
        amount is marked as PARTIAL.
        """

        ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("4000.00"),
            payment_date=self.payment_date,
        )

        self.schedule.status = (
            ContributionSchedule.Status.PENDING
        )

        self.schedule.save(
            update_fields=["status"]
        )

        recalculate_schedule_status(
            self.schedule
        )

        self.schedule.refresh_from_db()

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.PARTIAL,
        )


    def test_recalculate_status_sets_paid_when_fully_paid(self):
        """
        Verify that a schedule is marked as PAID when the
        total payments reach the expected amount.
        """

        ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("10000.00"),
            payment_date=self.payment_date,
        )

        recalculate_schedule_status(
            self.schedule
        )

        self.schedule.refresh_from_db()

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.PAID,
        )


    def test_recalculate_status_preserves_waived_status(self):
        """
        Verify that recalculating a waived schedule does not
        change its WAIVED status.
        """

        self.schedule.status = (
            ContributionSchedule.Status.WAIVED
        )

        self.schedule.save(
            update_fields=["status"]
        )

        recalculate_schedule_status(
            self.schedule
        )

        self.schedule.refresh_from_db()

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.WAIVED,
        )


    def test_recalculate_status_handles_multiple_payments(self):
        """
        Verify that status is calculated from the combined
        total of multiple payments.
        """

        ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("3000.00"),
            payment_date=self.payment_date,
        )

        ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("4000.00"),
            payment_date=self.payment_date,
        )

        recalculate_schedule_status(
            self.schedule
        )

        self.schedule.refresh_from_db()

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.PARTIAL,
        )


    # ---------------------------------------------------------
    # create_payment() Default Value Tests
    # ---------------------------------------------------------

    def test_create_payment_uses_default_payment_date(self):
        """
        Verify that create_payment() automatically uses today's
        date when payment_date is not supplied.
        """

        payment = create_payment(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
        )

        self.assertEqual(
            payment.payment_date,
            timezone.now().date(),
        )


    def test_create_payment_uses_cash_as_default_payment_method(self):
        """
        Verify that CASH is used as the default payment method.
        """

        payment = create_payment(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=self.payment_date,
        )

        self.assertEqual(
            payment.payment_method,
            ContributionPayment.PaymentMethod.CASH,
        )


    def test_create_payment_normalizes_empty_reference(self):
        """
        Verify that an empty or None reference is stored safely
        as an empty string.
        """

        payment = create_payment(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=self.payment_date,
            reference=None,
        )

        self.assertEqual(
            payment.reference,
            "",
        )


    def test_create_payment_normalizes_empty_notes(self):
        """
        Verify that an empty or None notes value is stored safely
        as an empty string.
        """

        payment = create_payment(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=self.payment_date,
            notes=None,
        )

        self.assertEqual(
            payment.notes,
            "",
        )


    # ---------------------------------------------------------
    # create_payment() Boundary Tests
    # ---------------------------------------------------------

    def test_payment_equal_to_remaining_balance_is_allowed(self):
        """
        Verify that a payment exactly equal to the remaining
        balance is accepted and marks the schedule as PAID.
        """

        ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("4000.00"),
            payment_date=self.payment_date,
        )

        payment = create_payment(
            schedule=self.schedule,
            amount=Decimal("6000.00"),
            payment_date=self.payment_date,
        )

        self.assertEqual(
            payment.amount,
            Decimal("6000.00"),
        )

        self.schedule.refresh_from_db()

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.PAID,
        )


    def test_payment_above_remaining_balance_is_rejected(self):
        """
        Verify that a payment greater than the remaining balance
        is rejected.
        """

        create_payment(
            schedule=self.schedule,
            amount=Decimal("6000.00"),
            payment_date=self.payment_date,
        )

        with self.assertRaises(ValueError):
            create_payment(
                schedule=self.schedule,
                amount=Decimal("4001.00"),
                payment_date=self.payment_date,
            )


    def test_rejected_payment_does_not_create_database_record(self):
        """
        Verify that a rejected payment does not create a
        ContributionPayment record.
        """

        with self.assertRaises(ValueError):
            create_payment(
                schedule=self.schedule,
                amount=Decimal("10001.00"),
                payment_date=self.payment_date,
            )

        self.assertEqual(
            ContributionPayment.objects.count(),
            0,
        )


    def test_rejected_payment_does_not_change_schedule_status(self):
        """
        Verify that a failed payment attempt does not alter
        the existing schedule status.
        """

        with self.assertRaises(ValueError):
            create_payment(
                schedule=self.schedule,
                amount=Decimal("10001.00"),
                payment_date=self.payment_date,
            )

        self.schedule.refresh_from_db()

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.PENDING,
        )


    # ---------------------------------------------------------
    # create_payment() Data Integrity Tests
    # ---------------------------------------------------------

    def test_create_payment_stores_payment_date(self):
        """
        Verify that the supplied payment date is stored exactly.
        """

        payment = create_payment(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=date(2026, 8, 25),
        )

        self.assertEqual(
            payment.payment_date,
            date(2026, 8, 25),
        )


    def test_create_payment_stores_reference(self):
        """
        Verify that a supplied payment reference is persisted.
        """

        payment = create_payment(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=self.payment_date,
            reference="MPESA-TEST-001",
        )

        self.assertEqual(
            payment.reference,
            "MPESA-TEST-001",
        )


    def test_create_payment_stores_notes(self):
        """
        Verify that supplied payment notes are persisted.
        """

        payment = create_payment(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=self.payment_date,
            notes="Test payment received.",
        )

        self.assertEqual(
            payment.notes,
            "Test payment received.",
        )


    def test_create_payment_increases_payment_count(self):
        """
        Verify that a successful payment creates exactly one
        new payment record.
        """

        self.assertEqual(
            ContributionPayment.objects.count(),
            0,
        )

        create_payment(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=self.payment_date,
        )

        self.assertEqual(
            ContributionPayment.objects.count(),
            1,
        )




class PaymentListViewTests(TestCase):

    def setUp(self):

        self.group = Group.objects.create(
            name="Payment List Group",
            code="PLG",
        )

        self.other_group = Group.objects.create(
            name="Other Payment Group",
            code="OPG",
        )

        # -----------------------------------------------------
        # Users
        # -----------------------------------------------------

        self.superuser = User.objects.create_superuser(
            email="superuser@example.com",
            password="TestPassword123!",
        )

        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="TestPassword123!",
        )

        self.chairman_user = User.objects.create_user(
            email="chairman@example.com",
            password="TestPassword123!",
        )

        self.treasurer_user = User.objects.create_user(
            email="treasurer@example.com",
            password="TestPassword123!",
        )

        self.member_user = User.objects.create_user(
            email="member@example.com",
            password="TestPassword123!",
        )

        self.other_group_admin = User.objects.create_user(
            email="otheradmin@example.com",
            password="TestPassword123!",
        )

        # -----------------------------------------------------
        # Memberships
        # -----------------------------------------------------

        self.admin_membership = Membership.objects.create(
            user=self.admin_user,
            group=self.group,
            membership_number="PLG-ADMIN-001",
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )

        self.chairman_membership = Membership.objects.create(
            user=self.chairman_user,
            group=self.group,
            membership_number="PLG-CHAIR-001",
            role=Membership.Role.CHAIRMAN,
            status=Membership.Status.ACTIVE,
        )

        self.treasurer_membership = Membership.objects.create(
            user=self.treasurer_user,
            group=self.group,
            membership_number="PLG-TREAS-001",
            role=Membership.Role.TREASURER,
            status=Membership.Status.ACTIVE,
        )

        self.member_membership = Membership.objects.create(
            user=self.member_user,
            group=self.group,
            membership_number="PLG-MEMBER-001",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

        self.other_admin_membership = Membership.objects.create(
            user=self.other_group_admin,
            group=self.other_group,
            membership_number="OPG-ADMIN-001",
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )

        # -----------------------------------------------------
        # Contribution Category
        # -----------------------------------------------------

        self.category = ContributionCategory.objects.create(
            name="Payment List Category",
        )

        # -----------------------------------------------------
        # Contribution Type
        # -----------------------------------------------------

        self.contribution_type = ContributionType.objects.create(
            category=self.category,
            name="Payment List Contribution",
            amount=Decimal("10000.00"),
            status=ContributionType.Status.ACTIVE,
        )

        # -----------------------------------------------------
        # Schedule
        # -----------------------------------------------------

        self.schedule = ContributionSchedule.objects.create(
            membership=self.member_membership,
            contribution_type=self.contribution_type,
            period=date(2026, 8, 1),
            expected_amount=Decimal("10000.00"),
            status=ContributionSchedule.Status.PARTIAL,
        )

        # -----------------------------------------------------
        # Payments
        # -----------------------------------------------------

        self.payment_one = ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("3000.00"),
            payment_date=date(2026, 8, 10),
            payment_method=ContributionPayment.PaymentMethod.MPESA,
            reference="MPESA-001",
        )

        self.payment_two = ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("2000.00"),
            payment_date=date(2026, 8, 15),
            payment_method=ContributionPayment.PaymentMethod.CASH,
            reference="CASH-001",
        )

        self.url = reverse(
            "contributions:payment-list",
            kwargs={
                "schedule_id": self.schedule.pk,
            },
        )

    # ---------------------------------------------------------
    # Access Tests
    # ---------------------------------------------------------

    def test_superuser_can_view_payment_list(self):

        self.client.force_login(
            self.superuser
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_group_admin_can_view_payment_list(self):

        self.client.force_login(
            self.admin_user
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_chairman_can_view_payment_list(self):

        self.client.force_login(
            self.chairman_user
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_treasurer_can_view_payment_list(self):

        self.client.force_login(
            self.treasurer_user
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_normal_member_cannot_view_payment_list(self):

        self.client.force_login(
            self.member_user
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_other_group_admin_cannot_view_payment_list(self):

        self.client.force_login(
            self.other_group_admin
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    # ---------------------------------------------------------
    # Payment Data Tests
    # ---------------------------------------------------------

    def test_payment_list_contains_payments(self):

        self.client.force_login(
            self.admin_user
        )

        response = self.client.get(
            self.url
        )

        self.assertContains(
            response,
            "MPESA-001",
        )

        self.assertContains(
            response,
            "CASH-001",
        )

    def test_payment_list_contains_correct_schedule(self):

        self.client.force_login(
            self.admin_user
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.context["schedule"],
            self.schedule,
        )

    def test_payment_list_calculates_total_paid_correctly(self):

        self.client.force_login(
            self.admin_user
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.context["total_paid"],
            Decimal("5000.00"),
        )

    def test_payment_list_calculates_remaining_balance_correctly(self):

        self.client.force_login(
            self.admin_user
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.context["remaining_balance"],
            Decimal("5000.00"),
        )

    def test_payment_list_orders_payments_by_latest_date(self):

        self.client.force_login(
            self.admin_user
        )

        response = self.client.get(
            self.url
        )

        payments = list(
            response.context["payments"]
        )

        self.assertEqual(
            payments[0],
            self.payment_two,
        )

        self.assertEqual(
            payments[1],
            self.payment_one,
        )



class PaymentDetailViewTests(TestCase):

    def setUp(self):

        self.group = Group.objects.create(
            name="Payment Detail Group",
            code="PDG",
        )

        self.other_group = Group.objects.create(
            name="Other Payment Detail Group",
            code="OPDG",
        )

        # -----------------------------------------------------
        # Users
        # -----------------------------------------------------

        self.superuser = User.objects.create_superuser(
            email="paymentdetail-superuser@example.com",
            password="TestPassword123!",
        )

        self.admin_user = User.objects.create_user(
            email="paymentdetail-admin@example.com",
            password="TestPassword123!",
        )

        self.chairman_user = User.objects.create_user(
            email="paymentdetail-chairman@example.com",
            password="TestPassword123!",
        )

        self.treasurer_user = User.objects.create_user(
            email="paymentdetail-treasurer@example.com",
            password="TestPassword123!",
        )

        self.member_user = User.objects.create_user(
            email="paymentdetail-member@example.com",
            password="TestPassword123!",
        )

        self.other_group_admin_user = User.objects.create_user(
            email="paymentdetail-other-admin@example.com",
            password="TestPassword123!",
        )

        # -----------------------------------------------------
        # Memberships
        # -----------------------------------------------------

        self.admin_membership = Membership.objects.create(
            user=self.admin_user,
            group=self.group,
            membership_number="PDG-ADMIN-001",
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )

        self.chairman_membership = Membership.objects.create(
            user=self.chairman_user,
            group=self.group,
            membership_number="PDG-CHAIR-001",
            role=Membership.Role.CHAIRMAN,
            status=Membership.Status.ACTIVE,
        )

        self.treasurer_membership = Membership.objects.create(
            user=self.treasurer_user,
            group=self.group,
            membership_number="PDG-TREAS-001",
            role=Membership.Role.TREASURER,
            status=Membership.Status.ACTIVE,
        )

        self.member_membership = Membership.objects.create(
            user=self.member_user,
            group=self.group,
            membership_number="PDG-MEMBER-001",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

        self.other_group_admin_membership = Membership.objects.create(
            user=self.other_group_admin_user,
            group=self.other_group,
            membership_number="OPDG-ADMIN-001",
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )

        # -----------------------------------------------------
        # Contribution data
        # -----------------------------------------------------

        self.category = ContributionCategory.objects.create(
            name="Payment Detail Category",
        )

        self.contribution_type = ContributionType.objects.create(
            category=self.category,
            name="Payment Detail Contribution",
            amount=Decimal("10000.00"),
            status=ContributionType.Status.ACTIVE,
        )

        self.schedule = ContributionSchedule.objects.create(
            membership=self.member_membership,
            contribution_type=self.contribution_type,
            period=date(2026, 8, 1),
            expected_amount=Decimal("10000.00"),
            status=ContributionSchedule.Status.PARTIAL,
        )

        self.payment = ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=date(2026, 8, 21),
            payment_method=ContributionPayment.PaymentMethod.MPESA,
            reference="MPESA-PD-001",
            notes="Payment detail test payment.",
        )

        self.url = reverse(
            "contributions:payment-detail",
            kwargs={
                "payment_id": self.payment.pk,
            },
        )

    # ---------------------------------------------------------
    # Access tests
    # ---------------------------------------------------------

    def test_superuser_can_view_payment_detail(self):

        self.client.force_login(
            self.superuser
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_group_admin_can_view_payment_detail(self):

        self.client.force_login(
            self.admin_user
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_chairman_can_view_payment_detail(self):

        self.client.force_login(
            self.chairman_user
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_treasurer_can_view_payment_detail(self):

        self.client.force_login(
            self.treasurer_user
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            200,
        )

    def test_normal_member_cannot_view_payment_detail(self):

        self.client.force_login(
            self.member_user
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_other_group_admin_cannot_view_payment_detail(self):

        self.client.force_login(
            self.other_group_admin_user
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    # ---------------------------------------------------------
    # Data tests
    # ---------------------------------------------------------

    def test_payment_detail_returns_correct_payment(self):

        self.client.force_login(
            self.admin_user
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.context["payment"],
            self.payment,
        )

    def test_payment_detail_contains_payment_reference(self):

        self.client.force_login(
            self.admin_user
        )

        response = self.client.get(
            self.url
        )

        self.assertContains(
            response,
            "MPESA-PD-001",
        )

    def test_payment_detail_contains_payment_notes(self):

        self.client.force_login(
            self.admin_user
        )

        response = self.client.get(
            self.url
        )

        self.assertContains(
            response,
            "Payment detail test payment.",
        )

    def test_payment_detail_returns_schedule(self):

        self.client.force_login(
            self.admin_user
        )

        response = self.client.get(
            self.url
        )

        self.assertEqual(
            response.context["schedule"],
            self.schedule,
        )


class ContributionWaiverServiceTests(TestCase):

    def setUp(self):

        self.group = Group.objects.create(
            name="Waiver Test Group",
            code="WTG",
        )

        self.admin_user = User.objects.create_user(
            email="waiver-admin@example.com",
            password="TestPassword123!",
        )

        self.member_user = User.objects.create_user(
            email="waiver-member@example.com",
            password="TestPassword123!",
        )

        self.admin_membership = Membership.objects.create(
            user=self.admin_user,
            group=self.group,
            membership_number="WTG-ADMIN-001",
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )

        self.member_membership = Membership.objects.create(
            user=self.member_user,
            group=self.group,
            membership_number="WTG-MEMBER-001",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

        self.category = ContributionCategory.objects.create(
            name="Waiver Category",
        )

        self.contribution_type = ContributionType.objects.create(
            category=self.category,
            name="Waiver Contribution",
            amount=Decimal("10000.00"),
            status=ContributionType.Status.ACTIVE,
        )

        self.schedule = ContributionSchedule.objects.create(
            membership=self.member_membership,
            contribution_type=self.contribution_type,
            period=date(2026, 8, 1),
            expected_amount=Decimal("10000.00"),
            status=ContributionSchedule.Status.PENDING,
        )

    def test_pending_schedule_can_be_waived(self):

        waive_contribution(
            schedule=self.schedule,
            waived_by=self.admin_user,
            reason="Approved exemption.",
        )

        self.schedule.refresh_from_db()

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.WAIVED,
        )

    def test_waiver_records_user(self):

        waive_contribution(
            schedule=self.schedule,
            waived_by=self.admin_user,
            reason="Approved exemption.",
        )

        self.schedule.refresh_from_db()

        self.assertEqual(
            self.schedule.waived_by,
            self.admin_user,
        )

    def test_waiver_records_datetime(self):

        waive_contribution(
            schedule=self.schedule,
            waived_by=self.admin_user,
            reason="Approved exemption.",
        )

        self.schedule.refresh_from_db()

        self.assertIsNotNone(
            self.schedule.waived_at,
        )

    def test_waiver_records_reason(self):

        reason = "Member was officially exempted."

        waive_contribution(
            schedule=self.schedule,
            waived_by=self.admin_user,
            reason=reason,
        )

        self.schedule.refresh_from_db()

        self.assertEqual(
            self.schedule.waived_reason,
            reason,
        )

    def test_reason_is_required(self):

        with self.assertRaises(
            ValueError
        ):

            waive_contribution(
                schedule=self.schedule,
                waived_by=self.admin_user,
                reason="",
            )

    def test_whitespace_only_reason_is_rejected(self):

        with self.assertRaises(
            ValueError
        ):

            waive_contribution(
                schedule=self.schedule,
                waived_by=self.admin_user,
                reason="   ",
            )

    def test_already_waived_schedule_cannot_be_waived_again(self):

        self.schedule.status = (
            ContributionSchedule.Status.WAIVED
        )

        self.schedule.save(
            update_fields=["status"]
        )

        with self.assertRaises(
            ValueError
        ):

            waive_contribution(
                schedule=self.schedule,
                waived_by=self.admin_user,
                reason="Second waiver.",
            )

    def test_paid_schedule_cannot_be_waived(self):

        self.schedule.status = (
            ContributionSchedule.Status.PAID
        )

        self.schedule.save(
            update_fields=["status"]
        )

        with self.assertRaises(
            ValueError
        ):

            waive_contribution(
                schedule=self.schedule,
                waived_by=self.admin_user,
                reason="Attempt to waive paid schedule.",
            )

    def test_partial_schedule_can_be_waived(self):

        self.schedule.status = (
            ContributionSchedule.Status.PARTIAL
        )

        self.schedule.save(
            update_fields=["status"]
        )

        ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=date(2026, 8, 15),
        )

        waive_contribution(
            schedule=self.schedule,
            waived_by=self.admin_user,
            reason="Remaining balance waived.",
        )

        self.schedule.refresh_from_db()

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.WAIVED,
        )

    def test_partial_payment_is_preserved_after_waiver(self):

        self.schedule.status = (
            ContributionSchedule.Status.PARTIAL
        )

        self.schedule.save(
            update_fields=["status"]
        )

        payment = ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=date(2026, 8, 15),
        )

        waive_contribution(
            schedule=self.schedule,
            waived_by=self.admin_user,
            reason="Remaining balance waived.",
        )

        self.assertTrue(
            ContributionPayment.objects.filter(
                pk=payment.pk
            ).exists()
        )

    def test_waiver_creates_history_record(self):

        waive_contribution(
            schedule=self.schedule,
            waived_by=self.admin_user,
            reason="Approved exemption.",
        )

        self.assertEqual(
            ContributionWaiver.objects.count(),
            1,
        )

    def test_waiver_history_records_correct_schedule(self):

        waive_contribution(
            schedule=self.schedule,
            waived_by=self.admin_user,
            reason="Approved exemption.",
        )

        waiver = ContributionWaiver.objects.get(
            schedule=self.schedule
        )

        self.assertEqual(
            waiver.schedule,
            self.schedule,
        )

    def test_waiver_history_records_waived_action(self):

        waive_contribution(
            schedule=self.schedule,
            waived_by=self.admin_user,
            reason="Approved exemption.",
        )

        waiver = ContributionWaiver.objects.get(
            schedule=self.schedule
        )

        self.assertEqual(
            waiver.action,
            ContributionWaiver.Action.WAIVED,
        )

    def test_waiver_history_records_reason(self):

        reason = "Member was officially exempted."

        waive_contribution(
            schedule=self.schedule,
            waived_by=self.admin_user,
            reason=reason,
        )

        waiver = ContributionWaiver.objects.get(
            schedule=self.schedule
        )

        self.assertEqual(
            waiver.reason,
            reason,
        )

    def test_waiver_history_records_performed_by(self):

        waive_contribution(
            schedule=self.schedule,
            waived_by=self.admin_user,
            reason="Approved exemption.",
        )

        waiver = ContributionWaiver.objects.get(
            schedule=self.schedule
        )

        self.assertEqual(
            waiver.performed_by,
            self.admin_user,
        )

    def test_waiver_history_records_performed_at(self):

        waive_contribution(
            schedule=self.schedule,
            waived_by=self.admin_user,
            reason="Approved exemption.",
        )

        waiver = ContributionWaiver.objects.get(
            schedule=self.schedule
        )

        self.assertIsNotNone(
            waiver.performed_at,
        )


    def test_waived_schedule_without_payments_is_restored_to_pending(self):

        waive_contribution(
            schedule=self.schedule,
            waived_by=self.admin_user,
            reason="Temporary exemption.",
        )

        restore_contribution(
            schedule=self.schedule,
            restored_by=self.admin_user,
            reason="Member resumed contribution.",
        )

        self.schedule.refresh_from_db()

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.PENDING,
        )

    def test_waived_schedule_with_partial_payment_is_restored_to_partial(self):

        ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("5000.00"),
            payment_date=date(2026, 8, 15),
        )

        waive_contribution(
            schedule=self.schedule,
            waived_by=self.admin_user,
            reason="Remaining balance temporarily waived.",
        )

        restore_contribution(
            schedule=self.schedule,
            restored_by=self.admin_user,
            reason="Member resumed contribution.",
        )

        self.schedule.refresh_from_db()

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.PARTIAL,
        )

    def test_waived_schedule_with_full_payment_is_restored_to_paid(self):

        ContributionPayment.objects.create(
            schedule=self.schedule,
            amount=Decimal("10000.00"),
            payment_date=date(2026, 8, 15),
        )

        waive_contribution(
            schedule=self.schedule,
            waived_by=self.admin_user,
            reason="Temporary exemption.",
        )

        restore_contribution(
            schedule=self.schedule,
            restored_by=self.admin_user,
            reason="Contribution status reviewed.",
        )

        self.schedule.refresh_from_db()

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.PAID,
        )

    def test_non_waived_schedule_cannot_be_restored(self):

        with self.assertRaises(ValueError):

            restore_contribution(
                schedule=self.schedule,
                restored_by=self.admin_user,
                reason="Attempted restore.",
            )

        self.schedule.refresh_from_db()

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.PENDING,
        )

    def test_restore_requires_reason(self):

        waive_contribution(
            schedule=self.schedule,
            waived_by=self.admin_user,
            reason="Temporary exemption.",
        )

        with self.assertRaises(ValueError):

            restore_contribution(
                schedule=self.schedule,
                restored_by=self.admin_user,
                reason="",
            )

        self.schedule.refresh_from_db()

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.WAIVED,
        )

    def test_whitespace_only_restore_reason_is_rejected(self):

        waive_contribution(
            schedule=self.schedule,
            waived_by=self.admin_user,
            reason="Temporary exemption.",
        )

        with self.assertRaises(ValueError):

            restore_contribution(
                schedule=self.schedule,
                restored_by=self.admin_user,
                reason="   ",
            )

        self.schedule.refresh_from_db()

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.WAIVED,
        )





class ContributionWaiverViewTests(TestCase):

    def setUp(self):

        self.group = Group.objects.create(
            name="Waiver View Test Group",
            code="WV",
        )

        self.other_group = Group.objects.create(
            name="Other Waiver Test Group",
            code="OWV",
        )

        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="TestPassword123!",
        )

        self.member_user = User.objects.create_user(
            email="member@example.com",
            password="TestPassword123!",
        )

        self.other_admin_user = User.objects.create_user(
            email="other-admin@example.com",
            password="TestPassword123!",
        )

        self.admin_membership = Membership.objects.create(
            user=self.admin_user,
            group=self.group,
            membership_number="WV-ADMIN-001",
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )

        self.member_membership = Membership.objects.create(
            user=self.member_user,
            group=self.group,
            membership_number="WV-MEMBER-001",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

        self.other_admin_membership = Membership.objects.create(
            user=self.other_admin_user,
            group=self.other_group,
            membership_number="OWV-ADMIN-001",
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )

        self.category = ContributionCategory.objects.create(
            name="Waiver View Category",
        )

        self.contribution_type = ContributionType.objects.create(
            category=self.category,
            name="Waiver View Contribution",
            amount=Decimal("10000.00"),
            status=ContributionType.Status.ACTIVE,
        )

        self.schedule = ContributionSchedule.objects.create(
            membership=self.member_membership,
            contribution_type=self.contribution_type,
            period=date(2026, 8, 1),
            expected_amount=Decimal("10000.00"),
            status=ContributionSchedule.Status.PENDING,
        )

    def get_waive_url(self):

        return reverse(
            "contributions:waive-contribution",
            kwargs={
                "schedule_id": self.schedule.pk,
            },
        )

    def test_admin_can_access_waiver_page(self):

        self.client.force_login(
            self.admin_user
        )

        response = self.client.get(
            self.get_waive_url()
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertTemplateUsed(
            response,
            "contributions/schedules/waive.html",
        )

    def test_admin_can_waive_pending_schedule(self):

        self.client.force_login(
            self.admin_user
        )

        response = self.client.post(
            self.get_waive_url(),
            {
                "reason": (
                    "Member approved for contribution exemption."
                ),
            },
        )

        self.schedule.refresh_from_db()

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.WAIVED,
        )

        self.assertEqual(
            self.schedule.waived_by,
            self.admin_user,
        )

        self.assertEqual(
            self.schedule.waived_reason,
            "Member approved for contribution exemption.",
        )

        self.assertIsNotNone(
            self.schedule.waived_at,
        )

    def test_member_cannot_waive_contribution(self):

        self.client.force_login(
            self.member_user
        )

        response = self.client.get(
            self.get_waive_url()
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_other_group_admin_cannot_waive_contribution(self):

        self.client.force_login(
            self.other_admin_user
        )

        response = self.client.get(
            self.get_waive_url()
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_waiver_requires_reason(self):

        self.client.force_login(
            self.admin_user
        )

        response = self.client.post(
            self.get_waive_url(),
            {
                "reason": "",
            },
        )

        self.schedule.refresh_from_db()

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.PENDING,
        )

        self.assertContains(
            response,
            "This field is required.",
        )

    def test_paid_schedule_cannot_be_waived(self):

        self.schedule.status = (
            ContributionSchedule.Status.PAID
        )

        self.schedule.save(
            update_fields=["status"]
        )

        self.client.force_login(
            self.admin_user
        )

        response = self.client.post(
            self.get_waive_url(),
            {
                "reason": "Attempting to waive paid contribution.",
            },
        )

        self.schedule.refresh_from_db()

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.PAID,
        )

    def test_already_waived_schedule_redirects(self):

        self.schedule.status = (
            ContributionSchedule.Status.WAIVED
        )

        self.schedule.save(
            update_fields=["status"]
        )

        self.client.force_login(
            self.admin_user
        )

        response = self.client.get(
            self.get_waive_url()
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.schedule.refresh_from_db()

        self.assertEqual(
            self.schedule.status,
            ContributionSchedule.Status.WAIVED,
        )

    def test_schedule_detail_shows_waiver_history(self):

        waive_contribution(
            schedule=self.schedule,
            waived_by=self.admin_user,
            reason="Approved exemption.",
        )

        self.client.force_login(
            self.admin_user
        )

        response = self.client.get(
            reverse(
                "contributions:schedule-detail",
                kwargs={
                    "schedule_id": self.schedule.pk,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "Approved exemption.",
        )


    def test_schedule_detail_shows_restore_history(self):

        waive_contribution(
            schedule=self.schedule,
            waived_by=self.admin_user,
            reason="Temporary exemption.",
        )

        restore_contribution(
            schedule=self.schedule,
            restored_by=self.admin_user,
            reason="Contribution restored.",
        )

        self.client.force_login(
            self.admin_user
        )

        response = self.client.get(
            reverse(
                "contributions:schedule-detail",
                kwargs={
                    "schedule_id": self.schedule.pk,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "Contribution restored.",
        )

# =============================================================
# Cross-Group Security Tests
# =============================================================
class ContributionCrossGroupSecurityTests(TestCase):

    def setUp(self):
        # -----------------------------------------------------
        # Groups
        # -----------------------------------------------------

        self.group_a = Group.objects.create(
            name="Security Group A",
            code="SGA",
        )

        self.group_b = Group.objects.create(
            name="Security Group B",
            code="SGB",
        )

        # -----------------------------------------------------
        # Users
        # -----------------------------------------------------

        self.admin_a = User.objects.create_user(
            email="security-admin-a@example.com",
            password="TestPassword123!",
        )

        self.admin_b = User.objects.create_user(
            email="security-admin-b@example.com",
            password="TestPassword123!",
        )

        # -----------------------------------------------------
        # Memberships
        # -----------------------------------------------------

        self.membership_a = Membership.objects.create(
            user=self.admin_a,
            group=self.group_a,
            membership_number="SGA-ADMIN-001",
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )

        self.membership_b = Membership.objects.create(
            user=self.admin_b,
            group=self.group_b,
            membership_number="SGB-ADMIN-001",
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )

        # -----------------------------------------------------
        # Contribution category
        # -----------------------------------------------------

        self.category = ContributionCategory.objects.create(
            name="Cross Group Security Category",
        )

        # -----------------------------------------------------
        # Contribution type
        # -----------------------------------------------------

        self.contribution_type = ContributionType.objects.create(
            category=self.category,
            name="Cross Group Security Contribution",
            amount=Decimal("10000.00"),
            status=ContributionType.Status.ACTIVE,
        )

        # -----------------------------------------------------
        # Schedule in Group B
        # -----------------------------------------------------

        self.schedule_b = ContributionSchedule.objects.create(
            membership=self.membership_b,
            contribution_type=self.contribution_type,
            period=date(2026, 8, 1),
            expected_amount=Decimal("10000.00"),
            status=ContributionSchedule.Status.PARTIAL,
        )

        # -----------------------------------------------------
        # Payment belonging to Group B
        # -----------------------------------------------------

        self.payment_b = ContributionPayment.objects.create(
            schedule=self.schedule_b,
            amount=Decimal("5000.00"),
            payment_date=date(2026, 8, 15),
            payment_method=ContributionPayment.PaymentMethod.CASH,
            reference="SGB-SECURITY-001",
            notes="Group B security test payment.",
        )

    # ---------------------------------------------------------
    # Schedule Detail
    # ---------------------------------------------------------

    def test_group_a_admin_cannot_view_group_b_schedule(self):

        self.client.force_login(
            self.admin_a
        )

        response = self.client.get(
            reverse(
                "contributions:schedule-detail",
                kwargs={
                    "schedule_id": self.schedule_b.pk,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    # ---------------------------------------------------------
    # Create Payment
    # ---------------------------------------------------------

    def test_group_a_admin_cannot_create_payment_for_group_b(self):

        self.client.force_login(
            self.admin_a
        )

        response = self.client.get(
            reverse(
                "contributions:create-payment",
                kwargs={
                    "schedule_id": self.schedule_b.pk,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.assertEqual(
            ContributionPayment.objects.filter(
                schedule=self.schedule_b,
            ).count(),
            1,
        )

    # ---------------------------------------------------------
    # Edit Payment
    # ---------------------------------------------------------

    def test_group_a_admin_cannot_edit_group_b_payment(self):

        self.client.force_login(
            self.admin_a
        )

        response = self.client.get(
            reverse(
                "contributions:payment-edit",
                kwargs={
                    "payment_id": self.payment_b.pk,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.payment_b.refresh_from_db()

        self.assertEqual(
            self.payment_b.amount,
            Decimal("5000.00"),
        )

    # ---------------------------------------------------------
    # Delete Payment
    # ---------------------------------------------------------

    def test_group_a_admin_cannot_delete_group_b_payment(self):

        self.client.force_login(
            self.admin_a
        )

        response = self.client.post(
            reverse(
                "contributions:payment-delete",
                kwargs={
                    "payment_id": self.payment_b.pk,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.assertTrue(
            ContributionPayment.objects.filter(
                pk=self.payment_b.pk,
            ).exists()
        )

    # ---------------------------------------------------------
    # Waive Contribution
    # ---------------------------------------------------------

    def test_group_a_admin_cannot_waive_group_b_schedule(self):

        self.client.force_login(
            self.admin_a
        )

        response = self.client.get(
            reverse(
                "contributions:waive-contribution",
                kwargs={
                    "schedule_id": self.schedule_b.pk,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.schedule_b.refresh_from_db()

        self.assertEqual(
            self.schedule_b.status,
            ContributionSchedule.Status.PARTIAL,
        )

    # ---------------------------------------------------------
    # Restore Contribution
    # ---------------------------------------------------------

    def test_group_a_admin_cannot_restore_group_b_schedule(self):

        self.schedule_b.status = (
            ContributionSchedule.Status.WAIVED
        )

        self.schedule_b.save(
            update_fields=["status"]
        )

        self.client.force_login(
            self.admin_a
        )

        response = self.client.get(
            reverse(
                "contributions:restore-contribution",
                kwargs={
                    "schedule_id": self.schedule_b.pk,
                },
            )
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.schedule_b.refresh_from_db()

        self.assertEqual(
            self.schedule_b.status,
            ContributionSchedule.Status.WAIVED,
        )
    

# =============================================================
# Dashboard and Schedule List Group Isolation Tests
# =============================================================

class ContributionListGroupIsolationTests(TestCase):

    def setUp(self):
        # ---------------------------------------------------------
        # Groups
        # ---------------------------------------------------------

        self.group_a = Group.objects.create(
            name="Dashboard Security Group A",
            code="DSGA",
        )

        self.group_b = Group.objects.create(
            name="Dashboard Security Group B",
            code="DSGB",
        )

        # ---------------------------------------------------------
        # Users
        # ---------------------------------------------------------

        self.admin_a = User.objects.create_user(
            email="dashboard-admin-a@example.com",
            password="TestPassword123!",
        )

        self.admin_b = User.objects.create_user(
            email="dashboard-admin-b@example.com",
            password="TestPassword123!",
        )

        # ---------------------------------------------------------
        # Memberships
        # ---------------------------------------------------------

        self.membership_a = Membership.objects.create(
            user=self.admin_a,
            group=self.group_a,
            membership_number="DSGA-ADMIN-001",
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )

        self.membership_b = Membership.objects.create(
            user=self.admin_b,
            group=self.group_b,
            membership_number="DSGB-ADMIN-001",
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )

        # ---------------------------------------------------------
        # Contribution type
        # ---------------------------------------------------------

        self.category = ContributionCategory.objects.create(
            name="List Isolation Category",
        )

        self.contribution_type = ContributionType.objects.create(
            category=self.category,
            name="List Isolation Contribution",
            amount=Decimal("10000.00"),
            status=ContributionType.Status.ACTIVE,
        )

        # ---------------------------------------------------------
        # Current period
        # ---------------------------------------------------------

        self.period = date(
            timezone.now().year,
            timezone.now().month,
            1,
        )

        # ---------------------------------------------------------
        # Group A schedule
        # ---------------------------------------------------------

        self.schedule_a = ContributionSchedule.objects.create(
            membership=self.membership_a,
            contribution_type=self.contribution_type,
            period=self.period,
            expected_amount=Decimal("10000.00"),
            status=ContributionSchedule.Status.PENDING,
        )

        # ---------------------------------------------------------
        # Group B schedule
        # ---------------------------------------------------------

        self.schedule_b = ContributionSchedule.objects.create(
            membership=self.membership_b,
            contribution_type=self.contribution_type,
            period=self.period,
            expected_amount=Decimal("10000.00"),
            status=ContributionSchedule.Status.PENDING,
        )

    # ---------------------------------------------------------
    # Dashboard Tests
    # ---------------------------------------------------------

    def test_group_a_admin_dashboard_does_not_show_group_b_schedule(self):
        """
        An admin of Group A must not see Group B schedules
        on the contribution dashboard.
        """

        self.client.force_login(
            self.admin_a
        )

        response = self.client.get(
            reverse(
                "contributions:dashboard"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        # Group A schedule must be visible.
        self.assertContains(
            response,
            self.schedule_a.membership.membership_number,
        )

        # Group B schedule must not be visible.
        self.assertNotContains(
            response,
            self.schedule_b.membership.membership_number,
        )

    def test_group_b_admin_dashboard_does_not_show_group_a_schedule(self):
        """
        An admin of Group B must not see Group A schedules
        on the contribution dashboard.
        """

        self.client.force_login(
            self.admin_b
        )

        response = self.client.get(
            reverse(
                "contributions:dashboard"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        # Group B schedule must be visible.
        self.assertContains(
            response,
            self.schedule_b.membership.membership_number,
        )

        # Group A schedule must not be visible.
        self.assertNotContains(
            response,
            self.schedule_a.membership.membership_number,
        )

    # ---------------------------------------------------------
    # Schedule List Tests
    # ---------------------------------------------------------

    def test_group_a_schedule_list_does_not_show_group_b_schedule(self):
        """
        An admin of Group A must not see Group B schedules
        on the schedule list.
        """

        self.client.force_login(
            self.admin_a
        )

        response = self.client.get(
            reverse(
                "contributions:schedule-list"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        # Group A schedule must be visible.
        self.assertContains(
            response,
            self.schedule_a.membership.membership_number,
        )

        # Group B schedule must not be visible.
        self.assertNotContains(
            response,
            self.schedule_b.membership.membership_number,
        )

    def test_group_b_schedule_list_does_not_show_group_a_schedule(self):
        """
        An admin of Group B must not see Group A schedules
        on the schedule list.
        """

        self.client.force_login(
            self.admin_b
        )

        response = self.client.get(
            reverse(
                "contributions:schedule-list"
            )
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        # Group B schedule must be visible.
        self.assertContains(
            response,
            self.schedule_b.membership.membership_number,
        )

        # Group A schedule must not be visible.
        self.assertNotContains(
            response,
            self.schedule_a.membership.membership_number,
        )


# =============================================================
# Inactive and Suspended Membership Security Tests
# =============================================================

class ContributionInactiveMembershipSecurityTests(TestCase):

    def setUp(self):
        self.group = Group.objects.create(
            name="Membership Security Group",
            code="MSG",
        )

        self.user = User.objects.create_user(
            email="inactive-membership@example.com",
            password="TestPassword123!",
        )

        self.membership = Membership.objects.create(
            user=self.user,
            group=self.group,
            membership_number="MSG-ADMIN-001",
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )

        self.category = ContributionCategory.objects.create(
            name="Inactive Membership Category",
        )

        self.contribution_type = ContributionType.objects.create(
            category=self.category,
            name="Inactive Membership Contribution",
            amount=Decimal("10000.00"),
            status=ContributionType.Status.ACTIVE,
        )

        self.schedule = ContributionSchedule.objects.create(
            membership=self.membership,
            contribution_type=self.contribution_type,
            period=date(2026, 9, 1),
            expected_amount=Decimal("10000.00"),
            status=ContributionSchedule.Status.PENDING,
        )

    def test_inactive_membership_cannot_view_schedule(self):
        """
        An inactive membership must not access
        contribution schedule details.
        """

        self.membership.status = Membership.Status.INACTIVE
        self.membership.save(update_fields=["status"])

        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "contributions:schedule-detail",
                kwargs={"schedule_id": self.schedule.pk},
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_suspended_membership_cannot_view_schedule(self):
        """
        A suspended membership must not access
        contribution schedule details.
        """

        self.membership.status = Membership.Status.SUSPENDED
        self.membership.save(update_fields=["status"])

        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "contributions:schedule-detail",
                kwargs={"schedule_id": self.schedule.pk},
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_inactive_membership_cannot_create_payment(self):
        """
        An inactive membership must not create
        a contribution payment.
        """

        self.membership.status = Membership.Status.INACTIVE
        self.membership.save(update_fields=["status"])

        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "contributions:create-payment",
                kwargs={"schedule_id": self.schedule.pk},
            )
        )

        self.assertEqual(response.status_code, 403)

        self.assertEqual(
            ContributionPayment.objects.filter(
                schedule=self.schedule
            ).count(),
            0,
        )

    def test_suspended_membership_cannot_create_payment(self):
        """
        A suspended membership must not create
        a contribution payment.
        """

        self.membership.status = Membership.Status.SUSPENDED
        self.membership.save(update_fields=["status"])

        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "contributions:create-payment",
                kwargs={"schedule_id": self.schedule.pk},
            )
        )

        self.assertEqual(response.status_code, 403)

        self.assertEqual(
            ContributionPayment.objects.filter(
                schedule=self.schedule
            ).count(),
            0,
        )


# =============================================================
# Inactive User Security Tests
# =============================================================

class ContributionInactiveUserSecurityTests(TestCase):

    def setUp(self):
        self.group = Group.objects.create(
            name="Inactive User Security Group",
            code="IUS",
        )

        self.user = User.objects.create_user(
            email="inactive-user@example.com",
            password="TestPassword123!",
        )

        self.membership = Membership.objects.create(
            user=self.user,
            group=self.group,
            membership_number="IUS-ADMIN-001",
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )

        self.category = ContributionCategory.objects.create(
            name="Inactive User Category",
        )

        self.contribution_type = ContributionType.objects.create(
            category=self.category,
            name="Inactive User Contribution",
            amount=Decimal("10000.00"),
            status=ContributionType.Status.ACTIVE,
        )

        self.schedule = ContributionSchedule.objects.create(
            membership=self.membership,
            contribution_type=self.contribution_type,
            period=date(2026, 9, 1),
            expected_amount=Decimal("10000.00"),
            status=ContributionSchedule.Status.PENDING,
        )

    def test_inactive_user_cannot_view_schedule(self):
        """
        An inactive user should not access contribution schedules.

        Django authentication redirects inactive users to the login page
        before the contribution view is reached.
        """

        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "contributions:schedule-detail",
                kwargs={"schedule_id": self.schedule.pk},
            )
        )

        # Inactive users are redirected to the login page.
        self.assertEqual(response.status_code, 302)

        # Confirm that the redirect destination is the login page.
        self.assertIn(
            "/accounts/login/",
            response.get("Location", ""),
        )

    def test_inactive_user_cannot_create_payment(self):
        """
        An inactive user should not be able to access payment creation.

        Django authentication redirects inactive users to the login page
        before the contribution view is reached.
        """

        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "contributions:create-payment",
                kwargs={"schedule_id": self.schedule.pk},
            )
        )

        # Inactive users are redirected to the login page.
        self.assertEqual(response.status_code, 302)

        # Confirm that the redirect destination is the login page.
        self.assertIn(
            "/accounts/login/",
            response.get("Location", ""),
        )

        # Confirm that no payment was created.
        self.assertEqual(
            ContributionPayment.objects.filter(
                schedule=self.schedule
            ).count(),
            0,
        )

    def test_inactive_user_cannot_view_payment_list(self):
        """
        An inactive user should not access the payment list.

        Django authentication redirects inactive users to the login page
        before the contribution view is reached.
        """

        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "contributions:payment-list",
                kwargs={"schedule_id": self.schedule.pk},
            )
        )

        # Inactive users are redirected to the login page.
        self.assertEqual(response.status_code, 302)

        # Confirm that the redirect destination is the login page.
        self.assertIn(
            "/accounts/login/",
            response.get("Location", ""),
        )


# =============================================================
# Role Boundary Security Tests
# =============================================================

class ContributionRoleBoundarySecurityTests(TestCase):

    def setUp(self):
        self.group = Group.objects.create(
            name="Role Security Group",
            code="RSG",
        )

        # ---------------------------------------------------------
        # Create users with different roles
        # ---------------------------------------------------------

        self.secretary = User.objects.create_user(
            email="role-secretary@example.com",
            password="TestPassword123!",
        )

        self.member = User.objects.create_user(
            email="role-member@example.com",
            password="TestPassword123!",
        )

        # ---------------------------------------------------------
        # Create memberships
        # ---------------------------------------------------------

        self.secretary_membership = Membership.objects.create(
            user=self.secretary,
            group=self.group,
            membership_number="RSG-SECRETARY-001",
            role=Membership.Role.SECRETARY,
            status=Membership.Status.ACTIVE,
        )

        self.member_membership = Membership.objects.create(
            user=self.member,
            group=self.group,
            membership_number="RSG-MEMBER-001",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

        # ---------------------------------------------------------
        # Create contribution data
        # ---------------------------------------------------------

        self.category = ContributionCategory.objects.create(
            name="Role Security Category",
        )

        self.contribution_type = ContributionType.objects.create(
            category=self.category,
            name="Role Security Contribution",
            amount=Decimal("10000.00"),
            status=ContributionType.Status.ACTIVE,
        )

        self.schedule_secretary = ContributionSchedule.objects.create(
            membership=self.secretary_membership,
            contribution_type=self.contribution_type,
            period=date(2026, 9, 1),
            expected_amount=Decimal("10000.00"),
            status=ContributionSchedule.Status.PENDING,
        )

        self.schedule_member = ContributionSchedule.objects.create(
            membership=self.member_membership,
            contribution_type=self.contribution_type,
            period=date(2026, 9, 1),
            expected_amount=Decimal("10000.00"),
            status=ContributionSchedule.Status.PENDING,
        )

    # =============================================================
    # SECRETARY SECURITY TESTS
    # =============================================================

    def test_secretary_cannot_view_schedule(self):
        """
        SECRETARY should not be allowed to access contribution
        schedule management.
        """

        self.client.force_login(self.secretary)

        response = self.client.get(
            reverse(
                "contributions:schedule-detail",
                kwargs={"schedule_id": self.schedule_secretary.pk},
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_secretary_cannot_create_payment(self):
        """
        SECRETARY should not be allowed to access payment creation.
        """

        self.client.force_login(self.secretary)

        response = self.client.get(
            reverse(
                "contributions:create-payment",
                kwargs={"schedule_id": self.schedule_secretary.pk},
            )
        )

        self.assertEqual(response.status_code, 403)

        # Confirm that no payment was created.
        self.assertEqual(
            ContributionPayment.objects.filter(
                schedule=self.schedule_secretary
            ).count(),
            0,
        )

    def test_secretary_cannot_view_payment_list(self):
        """
        SECRETARY should not be allowed to view payment management.
        """

        self.client.force_login(self.secretary)

        response = self.client.get(
            reverse(
                "contributions:payment-list",
                kwargs={"schedule_id": self.schedule_secretary.pk},
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_secretary_cannot_waive_contribution(self):
        """
        SECRETARY should not be allowed to waive contributions.
        """

        self.client.force_login(self.secretary)

        response = self.client.get(
            reverse(
                "contributions:waive-contribution",
                kwargs={"schedule_id": self.schedule_secretary.pk},
            )
        )

        self.assertEqual(response.status_code, 403)

        self.schedule_secretary.refresh_from_db()

        # Confirm that the contribution was not waived.
        self.assertEqual(
            self.schedule_secretary.status,
            ContributionSchedule.Status.PENDING,
        )

    # =============================================================
    # MEMBER SECURITY TESTS
    # =============================================================

    def test_member_cannot_view_schedule(self):
        """
        MEMBER should not be allowed to access contribution
        schedule management.
        """

        self.client.force_login(self.member)

        response = self.client.get(
            reverse(
                "contributions:schedule-detail",
                kwargs={"schedule_id": self.schedule_member.pk},
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_member_cannot_create_payment(self):
        """
        MEMBER should not be allowed to access payment creation.
        """

        self.client.force_login(self.member)

        response = self.client.get(
            reverse(
                "contributions:create-payment",
                kwargs={"schedule_id": self.schedule_member.pk},
            )
        )

        self.assertEqual(response.status_code, 403)

        # Confirm that no payment was created.
        self.assertEqual(
            ContributionPayment.objects.filter(
                schedule=self.schedule_member
            ).count(),
            0,
        )

    def test_member_cannot_view_payment_list(self):
        """
        MEMBER should not be allowed to view payment management.
        """

        self.client.force_login(self.member)

        response = self.client.get(
            reverse(
                "contributions:payment-list",
                kwargs={"schedule_id": self.schedule_member.pk},
            )
        )

        self.assertEqual(response.status_code, 403)

    def test_member_cannot_waive_contribution(self):
        """
        MEMBER should not be allowed to waive contributions.
        """

        self.client.force_login(self.member)

        response = self.client.get(
            reverse(
                "contributions:waive-contribution",
                kwargs={"schedule_id": self.schedule_member.pk},
            )
        )

        self.assertEqual(response.status_code, 403)

        self.schedule_member.refresh_from_db()

        # Confirm that the contribution was not waived.
        self.assertEqual(
            self.schedule_member.status,
            ContributionSchedule.Status.PENDING,
        )


# =============================================================
# Positive Role Security Tests
# =============================================================

class ContributionAllowedRoleSecurityTests(TestCase):

    def setUp(self):
        self.group = Group.objects.create(
            name="Allowed Role Security Group",
            code="ARSG",
        )

        # ---------------------------------------------------------
        # Create users for allowed roles
        # ---------------------------------------------------------

        self.admin = User.objects.create_user(
            email="allowed-admin@example.com",
            password="TestPassword123!",
        )

        self.chairman = User.objects.create_user(
            email="allowed-chairman@example.com",
            password="TestPassword123!",
        )

        self.treasurer = User.objects.create_user(
            email="allowed-treasurer@example.com",
            password="TestPassword123!",
        )

        # ---------------------------------------------------------
        # Create active memberships
        # ---------------------------------------------------------

        self.admin_membership = Membership.objects.create(
            user=self.admin,
            group=self.group,
            membership_number="ARSG-ADMIN-001",
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )

        self.chairman_membership = Membership.objects.create(
            user=self.chairman,
            group=self.group,
            membership_number="ARSG-CHAIRMAN-001",
            role=Membership.Role.CHAIRMAN,
            status=Membership.Status.ACTIVE,
        )

        self.treasurer_membership = Membership.objects.create(
            user=self.treasurer,
            group=self.group,
            membership_number="ARSG-TREASURER-001",
            role=Membership.Role.TREASURER,
            status=Membership.Status.ACTIVE,
        )

        # ---------------------------------------------------------
        # Create contribution data
        # ---------------------------------------------------------

        self.category = ContributionCategory.objects.create(
            name="Allowed Role Category",
        )

        self.contribution_type = ContributionType.objects.create(
            category=self.category,
            name="Allowed Role Contribution",
            amount=Decimal("10000.00"),
            status=ContributionType.Status.ACTIVE,
        )

        self.schedule = ContributionSchedule.objects.create(
            membership=self.admin_membership,
            contribution_type=self.contribution_type,
            period=date(2026, 9, 1),
            expected_amount=Decimal("10000.00"),
            status=ContributionSchedule.Status.PENDING,
        )

    # =============================================================
    # ADMIN
    # =============================================================

    def test_admin_can_view_schedule(self):
        """
        ADMIN should be allowed to view contribution schedules.
        """

        self.client.force_login(self.admin)

        response = self.client.get(
            reverse(
                "contributions:schedule-detail",
                kwargs={"schedule_id": self.schedule.pk},
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_admin_can_access_create_payment(self):
        """
        ADMIN should be allowed to access payment creation.
        """

        self.client.force_login(self.admin)

        response = self.client.get(
            reverse(
                "contributions:create-payment",
                kwargs={"schedule_id": self.schedule.pk},
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_admin_can_view_payment_list(self):
        """
        ADMIN should be allowed to view payment management.
        """

        self.client.force_login(self.admin)

        response = self.client.get(
            reverse(
                "contributions:payment-list",
                kwargs={"schedule_id": self.schedule.pk},
            )
        )

        self.assertEqual(response.status_code, 200)

    # =============================================================
    # CHAIRMAN
    # =============================================================

    def test_chairman_can_view_schedule(self):
        """
        CHAIRMAN should be allowed to view contribution schedules.
        """

        self.client.force_login(self.chairman)

        response = self.client.get(
            reverse(
                "contributions:schedule-detail",
                kwargs={"schedule_id": self.schedule.pk},
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_chairman_can_access_create_payment(self):
        """
        CHAIRMAN should be allowed to access payment creation.
        """

        self.client.force_login(self.chairman)

        response = self.client.get(
            reverse(
                "contributions:create-payment",
                kwargs={"schedule_id": self.schedule.pk},
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_chairman_can_view_payment_list(self):
        """
        CHAIRMAN should be allowed to view payment management.
        """

        self.client.force_login(self.chairman)

        response = self.client.get(
            reverse(
                "contributions:payment-list",
                kwargs={"schedule_id": self.schedule.pk},
            )
        )

        self.assertEqual(response.status_code, 200)

    # =============================================================
    # TREASURER
    # =============================================================

    def test_treasurer_can_view_schedule(self):
        """
        TREASURER should be allowed to view contribution schedules.
        """

        self.client.force_login(self.treasurer)

        response = self.client.get(
            reverse(
                "contributions:schedule-detail",
                kwargs={"schedule_id": self.schedule.pk},
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_treasurer_can_access_create_payment(self):
        """
        TREASURER should be allowed to access payment creation.
        """

        self.client.force_login(self.treasurer)

        response = self.client.get(
            reverse(
                "contributions:create-payment",
                kwargs={"schedule_id": self.schedule.pk},
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_treasurer_can_view_payment_list(self):
        """
        TREASURER should be allowed to view payment management.
        """

        self.client.force_login(self.treasurer)

        response = self.client.get(
            reverse(
                "contributions:payment-list",
                kwargs={"schedule_id": self.schedule.pk},
            )
        )

        self.assertEqual(response.status_code, 200)


# =============================================================
# Superuser Security Tests
# =============================================================

class ContributionSuperuserSecurityTests(TestCase):

    def setUp(self):
        self.group = Group.objects.create(
            name="Superuser Security Group",
            code="SUSG",
        )

        self.superuser = User.objects.create_superuser(
            email="superuser-security@example.com",
            password="TestPassword123!",
        )

        # ---------------------------------------------------------
        # Active target user and membership
        # ---------------------------------------------------------

        self.active_user = User.objects.create_user(
            email="active-target@example.com",
            password="TestPassword123!",
        )

        self.active_membership = Membership.objects.create(
            user=self.active_user,
            group=self.group,
            membership_number="SUSG-ACTIVE-001",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

        # ---------------------------------------------------------
        # Inactive membership
        # ---------------------------------------------------------

        self.inactive_membership_user = User.objects.create_user(
            email="inactive-membership-target@example.com",
            password="TestPassword123!",
        )

        self.inactive_membership = Membership.objects.create(
            user=self.inactive_membership_user,
            group=self.group,
            membership_number="SUSG-INACTIVE-MEM-001",
            role=Membership.Role.MEMBER,
            status=Membership.Status.INACTIVE,
        )

        # ---------------------------------------------------------
        # Suspended membership
        # ---------------------------------------------------------

        self.suspended_membership_user = User.objects.create_user(
            email="suspended-membership-target@example.com",
            password="TestPassword123!",
        )

        self.suspended_membership = Membership.objects.create(
            user=self.suspended_membership_user,
            group=self.group,
            membership_number="SUSG-SUSPENDED-MEM-001",
            role=Membership.Role.MEMBER,
            status=Membership.Status.SUSPENDED,
        )

        # ---------------------------------------------------------
        # Inactive user
        # ---------------------------------------------------------

        self.inactive_user = User.objects.create_user(
            email="inactive-target@example.com",
            password="TestPassword123!",
            is_active=False,
        )

        self.inactive_user_membership = Membership.objects.create(
            user=self.inactive_user,
            group=self.group,
            membership_number="SUSG-INACTIVE-USER-001",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

        # ---------------------------------------------------------
        # Inactive group
        # ---------------------------------------------------------

        self.inactive_group = Group.objects.create(
            name="Inactive Superuser Group",
            code="ISUG",
            is_active=False,
        )

        self.inactive_group_user = User.objects.create_user(
            email="inactive-group-target@example.com",
            password="TestPassword123!",
        )

        self.inactive_group_membership = Membership.objects.create(
            user=self.inactive_group_user,
            group=self.inactive_group,
            membership_number="ISUG-MEMBER-001",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

        # ---------------------------------------------------------
        # Contribution category and type
        # ---------------------------------------------------------

        self.category = ContributionCategory.objects.create(
            name="Superuser Security Category",
        )

        self.contribution_type = ContributionType.objects.create(
            category=self.category,
            name="Superuser Security Contribution",
            amount=Decimal("10000.00"),
            status=ContributionType.Status.ACTIVE,
        )

        # ---------------------------------------------------------
        # Schedules
        # ---------------------------------------------------------

        self.active_schedule = ContributionSchedule.objects.create(
            membership=self.active_membership,
            contribution_type=self.contribution_type,
            period=date(2026, 9, 1),
            expected_amount=Decimal("10000.00"),
            status=ContributionSchedule.Status.PENDING,
        )

        self.inactive_membership_schedule = (
            ContributionSchedule.objects.create(
                membership=self.inactive_membership,
                contribution_type=self.contribution_type,
                period=date(2026, 9, 1),
                expected_amount=Decimal("10000.00"),
                status=ContributionSchedule.Status.PENDING,
            )
        )

        self.suspended_membership_schedule = (
            ContributionSchedule.objects.create(
                membership=self.suspended_membership,
                contribution_type=self.contribution_type,
                period=date(2026, 9, 1),
                expected_amount=Decimal("10000.00"),
                status=ContributionSchedule.Status.PENDING,
            )
        )

        self.inactive_user_schedule = (
            ContributionSchedule.objects.create(
                membership=self.inactive_user_membership,
                contribution_type=self.contribution_type,
                period=date(2026, 9, 1),
                expected_amount=Decimal("10000.00"),
                status=ContributionSchedule.Status.PENDING,
            )
        )

        self.inactive_group_schedule = (
            ContributionSchedule.objects.create(
                membership=self.inactive_group_membership,
                contribution_type=self.contribution_type,
                period=date(2026, 9, 1),
                expected_amount=Decimal("10000.00"),
                status=ContributionSchedule.Status.PENDING,
            )
        )

    # =============================================================
    # SUPERUSER - ACTIVE TARGET
    # =============================================================

    def test_superuser_can_view_active_schedule(self):
        """
        A superuser should be allowed to view a schedule when the
        target membership, user, and group are all active.
        """

        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse(
                "contributions:schedule-detail",
                kwargs={"schedule_id": self.active_schedule.pk},
            )
        )

        self.assertEqual(response.status_code, 200)

    # =============================================================
    # SUPERUSER - INACTIVE MEMBERSHIP
    # =============================================================

    def test_superuser_cannot_view_inactive_membership_schedule(self):
        """
        A superuser should not access a schedule belonging to an
        inactive membership.
        """

        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse(
                "contributions:schedule-detail",
                kwargs={
                    "schedule_id": self.inactive_membership_schedule.pk
                },
            )
        )

        self.assertEqual(response.status_code, 403)

    # =============================================================
    # SUPERUSER - SUSPENDED MEMBERSHIP
    # =============================================================

    def test_superuser_cannot_view_suspended_membership_schedule(self):
        """
        A superuser should not access a schedule belonging to a
        suspended membership.
        """

        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse(
                "contributions:schedule-detail",
                kwargs={
                    "schedule_id": self.suspended_membership_schedule.pk
                },
            )
        )

        self.assertEqual(response.status_code, 403)

    # =============================================================
    # SUPERUSER - INACTIVE USER
    # =============================================================

    def test_superuser_cannot_view_inactive_user_schedule(self):
        """
        A superuser should not access a schedule belonging to an
        inactive user.
        """

        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse(
                "contributions:schedule-detail",
                kwargs={
                    "schedule_id": self.inactive_user_schedule.pk
                },
            )
        )

        self.assertEqual(response.status_code, 403)

    # =============================================================
    # SUPERUSER - INACTIVE GROUP
    # =============================================================

    def test_superuser_cannot_view_inactive_group_schedule(self):
        """
        A superuser should not access a schedule belonging to an
        inactive group.
        """

        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse(
                "contributions:schedule-detail",
                kwargs={
                    "schedule_id": self.inactive_group_schedule.pk
                },
            )
        )

        self.assertEqual(response.status_code, 403)

    # =============================================================
    # SUPERUSER - PAYMENT CREATION
    # =============================================================

    def test_superuser_cannot_create_payment_for_inactive_membership(self):
        """
        A superuser should not create a payment for an inactive
        membership.
        """

        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse(
                "contributions:create-payment",
                kwargs={
                    "schedule_id": self.inactive_membership_schedule.pk
                },
            )
        )

        self.assertEqual(response.status_code, 403)

        # Confirm that no payment was created.
        self.assertEqual(
            ContributionPayment.objects.filter(
                schedule=self.inactive_membership_schedule
            ).count(),
            0,
        )