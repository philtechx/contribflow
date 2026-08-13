from .services.membership_permissions import can_manage_memberships
from django.db import IntegrityError
from .forms import MembershipForm
from django.urls import reverse
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

# MembershipPermissionsTests
class MembershipPermissionTests(TestCase):
    def setUp(self):
        self.group = Group.objects.create(
            name="Permission Test Group",
            code="PERM",
        )

        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="TestPassword123!",
        )

        self.chairman_user = User.objects.create_user(
            email="chairman@example.com",
            password="TestPassword123!",
        )

        self.member_user = User.objects.create_user(
            email="member@example.com",
            password="TestPassword123!",
        )

        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="TestPassword123!",
        )

        Membership.objects.create(
            user=self.admin_user,
            group=self.group,
            membership_number="PERM-0001",
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )

        Membership.objects.create(
            user=self.chairman_user,
            group=self.group,
            membership_number="PERM-0002",
            role=Membership.Role.CHAIRMAN,
            status=Membership.Status.ACTIVE,
        )

        Membership.objects.create(
            user=self.member_user,
            group=self.group,
            membership_number="PERM-0003",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

    def test_superuser_can_manage_any_group(self):
        self.other_user.is_superuser = True
        self.other_user.save(update_fields=["is_superuser"])

        self.assertTrue(
            can_manage_memberships(
                self.other_user,
                self.group,
            )
        )

    def test_group_admin_can_manage_own_group(self):
        self.assertTrue(
            can_manage_memberships(
                self.admin_user,
                self.group,
            )
        )

    def test_chairman_can_manage_own_group(self):
        self.assertTrue(
            can_manage_memberships(
                self.chairman_user,
                self.group,
            )
        )

    def test_normal_member_cannot_manage_memberships(self):
        self.assertFalse(
            can_manage_memberships(
                self.member_user,
                self.group,
            )
        )

    def test_unrelated_user_cannot_manage_group(self):
        self.assertFalse(
            can_manage_memberships(
                self.other_user,
                self.group,
            )
        )

    def test_inactive_admin_cannot_manage_group(self):
        membership = Membership.objects.get(
            user=self.admin_user,
            group=self.group,
        )

        membership.status = Membership.Status.INACTIVE
        membership.save(update_fields=["status"])

        self.assertFalse(
            can_manage_memberships(
                self.admin_user,
                self.group,
            )
        )

# MembershipViewPermissionTests
class MembershipViewPermissionTests(TestCase):
    def setUp(self):
        self.group_a = Group.objects.create(
            name="Group A",
            code="GRPA",
        )

        self.group_b = Group.objects.create(
            name="Group B",
            code="GRPB",
        )

        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="TestPassword123!",
        )

        self.member = User.objects.create_user(
            email="member@example.com",
            password="TestPassword123!",
        )

        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="TestPassword123!",
        )

        Membership.objects.create(
            user=self.admin,
            group=self.group_a,
            membership_number="GRPA-0001",
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )

        Membership.objects.create(
            user=self.member,
            group=self.group_a,
            membership_number="GRPA-0002",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

        Membership.objects.create(
            user=self.other_user,
            group=self.group_b,
            membership_number="GRPB-0001",
            role=Membership.Role.MEMBER,
            status=Membership.Status.ACTIVE,
        )

    def test_group_admin_can_access_membership_list(self):
        self.client.login(
            email="admin@example.com",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse("memberships:list")
        )

        self.assertEqual(response.status_code, 200)

    def test_group_admin_only_sees_own_group_memberships(self):
        self.client.login(
            email="admin@example.com",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse("memberships:list")
        )

        memberships = response.context["memberships"]

        self.assertEqual(
            memberships.count(),
            2,
        )

        self.assertTrue(
            all(
                membership.group == self.group_a
                for membership in memberships
            )
        )

    def test_normal_member_cannot_access_membership_list(self):
        self.client.login(
            email="member@example.com",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse("memberships:list")
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_unrelated_user_cannot_access_membership_list(self):
        self.client.login(
            email="other@example.com",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse("memberships:list")
        )

        self.assertEqual(
            response.status_code,
            403,
        )

    def test_admin_cannot_create_membership_in_other_group(self):
        self.client.login(
            email="admin@example.com",
            password="TestPassword123!",
        )

        response = self.client.post(
            reverse("memberships:create"),
            {
                "user": self.member.pk,
                "group": self.group_b.pk,
                "role": Membership.Role.MEMBER,
                "status": Membership.Status.ACTIVE,
                "notes": "",
            },
        )

        self.assertEqual(
            response.status_code,
            403,
        )

# MembershipFormTests
class MembershipFormTests(TestCase):

    def setUp(self):
        self.group_a = Group.objects.create(
            name="Group A",
            code="FORM-A",
        )

        self.group_b = Group.objects.create(
            name="Group B",
            code="FORM-B",
        )

        self.admin = User.objects.create_user(
            email="form-admin@example.com",
            password="TestPassword123!",
        )

        Membership.objects.create(
            user=self.admin,
            group=self.group_a,
            membership_number="FORM-0001",
            role=Membership.Role.ADMIN,
            status=Membership.Status.ACTIVE,
        )

    def test_admin_only_sees_manageable_groups(self):
        form = MembershipForm(
            user=self.admin,
        )

        groups = list(
            form.fields["group"]
            .queryset
        )

        self.assertEqual(
            groups,
            [self.group_a],
        )

    def test_unauthenticated_form_has_no_groups(self):
        form = MembershipForm()

        self.assertEqual(
            form.fields["group"].queryset.count(),
            0,
        )