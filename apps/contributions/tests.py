from datetime import date
from decimal import Decimal

from django.db import IntegrityError
from django.db.models import Sum
from django.test import TestCase

from .services.contribution_schedule_service import (
    generate_monthly_schedules,
)
from django.urls import reverse
from django.contrib.messages import get_messages
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
)


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

    def test_admin_can_generate_schedules(self):
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

    def test_member_cannot_generate_schedules(self):
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
            },
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_unrelated_user_cannot_generate_schedules(self):
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
            },
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_generate_requires_month(self):
        self.client.login(
            email="admin@example.com",
            password="TestPassword123!",
        )

        response = self.client.post(
            reverse(
                "contributions:generate-schedules"
            ),
            {},
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
            },
        )

        second_response = self.client.post(
            self.url,
            {
                "month": "2026-08",
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