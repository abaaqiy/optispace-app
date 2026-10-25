from concurrent.futures import ThreadPoolExecutor
from datetime import date, time, timedelta
from threading import Barrier

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from rooms.models import Room
from scheduling.models import Allocation, TimetableDay

from .models import Reservation
from .services import change_reservation


def fixtures():
    users = get_user_model().objects
    student = users.create_user(username="reader", email="reader@student.oauife.edu.ng", first_name="Reader")
    other = users.create_user(username="other", email="other@student.oauife.edu.ng")
    lecturer = users.create_user(username="lecturer", email="lecturer@oauife.edu.ng", role="lecturer")
    admin = users.create_superuser(username="reviewer", email="reviewer@oauife.edu.ng", password="Test-only-271!")
    room = Room.objects.create(code="reading-1", name="Reading Room", zone="Science", capacity=20, size_category="small", room_type="Reading Room")
    large = Room.objects.create(code="lecture-1", name="Lecture Room", zone="Science", capacity=200, size_category="large", room_type="Lecture Theatre")
    future_date = timezone.localdate() + timedelta(days=30)
    day = TimetableDay.objects.create(room=room, date=future_date, coverage_start=time(8), coverage_end=time(18), is_published=True)
    TimetableDay.objects.create(room=large, date=future_date, coverage_start=time(8), coverage_end=time(18), is_published=True)
    return student, other, lecturer, admin, room, large, day


class ReservationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student, cls.other, cls.lecturer, cls.admin, cls.room, cls.large, cls.day = fixtures()

    def setUp(self):
        self.client.force_authenticate(self.student)

    def payload(self, **changes):
        return {"roomId": self.room.code, "date": str(self.day.date), "startTime": "10:00", "endTime": "12:00", "purpose": "Group study", **changes}

    def request_room(self, user=None, **changes):
        self.client.force_authenticate(user or self.student)
        response = self.client.post("/api/reservations/", self.payload(**changes), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return Reservation.objects.get(reference=response.data["refId"])

    def action(self, reservation, action, user=None, **data):
        self.client.force_authenticate(user or self.admin)
        return self.client.post(f"/api/reservations/{reservation.reference}/{action}/", data, format="json")

    def room_at(self, clock):
        return self.client.get(f"/api/rooms/{self.room.code}/", {"date": str(self.day.date), "time": clock}).data

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
        self.assertEqual([item["refId"] for item in self.client.get("/api/reservations/").data], [first.reference])
        self.assertEqual(self.action(second, "cancel", self.student).status_code, 404)
        self.assertEqual(self.action(first, "approve", self.student).status_code, 403)
        self.assertEqual(self.action(first, "reject", self.lecturer).status_code, 404)
        self.client.force_authenticate(self.admin)
        self.assertEqual(len(self.client.get("/api/reservations/").data), 2)
        self.assertEqual(self.client.post("/api/reservations/", self.payload(), format="json").status_code, 403)

    def test_students_cannot_request_large_rooms_but_lecturers_can(self):
        response = self.client.post("/api/reservations/", self.payload(roomId=self.large.code), format="json")
        self.assertEqual(response.status_code, 400)
        self.request_room(self.lecturer, roomId=self.large.code)

    def test_anonymous_inactive_and_staff_without_superuser_cannot_review(self):
        booking = self.request_room()
        anonymous = APIClient()
        self.assertEqual(anonymous.get("/api/reservations/").status_code, 403)
        self.assertEqual(anonymous.post("/api/reservations/", self.payload(), format="json").status_code, 403)
        self.student.is_active = False
        self.student.save()
        self.assertEqual(self.client.post("/api/reservations/", self.payload(startTime="13:00", endTime="14:00"), format="json").status_code, 400)
        self.other.is_staff = True
        self.other.save()
        own = self.request_room(self.other)
        self.assertEqual(self.action(own, "approve", self.other).status_code, 403)
        self.assertEqual(self.action(booking, "approve").status_code, 409)

    def test_spoofed_owner_or_status_and_invalid_inputs_are_rejected(self):
        for changes in (
            {"user": self.other.pk}, {"status": "approved"}, {"organizer": "Someone else"},
            {"date": "bad"}, {"date": str(timezone.localdate() - timedelta(days=1))},
            {"startTime": "12:00"}, {"endTime": "09:00"}, {"startTime": "25:00"},
            {"startTime": "10:00:30"}, {"purpose": "   "}, {"purpose": "a" * 201}, {"roomId": "missing"},
        ):
            with self.subTest(changes=changes):
                self.assertEqual(self.client.post("/api/reservations/", self.payload(**changes), format="json").status_code, 400)
        self.assertEqual(Reservation.objects.count(), 0)

    def test_request_needs_published_coverage(self):
        for changes in ({"startTime": "07:00"}, {"endTime": "19:00"}, {"date": str(self.day.date + timedelta(days=1))}):
            self.assertEqual(self.client.post("/api/reservations/", self.payload(**changes), format="json").status_code, 400)
        self.day.is_published = False
        self.day.save()
        self.assertEqual(self.client.post("/api/reservations/", self.payload(), format="json").status_code, 400)

    def test_duplicate_request_does_not_create_second_record(self):
        self.request_room()
        self.assertEqual(self.client.post("/api/reservations/", self.payload(), format="json").status_code, 400)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_lecture_conflicts_block_requests_and_adjacent_times_work(self):
        Allocation.objects.create(timetable=self.day, title="Lecture", start_time=time(9), end_time=time(11))
        self.assertEqual(self.client.post("/api/reservations/", self.payload(), format="json").status_code, 400)
        self.request_room(startTime="11:00")

    def test_approve_updates_availability_without_exposing_private_data(self):
        booking = self.request_room(purpose="Private discussion")
        response = self.action(booking, "approve", note="Confirmed")
        self.assertEqual(response.status_code, 200, response.data)
        booking.refresh_from_db()
        self.assertEqual(booking.reviewed_by, self.admin)
        self.assertEqual(booking.review_note, "Confirmed")
        self.assertIsNotNone(booking.reviewed_at)
        data = self.room_at("10:00")
        self.assertEqual(data["status"], "reserved")
        self.assertEqual(data["currentSchedule"], "Reserved")
        self.assertNotIn("Private discussion", str(data))
        self.assertNotIn(self.student.email, str(data))
        self.assertEqual(self.room_at("12:00")["status"], "available")
        self.assertEqual(self.room_at("09:30")["status"], "soon")
        self.assertEqual([slot["reserved"] for slot in data["hourlySchedule"]], [False, True, False])
        rooms = self.client.get("/api/rooms/", {"date": str(self.day.date), "time": "10:30", "status": "reserved"}).data
        self.assertEqual([room["id"] for room in rooms], [self.room.code])

    def test_only_one_overlapping_request_can_be_approved(self):
        first = self.request_room()
        second = self.request_room(self.other)
        self.assertEqual(self.action(first, "approve").status_code, 200)
        self.assertEqual(self.action(second, "approve").status_code, 409)
        second.refresh_from_db()
        self.assertEqual(second.status, "pending")
        self.client.force_authenticate(self.lecturer)
        self.assertEqual(self.client.post("/api/reservations/", self.payload(), format="json").status_code, 400)
        adjacent = self.request_room(self.lecturer, startTime="12:00", endTime="13:00")
        self.assertEqual(self.action(adjacent, "approve").status_code, 200)

    def test_approval_rechecks_new_lecture_or_unpublished_timetable(self):
        booking = self.request_room()
        lecture = Allocation.objects.create(timetable=self.day, title="New lecture", start_time=time(10), end_time=time(11))
        self.assertEqual(self.action(booking, "approve").status_code, 409)
        lecture.is_cancelled = True
        lecture.save()
        self.day.is_published = False
        self.day.save()
        self.assertEqual(self.action(booking, "approve").status_code, 409)

    def test_approved_reservation_blocks_lecture_creation_edit_and_restore(self):
        lecture = Allocation.objects.create(timetable=self.day, title="Lecture", start_time=time(12), end_time=time(13))
        booking = self.request_room()
        self.assertEqual(self.action(booking, "approve").status_code, 200)
        with self.assertRaises(ValidationError):
            Allocation.objects.create(timetable=self.day, title="Conflicting lecture", start_time=time(11), end_time=time(13))
        lecture.start_time = time(11)
        with self.assertRaises(ValidationError):
            lecture.save()
        cancelled = Allocation.objects.create(timetable=self.day, title="Cancelled lecture", start_time=time(10), end_time=time(11), is_cancelled=True)
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
        Reservation.objects.filter(pk=booking.pk).update(date=timezone.localdate() - timedelta(days=1))
        self.assertEqual(self.action(booking, "approve").status_code, 409)
        self.assertEqual(self.action(booking, "cancel", self.student).status_code, 409)
        self.assertEqual(self.action(booking, "reject").status_code, 200)

    def test_reserved_time_remains_visible_if_timetable_is_unpublished_or_removed(self):
        booking = self.request_room()
        self.action(booking, "approve")
        self.day.is_published = False
        self.day.save()
        self.assertEqual(self.room_at("10:30")["status"], "reserved")
        self.assertEqual(self.room_at("09:00")["status"], "unknown")
        self.assertEqual(len(self.room_at("09:00")["hourlySchedule"]), 1)
        self.day.delete()
        self.assertEqual(self.room_at("10:30")["status"], "reserved")

    def test_request_details_are_immutable(self):
        booking = self.request_room()
        booking.purpose = "Changed"
        with self.assertRaises(ValidationError):
            booking.save()
        self.assertEqual(self.client.patch(f"/api/reservations/{booking.reference}/", {}, format="json").status_code, 404)

    def test_csrf_required_for_session_authenticated_mutations(self):
        browser = APIClient(enforce_csrf_checks=True)
        browser.force_login(self.student)
        self.assertEqual(browser.post("/api/reservations/", self.payload(), format="json").status_code, 403)
        csrf = browser.get("/api/auth/csrf/").data["csrfToken"]
        response = browser.post("/api/reservations/", self.payload(), format="json", HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code, 201)
        url = f"/api/reservations/{response.data['refId']}/cancel/"
        self.assertEqual(browser.post(url, {}, format="json").status_code, 403)
        self.assertEqual(browser.post(url, {}, format="json", HTTP_X_CSRFTOKEN=csrf).status_code, 200)

    def test_admin_actions_use_same_conflict_checks_and_no_delete_or_add(self):
        first = self.request_room()
        self.request_room(self.other)
        self.client.force_authenticate(None)
        self.client.force_login(self.admin)
        url = reverse("admin:bookings_reservation_changelist")
        response = self.client.post(url, {"action": "approve_requests", "_selected_action": list(Reservation.objects.values_list("pk", flat=True))}, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Reservation.objects.filter(status="approved").count(), 1)
        self.assertContains(response, "overlaps an approved reservation")
        self.assertEqual(self.client.get(reverse("admin:bookings_reservation_add")).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin:bookings_reservation_delete", args=[first.pk])).status_code, 403)


class ReservationConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.student, self.other, self.lecturer, self.admin, self.room, self.large, self.day = fixtures()

    def pending(self, user):
        return Reservation.objects.create(room=self.room, user=user, date=self.day.date, start_time=time(10), end_time=time(12), purpose="Study")

    def race(self, *operations):
        barrier = Barrier(len(operations))
        def run(operation):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                operation()
                return "saved"
            except ValidationError:
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
            lambda: Allocation.objects.create(timetable=self.day, title="Lecture", start_time=time(10), end_time=time(11)),
        )
        self.assertEqual(Reservation.objects.filter(status="approved").count() + Allocation.objects.count(), 1)

    def test_simultaneous_duplicate_submissions_create_one_request(self):
        self.race(lambda: self.pending(self.student), lambda: self.pending(self.student))
        self.assertEqual(Reservation.objects.count(), 1)
