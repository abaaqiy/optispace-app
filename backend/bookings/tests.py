from concurrent.futures import ThreadPoolExecutor
from datetime import date, time, timedelta
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from rooms.models import Building, Room
from rooms.catalog import ROOM_TYPES
from scheduling.models import Course, TimetableDay
from scheduling.services.timetable_import import (
    ImportProblem,
    apply_import,
    preview_import,
)
from scheduling.test_timetable_import import timetable_csv

from .models import Reservation
from .services import change_reservation


def fixtures():
    users = get_user_model().objects
    student = users.create_user(
        username="reader", email="reader@student.oauife.edu.ng", first_name="Reader"
    )
    other = users.create_user(username="other", email="other@student.oauife.edu.ng")
    lecturer = users.create_user(
        username="lecturer", email="lecturer@oauife.edu.ng", role="lecturer"
    )
    admin = users.create_superuser(
        username="reviewer", email="reviewer@oauife.edu.ng", password="Test-only-271!"
    )
    building = Building.objects.create(
        name="Science building", campus_zone="Faculty of Science"
    )
    room = Room.objects.create(
        code="reading-1",
        name="Reading Room",
        building=building,
        capacity=20,
        size_category="small",
        room_type="Reading Room",
    )
    large = Room.objects.create(
        code="lecture-1",
        name="Lecture Room",
        building=building,
        capacity=200,
        size_category="large",
        room_type="Lecture Theatre",
    )
    future_date = timezone.localdate() + timedelta(days=30)
    day = TimetableDay.objects.create(
        room=room, date=future_date, start_time=time(8), end_time=time(9)
    )
    TimetableDay.objects.create(
        room=large, date=future_date, start_time=time(8), end_time=time(9)
    )
    return student, other, lecturer, admin, room, large, day


class ReservationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        (
            cls.student,
            cls.other,
            cls.lecturer,
            cls.admin,
            cls.room,
            cls.large,
            cls.day,
        ) = fixtures()

    def setUp(self):
        self.client.force_authenticate(self.student)

    def payload(self, **changes):
        return {
            "roomId": self.room.code,
            "date": str(self.day.date),
            "startTime": "10:00",
            "endTime": "12:00",
            "purpose": "Group study",
            **changes,
        }

    def request_room(self, user=None, **changes):
        self.client.force_authenticate(user or self.student)
        response = self.client.post(
            "/api/reservations/", self.payload(**changes), format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        return Reservation.objects.get(reference=response.data["refId"])

    def action(self, reservation, action, user=None, **data):
        self.client.force_authenticate(user or self.admin)
        return self.client.post(
            f"/api/reservations/{reservation.reference}/{action}/", data, format="json"
        )

    def room_at(self, clock):
        return self.client.get(
            f"/api/rooms/{self.room.code}/", {"date": str(self.day.date), "time": clock}
        ).data

    def test_request_persists_owner_pending_status_and_response_contract(self):
        booking = self.request_room(purpose="  Group study  ")
        self.assertEqual(booking.user, self.student)
        self.assertEqual(booking.status, "pending")
        self.assertEqual(booking.purpose, "Group study")
        self.assertIsNone(booking.reviewed_by)
        data = self.client.get("/api/reservations/").data[0]
        self.assertEqual(data["timeSlot"], "10:00 - 12:00")
        self.assertEqual(data["status"], "Pending")
        self.assertTrue(data["canCancel"])
        self.assertFalse(data["canReview"])
        self.assertEqual(self.room_at("10:30")["status"], "available")

    def test_roles_and_private_lists(self):
        first = self.request_room()
        second = self.request_room(self.other)
        self.client.force_authenticate(self.student)
        self.assertEqual(
            [item["refId"] for item in self.client.get("/api/reservations/").data],
            [first.reference],
        )
        self.assertEqual(self.action(second, "cancel", self.student).status_code, 404)
        self.assertEqual(self.action(first, "approve", self.student).status_code, 403)
        self.assertEqual(self.action(first, "reject", self.lecturer).status_code, 404)
        self.client.force_authenticate(self.admin)
        self.assertEqual(len(self.client.get("/api/reservations/").data), 2)
        self.assertEqual(
            self.client.post(
                "/api/reservations/", self.payload(), format="json"
            ).status_code,
            403,
        )

    def test_students_cannot_request_large_rooms_but_lecturers_can(self):
        response = self.client.post(
            "/api/reservations/", self.payload(roomId=self.large.code), format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.request_room(self.lecturer, roomId=self.large.code)

    def test_anonymous_inactive_and_staff_without_superuser_cannot_review(self):
        booking = self.request_room()
        anonymous = APIClient()
        self.assertEqual(anonymous.get("/api/reservations/").status_code, 403)
        self.assertEqual(
            anonymous.post(
                "/api/reservations/", self.payload(), format="json"
            ).status_code,
            403,
        )
        self.student.is_active = False
        self.student.save()
        self.assertEqual(
            self.client.post(
                "/api/reservations/",
                self.payload(startTime="13:00", endTime="14:00"),
                format="json",
            ).status_code,
            400,
        )
        self.other.is_staff = True
        self.other.save()
        own = self.request_room(self.other)
        self.assertEqual(self.action(own, "approve", self.other).status_code, 403)
        self.assertEqual(self.action(booking, "approve").status_code, 409)

    def test_spoofed_owner_or_status_and_invalid_inputs_are_rejected(self):
        for changes in (
            {"user": self.other.pk},
            {"status": "approved"},
            {"organizer": "Someone else"},
            {"date": "bad"},
            {"date": str(timezone.localdate() - timedelta(days=1))},
            {"startTime": "12:00"},
            {"endTime": "09:00"},
            {"startTime": "25:00"},
            {"startTime": "10:00:30"},
            {"purpose": "   "},
            {"purpose": "a" * 201},
            {"roomId": "missing"},
        ):
            with self.subTest(changes=changes):
                self.assertEqual(
                    self.client.post(
                        "/api/reservations/", self.payload(**changes), format="json"
                    ).status_code,
                    400,
                )
        self.assertEqual(Reservation.objects.count(), 0)

    def test_request_without_school_timetable_needs_admin_review_and_keeps_gaps_unknown(
        self,
    ):
        TimetableDay.objects.all().delete()
        booking = self.request_room()
        self.assertEqual(self.room_at("10:30")["status"], "unknown")
        self.assertEqual(self.action(booking, "approve").status_code, 200)
        self.assertEqual(self.room_at("10:30")["status"], "reserved")
        self.assertEqual(self.room_at("09:00")["status"], "unknown")
        self.assertEqual(self.room_at("09:59")["status"], "unknown")
        self.assertEqual(self.room_at("12:00")["status"], "unknown")

    def test_duplicate_request_does_not_create_second_record(self):
        self.request_room()
        self.assertEqual(
            self.client.post(
                "/api/reservations/", self.payload(), format="json"
            ).status_code,
            400,
        )
        self.assertEqual(Reservation.objects.count(), 1)

    def test_lecture_conflicts_block_requests_and_adjacent_times_work(self):
        TimetableDay.objects.create(
            room=self.room, date=self.day.date, start_time=time(9), end_time=time(11)
        )
        self.assertEqual(
            self.client.post(
                "/api/reservations/", self.payload(), format="json"
            ).status_code,
            400,
        )
        self.request_room(startTime="11:00")

    def test_approve_updates_availability_without_exposing_private_data(self):
        booking = self.request_room(purpose="Private discussion")
        response = self.action(booking, "approve", note="Confirmed")
        self.assertEqual(response.status_code, 200, response.data)
        booking.refresh_from_db()
        self.assertEqual(booking.reviewed_by, self.admin)
        self.assertEqual(booking.review_note, "Confirmed")
        self.assertIsNotNone(booking.reviewed_at)
        public = APIClient()
        data = public.get(
            f"/api/rooms/{self.room.code}/",
            {"date": str(self.day.date), "time": "10:00"},
        ).data
        self.assertEqual(data["status"], "reserved")
        self.assertEqual(data["currentSchedule"], "Approved reservation")
        self.assertNotIn("Private discussion", str(data))
        self.assertNotIn(self.student.email, str(data))
        self.assertNotIn("Confirmed", str(data))
        self.assertEqual(self.room_at("12:00")["status"], "available")
        self.assertEqual(self.room_at("09:50")["status"], "available")
        rooms = public.get(
            "/api/rooms/",
            {"date": str(self.day.date), "time": "10:30", "status": "reserved"},
        ).data
        self.assertEqual([room["id"] for room in rooms], [self.room.code])

    def test_only_one_overlapping_request_can_be_approved(self):
        first = self.request_room()
        second = self.request_room(self.other)
        self.assertEqual(self.action(first, "approve").status_code, 200)
        self.assertEqual(self.action(second, "approve").status_code, 409)
        second.refresh_from_db()
        self.assertEqual(second.status, "pending")
        self.client.force_authenticate(self.lecturer)
        self.assertEqual(
            self.client.post(
                "/api/reservations/", self.payload(), format="json"
            ).status_code,
            400,
        )
        adjacent = self.request_room(self.lecturer, startTime="12:00", endTime="13:00")
        self.assertEqual(self.action(adjacent, "approve").status_code, 200)

    def test_approval_rechecks_new_class_and_allows_cancelled_class_slot(self):
        booking = self.request_room()
        lecture = TimetableDay.objects.create(
            room=self.room, date=self.day.date, start_time=time(10), end_time=time(11)
        )
        self.assertEqual(self.action(booking, "approve").status_code, 409)
        lecture.is_cancelled = True
        lecture.save()
        self.assertEqual(self.action(booking, "approve").status_code, 200)

    def test_approved_reservation_blocks_lecture_creation_edit_and_restore(self):
        lecture = TimetableDay.objects.create(
            room=self.room, date=self.day.date, start_time=time(12), end_time=time(13)
        )
        booking = self.request_room()
        self.assertEqual(self.action(booking, "approve").status_code, 200)
        with self.assertRaises(ValidationError):
            TimetableDay.objects.create(
                room=self.room,
                date=self.day.date,
                start_time=time(11),
                end_time=time(13),
            )
        lecture.start_time = time(11)
        with self.assertRaises(ValidationError):
            lecture.save()
        cancelled = TimetableDay.objects.create(
            room=self.room,
            date=self.day.date,
            start_time=time(10),
            end_time=time(11),
            is_cancelled=True,
        )
        cancelled.is_cancelled = False
        with self.assertRaises(ValidationError):
            cancelled.save()

    def test_reject_records_note_and_does_not_block_time(self):
        booking = self.request_room()
        response = self.action(booking, "reject", note="Please use the library.")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["reviewNote"], "Please use the library.")
        self.assertFalse(response.data["canCancel"])
        self.assertEqual(self.action(booking, "approve").status_code, 409)
        self.assertEqual(self.action(booking, "cancel", self.student).status_code, 409)
        self.request_room()

    def test_cancel_retains_history_and_releases_approved_time(self):
        booking = self.request_room()
        self.action(booking, "approve")
        response = self.action(booking, "cancel", self.student)
        self.assertEqual(response.status_code, 200)
        booking.refresh_from_db()
        self.assertEqual(booking.status, "cancelled")
        self.assertEqual(booking.cancelled_by, self.student)
        self.assertIsNotNone(booking.cancelled_at)
        self.assertEqual(booking.reviewed_by, self.admin)
        self.assertEqual(self.room_at("10:00")["status"], "available")
        self.assertEqual(self.action(booking, "cancel").status_code, 409)
        self.request_room()

    def test_admin_can_cancel_pending_request(self):
        booking = self.request_room()
        self.assertEqual(self.action(booking, "cancel").status_code, 200)
        booking.refresh_from_db()
        self.assertEqual(booking.cancelled_by, self.admin)

    def test_past_requests_cannot_be_approved_or_cancelled_but_can_be_rejected(self):
        booking = self.request_room()
        Reservation.objects.filter(pk=booking.pk).update(
            date=timezone.localdate() - timedelta(days=1)
        )
        self.assertEqual(self.action(booking, "approve").status_code, 409)
        self.assertEqual(self.action(booking, "cancel", self.student).status_code, 409)
        self.assertEqual(self.action(booking, "reject").status_code, 200)

    def test_every_room_type_is_reserved_only_during_approved_booking(self):
        booking = self.request_room()
        self.assertEqual(self.action(booking, "approve").status_code, 200)
        for kind in (*ROOM_TYPES, "Custom Hall"):
            with self.subTest(kind=kind):
                self.room.room_type = kind
                self.room.save()
                for clock in ("09:44", "09:45", "09:59"):
                    self.assertEqual(self.room_at(clock)["status"], "available")
                    self.assertIsNone(self.room_at(clock)["reservedUntil"])
                current = self.room_at("10:00")
                self.assertEqual(current["status"], "reserved")
                self.assertEqual(current["reservedSeconds"], 7200)
                self.assertEqual(current["reservedUntil"], booking.ends_at.isoformat())
                self.assertEqual(self.room_at("11:59")["reservedSeconds"], 60)
                self.assertEqual(self.room_at("12:00")["status"], "available")
                slots = current["hourlySchedule"]
                self.assertEqual(
                    [slot["time"] for slot in slots if slot["reserved"]],
                    ["10:00 - 12:00"],
                )
                self.assertEqual(
                    [slot["status"] for slot in slots],
                    ["available", "occupied", "available", "reserved", "available"],
                )
        self.action(booking, "cancel", self.student)
        self.assertEqual(self.room_at("10:30")["status"], "available")
        self.assertIsNone(self.room_at("10:30")["reservedSeconds"])

    def test_adjacent_classes_and_bookings_switch_at_exact_start_and_end(self):
        TimetableDay.objects.create(
            room=self.room, date=self.day.date, start_time=time(9), end_time=time(10)
        )
        TimetableDay.objects.create(
            room=self.room, date=self.day.date, start_time=time(12), end_time=time(13)
        )
        booking = self.request_room()
        self.action(booking, "approve")
        for clock in ("09:45", "09:59"):
            self.assertEqual(self.room_at(clock)["status"], "occupied")
        self.assertEqual(self.room_at("10:00")["status"], "reserved")
        self.assertEqual(self.room_at("11:59")["status"], "reserved")
        self.assertEqual(self.room_at("12:00")["status"], "occupied")
        self.assertIsNone(self.room_at("12:00")["reservedSeconds"])

    def test_adjacent_approved_bookings_reset_remaining_time_at_boundary(self):
        first = self.request_room()
        second = self.request_room(self.other, startTime="12:00", endTime="13:00")
        self.action(first, "approve")
        self.action(second, "approve")
        self.assertEqual(self.room_at("11:59")["reservedSeconds"], 60)
        self.assertEqual(self.room_at("12:00")["status"], "reserved")
        self.assertEqual(self.room_at("12:00")["reservedSeconds"], 3600)
        self.assertEqual(self.room_at("13:00")["status"], "available")

    def test_reservation_end_uses_server_seconds_and_no_timetable_falls_back_to_unknown(
        self,
    ):
        TimetableDay.objects.all().delete()
        booking = self.request_room()
        self.action(booking, "approve")
        with patch(
            "rooms.views.timezone.now",
            return_value=booking.ends_at - timedelta(microseconds=1),
        ):
            data = self.client.get(f"/api/rooms/{self.room.code}/").data
            self.assertEqual(data["status"], "reserved")
            self.assertEqual(data["reservedSeconds"], 1)
        with patch("rooms.views.timezone.now", return_value=booking.ends_at):
            data = self.client.get(f"/api/rooms/{self.room.code}/").data
            self.assertEqual(data["status"], "unknown")
            self.assertIsNone(data["reservedUntil"])
        self.assertEqual(
            [slot["status"] for slot in data["hourlySchedule"]],
            ["unknown", "reserved", "unknown"],
        )
        self.action(booking, "cancel", self.student)
        self.assertEqual(self.room_at("10:30")["status"], "unknown")

    def test_approved_lecturer_booking_reserves_large_room(self):
        booking = self.request_room(self.lecturer, roomId=self.large.code)
        self.action(booking, "approve")
        data = self.client.get(
            f"/api/rooms/{self.large.code}/",
            {"date": str(self.day.date), "time": "10:30"},
        ).data
        self.assertEqual(data["status"], "reserved")
        self.assertEqual(data["reservedUntil"], booking.ends_at.isoformat())

    def test_ongoing_reservation_can_be_cancelled_and_releases_room(self):
        booking = self.request_room()
        self.action(booking, "approve")
        with patch(
            "django.utils.timezone.now",
            return_value=booking.starts_at + timedelta(minutes=30),
        ):
            self.client.force_authenticate(self.student)
            self.assertTrue(self.client.get("/api/reservations/").data[0]["canCancel"])
            self.assertEqual(
                self.action(booking, "cancel", self.student).status_code, 200
            )
        self.assertEqual(self.room_at("10:30")["status"], "available")

    def test_archived_history_is_hidden_immutable_and_does_not_block(self):
        booking = self.request_room()
        self.action(booking, "approve")
        Reservation.objects.filter(pk=booking.pk).update(is_archived=True)
        self.assertEqual(self.client.get("/api/reservations/").data, [])
        self.assertEqual(self.action(booking, "cancel").status_code, 404)
        self.assertEqual(self.room_at("10:30")["status"], "available")
        booking.refresh_from_db()
        with self.assertRaises(ValidationError):
            booking.save()
        self.request_room()
        TimetableDay.objects.create(
            room=self.room, date=self.day.date, start_time=time(10), end_time=time(11)
        )

    def test_status_filter_and_review_length_validation(self):
        booking = self.request_room()
        self.assertEqual(
            self.action(booking, "reject", note="a" * 501).status_code, 400
        )
        self.action(booking, "reject", note="Use another room.")
        self.assertEqual(
            len(self.client.get("/api/reservations/", {"status": "rejected"}).data), 1
        )
        self.assertEqual(
            self.client.get("/api/reservations/", {"status": "pending"}).data, []
        )
        self.assertEqual(
            self.client.get("/api/reservations/", {"status": "bad"}).status_code, 400
        )

    def test_request_details_are_immutable(self):
        booking = self.request_room()
        booking.purpose = "Changed"
        with self.assertRaises(ValidationError):
            booking.save()
        self.assertEqual(
            self.client.patch(
                f"/api/reservations/{booking.reference}/", {}, format="json"
            ).status_code,
            404,
        )

    def test_csrf_required_for_session_authenticated_mutations(self):
        browser = APIClient(enforce_csrf_checks=True)
        browser.force_login(self.student)
        self.assertEqual(
            browser.post(
                "/api/reservations/", self.payload(), format="json"
            ).status_code,
            403,
        )
        csrf = browser.get("/api/auth/csrf/").data["csrfToken"]
        response = browser.post(
            "/api/reservations/", self.payload(), format="json", HTTP_X_CSRFTOKEN=csrf
        )
        self.assertEqual(response.status_code, 201)
        url = f"/api/reservations/{response.data['refId']}/cancel/"
        self.assertEqual(browser.post(url, {}, format="json").status_code, 403)
        self.assertEqual(
            browser.post(url, {}, format="json", HTTP_X_CSRFTOKEN=csrf).status_code, 200
        )

    def test_admin_actions_use_same_conflict_checks_and_no_delete_or_add(self):
        first = self.request_room()
        self.request_room(self.other)
        self.client.force_authenticate(None)
        self.client.force_login(self.admin)
        url = reverse("admin:bookings_reservation_changelist")
        response = self.client.post(
            url,
            {
                "action": "approve_requests",
                "_selected_action": list(
                    Reservation.objects.values_list("pk", flat=True)
                ),
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Reservation.objects.filter(status="approved").count(), 1)
        self.assertContains(response, "overlaps an approved reservation")
        self.assertEqual(
            self.client.get(reverse("admin:bookings_reservation_add")).status_code, 403
        )
        self.assertEqual(
            self.client.get(
                reverse("admin:bookings_reservation_delete", args=[first.pk])
            ).status_code,
            403,
        )


class ReservationConcurrencyTests(TransactionTestCase):
    def setUp(self):
        (
            self.student,
            self.other,
            self.lecturer,
            self.admin,
            self.room,
            self.large,
            self.day,
        ) = fixtures()

    def pending(self, user):
        return Reservation.objects.create(
            room=self.room,
            user=user,
            date=self.day.date,
            start_time=time(10),
            end_time=time(12),
            purpose="Study",
        )

    def race(self, *operations):
        barrier = Barrier(len(operations))

        def run(operation):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                operation()
                return "saved"
            except (ValidationError, ImportProblem):
                return "conflict"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            results = list(pool.map(run, operations))
        self.assertCountEqual(results, ["saved", "conflict"])

    def test_simultaneous_approvals_cannot_double_book(self):
        first, second = self.pending(self.student), self.pending(self.other)
        self.race(
            lambda: change_reservation(first.reference, self.admin, "approve"),
            lambda: change_reservation(second.reference, self.admin, "approve"),
        )
        self.assertEqual(Reservation.objects.filter(status="approved").count(), 1)

    def test_approval_and_lecture_save_share_the_room_lock(self):
        booking = self.pending(self.student)
        self.race(
            lambda: change_reservation(booking.reference, self.admin, "approve"),
            lambda: TimetableDay.objects.create(
                room=self.room,
                date=self.day.date,
                start_time=time(10),
                end_time=time(11),
            ),
        )
        self.assertEqual(
            Reservation.objects.filter(status="approved").count()
            + TimetableDay.objects.count(),
            3,
        )

    def test_simultaneous_duplicate_submissions_create_one_request(self):
        self.race(
            lambda: self.pending(self.student), lambda: self.pending(self.student)
        )
        self.assertEqual(Reservation.objects.count(), 1)

    def test_approval_and_csv_import_cannot_double_book(self):
        booking = self.pending(self.student)
        course = Course.objects.create(
            code="CSC101", title="Computing", department="Computing"
        )
        text = timetable_csv(
            {
                "room": self.room.code,
                "course": course.code,
                "date": str(self.day.date),
                "start_time": "10:00",
                "end_time": "11:00",
                "academic_session": "2026/2027",
            }
        )
        fingerprint = preview_import(text).fingerprint
        self.race(
            lambda: change_reservation(booking.reference, self.admin, "approve"),
            lambda: apply_import(text, fingerprint, lambda entry, action: None),
        )
        self.assertEqual(
            Reservation.objects.filter(status="approved").count()
            + TimetableDay.objects.count(),
            3,
        )
