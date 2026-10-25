from datetime import date, time

from django.contrib import admin
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from rooms.models import Building, Room
from scheduling.models import TimetableDay
from .models import Reservation


class RetiredBookingsTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = get_user_model().objects.create_user(username="reader", email="reader@student.oauife.edu.ng")
        cls.lecturer = get_user_model().objects.create_user(username="lecturer", email="lecturer@oauife.edu.ng", role="lecturer")
        cls.admin = get_user_model().objects.create_superuser(username="manager", email="manager@oauife.edu.ng", password="Test-only-393!")
        cls.room = Room.objects.create(code="reading", name="Reading room", building=Building.objects.create(name="Science building", campus_zone="Science"), capacity=20, size_category="small", room_type="Reading Room")
        cls.day = TimetableDay.objects.create(room=cls.room, date=date(2030, 1, 5), start_time=time(8), end_time=time(9))
        cls.archived = Reservation.objects.create(room=cls.room, user=cls.student, date=cls.day.date, start_time=time(10), end_time=time(12), purpose="Historical request", status="approved")

    def test_former_endpoints_are_removed_for_every_role(self):
        for user in (None, self.student, self.lecturer, self.admin):
            self.client.force_authenticate(user)
            for path in ("/api/reservations/", *(f"/api/reservations/{self.archived.reference}/{action}/" for action in ("approve", "reject", "cancel"))):
                with self.subTest(user=user, path=path):
                    self.assertEqual(self.client.get(path).status_code, 404)
                    self.assertEqual(self.client.post(path, {}, format="json").status_code, 404)
        self.archived.refresh_from_db()
        self.assertEqual(self.archived.status, "approved")
        self.assertEqual(Reservation.objects.count(), 1)

    def test_archived_bookings_do_not_change_status_or_block_lectures(self):
        data = self.client.get('/api/rooms/reading/', {'date': str(self.day.date), 'time': '10:30'}).data
        self.assertEqual(data['status'], 'available')
        self.assertNotIn('Historical request', str(data))
        TimetableDay.objects.create(room=self.room, date=self.day.date, start_time=time(10), end_time=time(12))
        data = self.client.get('/api/rooms/reading/', {'date': str(self.day.date), 'time': '10:30'}).data
        self.assertEqual(data['status'], 'occupied')

    def test_no_booking_controls_in_admin(self):
        self.assertFalse(admin.site.is_registered(Reservation))
        self.client.force_login(self.admin)
        self.assertNotContains(self.client.get('/admin/'), 'bookings/reservation')
        self.assertEqual(self.client.get('/admin/bookings/reservation/').status_code, 404)
