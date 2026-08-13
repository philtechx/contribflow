from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.models import User
from apps.groups.models import Group
from .forms import MembershipForm
from .models import Membership
from .services.membership_service import (
    create_membership,
    generate_membership_number,
)


class MembershipServiceTests(TestCase):
    def setUp(self):
        self.group = Group.objects.create(
            name="Test Group",
            code="TST",
        )

        self.user1 = User.objects.create_user(
            email="user1@example.com",
            password="TestPassword123!",
            first_name="User",
            last_name="One",
        )

        self.user2 = User.objects.create_user(
            email="user2@example.com",
            password="TestPassword123!",
            first_name="User",
            last_name="Two",
        )

    def test_generate_first_membership_number(self):
        number = generate_membership_number(self.group)

        self.assertEqual(number, "TST-0001")

    def test_create_membership_generates_number_automatically(self):
        membership = create_membership(
            user=self.user1,
            group=self.group,
        )

        self.assertEqual(
            membership.membership_number,
            "TST-0001",
        )

    def test_second_membership_gets_next_number(self):
        create_membership(
            user=self.user1,
            group=self.group,
        )

        membership = create_membership(
            user=self.user2,
            group=self.group,
        )

        self.assertEqual(
            membership.membership_number,
            "TST-0002",
        )

    def test_user_cannot_join_same_group_twice(self):
        create_membership(
            user=self.user1,
            group=self.group,
        )

        with self.assertRaises(ValueError):
            create_membership(
                user=self.user1,
                group=self.group,
            )

    def test_user_can_join_different_groups(self):
        second_group = Group.objects.create(
            name="Second Test Group",
            code="TST2",
        )

        membership1 = create_membership(
            user=self.user1,
            group=self.group,
        )

        membership2 = create_membership(
            user=self.user1,
            group=second_group,
        )

        self.assertNotEqual(
            membership1.group,
            membership2.group,
        )

        self.assertEqual(
            Membership.objects.filter(
                user=self.user1
            ).count(),
            2,
        )


class MembershipModelTests(TestCase):
    def setUp(self):
        self.group = Group.objects.create(
            name="Test Group",
            code="TST",
        )

        self.user = User.objects.create_user(
            email="modeltest@example.com",
            password="TestPassword123!",
        )

    def test_membership_defaults(self):
        membership = Membership.objects.create(
            user=self.user,
            group=self.group,
            membership_number="TST-0001",
        )

        self.assertEqual(
            membership.role,
            Membership.Role.MEMBER,
        )

        self.assertEqual(
            membership.status,
            Membership.Status.ACTIVE,
        )

    def test_membership_string_representation(self):
        membership = Membership.objects.create(
            user=self.user,
            group=self.group,
            membership_number="TST-0001",
        )

        self.assertEqual(
            str(membership),
            "TST-0001 - modeltest@example.com",
        )

    def test_membership_number_unique_within_group(self):
        Membership.objects.create(
            user=self.user,
            group=self.group,
            membership_number="TST-0001",
        )

        second_user = User.objects.create_user(
            email="second@example.com",
            password="TestPassword123!",
        )

        with self.assertRaises(IntegrityError):
            Membership.objects.create(
                user=second_user,
                group=self.group,
                membership_number="TST-0001",
            )

class MembershipFormTests(TestCase):
    def setUp(self):
        self.group = Group.objects.create(
            name="Test Group",
            code="TST",
        )

        self.user = User.objects.create_user(
            email="formtest@example.com",
            password="TestPassword123!",
        )

    def test_membership_form_contains_expected_fields(self):
        form = MembershipForm()

        expected_fields = {
            "user",
            "group",
            "role",
            "status",
            "notes",
        }

        self.assertEqual(
            set(form.fields.keys()),
            expected_fields,
        )

    def test_membership_number_is_not_in_form(self):
        form = MembershipForm()

        self.assertNotIn(
            "membership_number",
            form.fields,
        )

    def test_membership_form_is_valid(self):
        form = MembershipForm(
            data={
                "user": self.user.pk,
                "group": self.group.pk,
                "role": Membership.Role.MEMBER,
                "status": Membership.Status.ACTIVE,
                "notes": "Test membership",
            }
        )

        self.assertTrue(form.is_valid())