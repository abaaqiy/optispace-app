from datetime import time
from unittest.mock import patch

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.models import Session
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase
from django.urls import reverse

from bookings.models import Reservation
from bookings.services import change_reservation
from bookings.tests import fixtures
from rooms.models import Building, Room
from scheduling.models import TimetableDay

from .models import User


class AccountDeletionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        (
            cls.student, cls.other, cls.lecturer, cls.admin,
            cls.room, cls.large, cls.day,
        ) = fixtures()

    def setUp(self):
        self.client.force_login(self.admin)

    def reserve(self, user=None, start=10, end=11):
        return Reservation.objects.create(
            user=user or self.lecturer, room=self.room, date=self.day.date,
            start_time=time(start), end_time=time(end), purpose="Account deletion test",
        )

    def bulk_delete(self, users, confirm=False):
        return self.client.post(reverse("admin:accounts_user_changelist"), {
            "action": "delete_selected",
            "_selected_action": [str(user.pk) for user in users],
            **({"post": "yes"} if confirm else {}),
        })

    def add_history(self, obj):
        return LogEntry.objects.create(
            user=self.admin, content_type=ContentType.objects.get_for_model(obj),
            object_id=str(obj.pk), object_repr=str(obj)[:200],
            action_flag=CHANGE, change_message="Test history",
        )

    def test_bulk_confirmation_includes_reservations_without_deleting_anything(self):
        booking = self.reserve()
        response = self.bulk_delete([self.lecturer])
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["perms_lacking"])
        self.assertFalse(response.context["protected"])
        self.assertContains(response, booking.reference)
        self.assertContains(response, "permanently removes")
        self.assertContains(response, "requested, reviewed or cancelled")
        self.assertTrue(User.objects.filter(pk=self.lecturer.pk).exists())
        self.assertTrue(Reservation.objects.filter(pk=booking.pk).exists())

    def test_delete_removes_every_reservation_status_and_archived_history(self):
        pending = self.reserve()
        approved = self.reserve(start=11, end=12)
        change_reservation(approved.reference, self.admin, "approve")
        rejected = self.reserve(start=12, end=13)
        change_reservation(rejected.reference, self.admin, "reject")
        cancelled = self.reserve(start=13, end=14)
        change_reservation(cancelled.reference, self.lecturer, "cancel")
        archived = self.reserve(start=14, end=15)
        Reservation.objects.filter(pk=archived.pk).update(is_archived=True)
        retained = self.reserve(self.other, start=15, end=16)
        retained_history = self.add_history(retained)
        removed_history = [self.add_history(self.lecturer).pk, self.add_history(pending).pk]
        user_session = Client()
        user_session.force_login(self.lecturer)
        session_key = user_session.session.session_key
        other_session = Client()
        other_session.force_login(self.other)
        other_session_key = other_session.session.session_key

        response = self.client.post(
            reverse("admin:accounts_user_delete", args=[self.lecturer.pk]),
            {"post": "yes"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(pk=self.lecturer.pk).exists())
        self.assertFalse(Reservation.objects.filter(
            pk__in=[pending.pk, approved.pk, rejected.pk, cancelled.pk, archived.pk],
        ).exists())
        self.assertTrue(Reservation.objects.filter(pk=retained.pk).exists())
        self.assertFalse(LogEntry.objects.filter(pk__in=removed_history).exists())
        self.assertFalse(LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(Reservation),
            object_id__in=[str(approved.pk), str(rejected.pk)],
        ).exists())
        self.assertTrue(LogEntry.objects.filter(pk=retained_history.pk).exists())
        self.assertFalse(Session.objects.filter(pk=session_key).exists())
        self.assertTrue(Session.objects.filter(pk=other_session_key).exists())
        self.assertEqual(user_session.get("/api/auth/me/").status_code, 403)
        self.assertEqual(other_session.get("/api/auth/me/").status_code, 200)
        self.assertEqual(Room.objects.count(), 2)
        self.assertEqual(Building.objects.count(), 1)
        self.assertEqual(TimetableDay.objects.count(), 2)

    def test_bulk_deletes_only_selected_accounts_and_their_reservations(self):
        self.reserve(self.student)
        self.reserve(self.lecturer, start=11, end=12)
        retained = self.reserve(self.other, start=12, end=13)
        response = self.bulk_delete([self.student, self.lecturer], confirm=True)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(pk__in=[self.student.pk, self.lecturer.pk]).exists())
        self.assertEqual(list(Reservation.objects.values_list("pk", flat=True)), [retained.pk])
        self.assertTrue(User.objects.filter(pk=self.other.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())

    def test_deleting_approved_request_releases_the_room_without_removing_lectures(self):
        booking = self.reserve()
        change_reservation(booking.reference, self.admin, "approve")
        url = f"/api/rooms/{self.room.code}/"
        query = {"date": str(self.day.date), "time": "10:30"}
        self.assertEqual(self.client.get(url, query).json()["status"], "reserved")
        self.bulk_delete([self.lecturer], confirm=True)
        self.assertEqual(self.client.get(url, query).json()["status"], "available")
        query["time"] = "08:30"
        self.assertEqual(self.client.get(url, query).json()["status"], "occupied")

    def test_deleting_a_reviewer_or_canceller_removes_the_linked_reservations(self):
        reviewer = User.objects.create_superuser(
            username="retired-admin", email="retired-admin@oauife.edu.ng",
            password="Ridge-Brook-472!",
        )
        reviewed = self.reserve(self.student)
        change_reservation(reviewed.reference, reviewer, "approve")
        cancelled = self.reserve(self.other, start=11, end=12)
        change_reservation(cancelled.reference, reviewer, "cancel")
        unrelated = self.reserve(self.lecturer, start=12, end=13)
        response = self.bulk_delete([reviewer])
        self.assertContains(response, reviewed.reference)
        self.assertContains(response, cancelled.reference)
        self.bulk_delete([reviewer], confirm=True)
        self.assertFalse(Reservation.objects.filter(pk__in=[reviewed.pk, cancelled.pk]).exists())
        self.assertTrue(Reservation.objects.filter(pk=unrelated.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.student.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.other.pk).exists())

    def test_model_deletion_also_cascades(self):
        booking = self.reserve()
        self.lecturer.delete()
        self.assertFalse(Reservation.objects.filter(pk=booking.pk).exists())

    def test_failure_rolls_back_account_reservations_history_and_session(self):
        booking = self.reserve()
        history = self.add_history(booking)
        user_session = Client()
        user_session.force_login(self.lecturer)
        key = user_session.session.session_key
        with patch.object(Session, "get_decoded", side_effect=RuntimeError("Simulated failure")):
            with self.assertRaises(RuntimeError), transaction.atomic():
                self.lecturer.delete()
        self.assertTrue(User.objects.filter(pk=self.lecturer.pk).exists())
        self.assertTrue(Reservation.objects.filter(pk=booking.pk).exists())
        self.assertTrue(LogEntry.objects.filter(pk=history.pk).exists())
        self.assertTrue(Session.objects.filter(pk=key).exists())

    def test_students_lecturers_and_ordinary_staff_cannot_delete_accounts(self):
        self.lecturer.is_staff = True
        self.lecturer.save(update_fields=["is_staff"])
        for user in (self.student, self.other, self.lecturer):
            with self.subTest(role=user.username):
                self.client.force_login(user)
                self.bulk_delete([self.other], confirm=True)
                self.assertTrue(User.objects.filter(pk=self.other.pk).exists())

    def test_reservation_delete_and_room_protection_are_unchanged(self):
        booking = self.reserve()
        response = self.client.post(
            reverse("admin:bookings_reservation_delete", args=[booking.pk]),
            {"post": "yes"},
        )
        self.assertEqual(response.status_code, 403)
        with self.assertRaises(ProtectedError):
            self.room.delete()
        self.assertTrue(Reservation.objects.filter(pk=booking.pk).exists())

    def test_account_delete_requires_csrf(self):
        self.reserve()
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.admin)
        url = reverse("admin:accounts_user_delete", args=[self.lecturer.pk])
        self.assertEqual(browser.post(url, {"post": "yes"}).status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.lecturer.pk).exists())


class AdministratorPasswordResetTests(TestCase):
    old_password = "Original-Pebble-428!"
    new_password = "New-Brook-Maple-913!"

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser(
            username="password-manager", email="password-manager@oauife.edu.ng",
            password=cls.old_password,
        )
        cls.lecturer = User.objects.create_user(
            username="password-lecturer", email="password-lecturer@oauife.edu.ng",
            password=cls.old_password, role="lecturer",
        )
        cls.student = User.objects.create_user(
            username="password-student", email="password-student@student.oauife.edu.ng",
            password=cls.old_password,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def reset_url(self, account=None):
        return reverse("admin:auth_user_password_change", args=[(account or self.lecturer).pk])

    def reset(self, account=None, **changes):
        return self.client.post(self.reset_url(account), {
            "password1": self.new_password,
            "password2": self.new_password,
            "set-password": "Reset password",
            **changes,
        })

    def test_reset_link_and_form_use_email_and_only_two_password_fields(self):
        url = self.reset_url()
        self.assertContains(self.client.get(reverse("admin:accounts_user_changelist")), f'href="{url}"')
        self.assertContains(self.client.get(reverse("admin:accounts_user_change", args=[self.lecturer.pk])), f'href="{url}"')
        response = self.client.get(url)
        self.assertContains(response, f"Reset password: {self.lecturer.email}")
        self.assertContains(response, "The old password is not required")
        self.assertEqual(list(response.context["form"].fields), ["password1", "password2"])
        self.assertNotContains(response, 'name="usable_password"')
        self.assertNotContains(response, 'name="old_password"')

    def test_admin_resets_without_old_password_and_invalidates_existing_sessions(self):
        old_session = Client()
        old_session.force_login(self.lecturer)
        response = self.reset()
        self.assertEqual(response.status_code, 302)
        self.lecturer.refresh_from_db()
        self.assertTrue(self.lecturer.check_password(self.new_password))
        self.assertFalse(self.lecturer.check_password(self.old_password))
        self.assertNotEqual(self.lecturer.password, self.new_password)
        self.assertEqual(old_session.get("/api/auth/me/").status_code, 403)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)
        login = Client()
        self.assertEqual(login.post("/api/auth/login/", {
            "email": self.lecturer.email, "password": self.old_password,
        }).status_code, 401)
        self.assertEqual(login.post("/api/auth/login/", {
            "email": self.lecturer.email, "password": self.new_password,
        }).status_code, 200)
        history = LogEntry.objects.filter(
            content_type=ContentType.objects.get_for_model(User),
            object_id=str(self.lecturer.pk), action_flag=CHANGE,
        ).get()
        self.assertIn("password", history.change_message.lower())
        self.assertNotIn(self.new_password, history.change_message)

    def test_student_and_inactive_lecturer_can_be_reset_without_changing_roles_or_activation(self):
        self.lecturer.is_active = False
        self.lecturer.save(update_fields=["is_active"])
        for account in (self.student, self.lecturer):
            with self.subTest(role=account.role):
                original = (account.role, account.is_active, account.is_staff, account.is_superuser)
                self.assertEqual(self.reset(account).status_code, 302)
                account.refresh_from_db()
                self.assertTrue(account.check_password(self.new_password))
                self.assertEqual((account.role, account.is_active, account.is_staff, account.is_superuser), original)
        self.assertEqual(Client().post("/api/auth/login/", {
            "email": self.lecturer.email, "password": self.new_password,
        }).status_code, 403)

    def test_administrator_can_reset_another_administrator(self):
        other = User.objects.create_superuser(
            username="other-manager", email="other-manager@oauife.edu.ng",
            password=self.old_password,
        )
        self.assertEqual(self.reset(other).status_code, 302)
        other.refresh_from_db()
        self.assertTrue(other.is_superuser)
        self.assertTrue(other.check_password(self.new_password))

    def test_own_reset_keeps_current_admin_session_but_invalidates_other_sessions(self):
        other_session = Client()
        other_session.force_login(self.admin)
        self.assertEqual(self.reset(self.admin).status_code, 302)
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 200)
        self.assertEqual(other_session.get("/api/auth/me/").status_code, 403)

    def test_password_confirmation_and_existing_validators_remain_required(self):
        for changes, message in (
            ({"password2": "Different-Pebble-473!"}, "didn’t match"),
            ({"password1": "short", "password2": "short"}, "too short"),
            ({"password1": "123456789012", "password2": "123456789012"}, "entirely numeric"),
            ({"password1": "password", "password2": "password"}, "too common"),
            ({"password1": "", "password2": ""}, "required"),
        ):
            with self.subTest(case=message):
                response = self.reset(**changes)
                self.assertEqual(response.status_code, 200)
                self.assertIn(message, str(response.context["form"].errors))
                self.lecturer.refresh_from_db()
                self.assertTrue(self.lecturer.check_password(self.old_password))

    def test_no_added_uppercase_number_or_symbol_requirement(self):
        password = "tidalriverstone"
        self.assertEqual(self.reset(password1=password, password2=password).status_code, 302)
        self.lecturer.refresh_from_db()
        self.assertTrue(self.lecturer.check_password(password))

    def test_students_lecturers_and_permissioned_staff_cannot_reset_passwords(self):
        staff = User.objects.create_user(
            username="support-staff", email="support-staff@oauife.edu.ng",
            role="lecturer", is_staff=True,
        )
        staff.user_permissions.add(Permission.objects.get(
            content_type__app_label="accounts", codename="change_user",
        ))
        for actor in (self.student, self.lecturer, staff):
            with self.subTest(role=actor.username):
                self.client.force_login(actor)
                response = self.reset()
                self.assertIn(response.status_code, (302, 403))
                self.lecturer.refresh_from_db()
                self.assertTrue(self.lecturer.check_password(self.old_password))
        self.assertNotContains(self.client.get(reverse("admin:accounts_user_changelist")), "Reset password")

    def test_reset_requires_csrf(self):
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.admin)
        response = browser.post(self.reset_url(), {
            "password1": self.new_password, "password2": self.new_password,
        })
        self.assertEqual(response.status_code, 403)
        self.lecturer.refresh_from_db()
        self.assertTrue(self.lecturer.check_password(self.old_password))

    def test_missing_account_returns_not_found(self):
        url = reverse("admin:auth_user_password_change", args=[999999])
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_reset_does_not_offer_or_accept_disabling_password_authentication(self):
        self.assertEqual(self.reset(usable_password="false", **{"unset-password": "Disable"}).status_code, 302)
        self.lecturer.refresh_from_db()
        self.assertTrue(self.lecturer.has_usable_password())
        self.assertTrue(self.lecturer.check_password(self.new_password))
