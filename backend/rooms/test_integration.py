from datetime import date, time

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from scheduling.models import Course, TimetableDay

from .models import Building, Facility, Room


class RoomIntegrationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.building = Building.objects.create(name="Test Science Building", campus_zone="Science")
        cls.room = Room.objects.create(
            code="science-101", name="Science Room 101", building=cls.building,
            room_number="101", capacity=80, size_category="large", room_type="Lecture room",
        )
        cls.other = Room.objects.create(
            code="reading-1", name="Reading Room", building=Building.objects.create(name="Library building", campus_zone="Library"), capacity=20,
            size_category="small", room_type="Study room",
        )
        wifi = Facility.objects.create(code="wifi")
        projector = Facility.objects.create(code="projector")
        cls.room.facilities.add(wifi, projector)
        cls.other.facilities.add(wifi)
        cls.course = Course.objects.create(code="CSC101", title="Introduction", department="Computing")
        cls.day = TimetableDay.objects.create(room=cls.room, date=date(2030, 5, 20), start_time=time(9), end_time=time(11), course=cls.course, academic_session="2029/2030")
        cls.admin = get_user_model().objects.create_superuser(
            username="test-admin", email="test-admin@oauife.edu.ng", password="Test-Admin-932!",
        )

    def test_room_contract_preserves_existing_fields_and_adds_location(self):
        response = self.client.get("/api/rooms/science-101/", {"date": "2030-05-20", "time": "09:30"})
        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertEqual(data["id"], "science-101")
        self.assertEqual(data["type"], "Lecture room")
        self.assertEqual(data["sizeCategory"], "large")
        self.assertEqual(set(data["facilities"]), {"wifi", "projector"})
        self.assertEqual(data["zone"], "Science")
        self.assertEqual(data["building"], {"id": self.building.pk, "name": self.building.name})
        self.assertEqual(data["roomNumber"], "101")
        self.assertEqual(data["status"], "occupied")
        self.assertEqual(data["availabilityAt"], "2030-05-20T09:30:00+01:00")
        self.assertEqual(len(data["hourlySchedule"]), 3)

    def test_room_filters_combine_and_require_all_facilities(self):
        response = self.client.get("/api/rooms/", {
            "zone": "Science", "building": self.building.pk, "capacity": 50,
            "category": "large", "facilities": ["wifi", "projector"],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], ["science-101"])
        response = self.client.get("/api/rooms/", {"zone": "Library", "facilities": ["wifi", "projector"]})
        self.assertEqual(response.data, [])

    def test_room_is_filtered_by_its_building_zone(self):
        response = self.client.get("/api/rooms/", {"zone": "Library", "category": "small"})
        self.assertEqual([item["id"] for item in response.data], ["reading-1"])
        self.assertEqual(response.data[0]["building"]["id"], self.other.building_id)
        self.assertEqual(response.data[0]["status"], "unknown")

    def test_available_filter_includes_free_period_before_a_lecture(self):
        response = self.client.get("/api/rooms/", {
            "date": "2030-05-20", "time": "08:30", "status": "available", "category": "large",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data], ["science-101"])
        self.assertEqual(response.data[0]["status"], "available")
        response = self.client.get("/api/rooms/", {
            "date": "2030-05-20", "time": "10:00", "status": "available", "category": "large",
        })
        self.assertEqual(response.data, [])

    def test_invalid_filters_return_400(self):
        for query in (
            {"capacity": "many"}, {"capacity": "0"}, {"facilities": ["not-a-facility"]},
            {"category": "giant"}, {"status": "bogus"}, {"building": "-1"},
            {"date": "2030-05-20"}, {"time": "12:00"},
        ):
            with self.subTest(query=query):
                self.assertEqual(self.client.get("/api/rooms/", query).status_code, 400)

    def test_filter_options_use_saved_campus_zones(self):
        response = self.client.get("/api/rooms/filters/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["zones"], ["Library", "Science"])
        self.assertIn({"code": "wifi", "label": "Wi-Fi"}, response.data["facilities"])

    def test_campus_schedule_uses_existing_table_contract(self):
        response = self.client.get("/api/schedules/", {"date": "2030-05-20"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        row = response.data[0]
        self.assertEqual(row["roomId"], self.room.code)
        self.assertEqual(row["purpose"], self.day.title)
        self.assertEqual(row["organizer"], "Computing")
        self.assertEqual(row["timeSlot"], "09:00 - 11:00")
        self.assertEqual(row["date"], "2030-05-20")
        self.assertEqual(row["status"], "Scheduled")
        self.assertTrue(row["isApproved"])
        self.assertEqual(self.client.get("/api/schedules/", {"date": "bad"}).status_code, 400)

    def test_deleted_timetable_disappears_from_schedule(self):
        self.day.delete()
        self.assertEqual(self.client.get("/api/schedules/", {"date": "2030-05-20"}).data, [])

    def test_non_admin_cannot_edit_room_or_timetable(self):
        student = get_user_model().objects.create_user(
            username="student-viewer", email="viewer@student.oauife.edu.ng", password="Test-Student-932!",
        )
        self.client.force_login(student)
        for url in (
            reverse("admin:rooms_room_change", args=[self.room.pk]),
            reverse("admin:scheduling_timetableday_change", args=[self.day.pk]),
        ):
            self.assertEqual(self.client.post(url, {}).status_code, 302)
        self.room.refresh_from_db()
        self.assertEqual(self.room.capacity, 80)
