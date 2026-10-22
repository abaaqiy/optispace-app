from datetime import UTC, date, datetime, time
from unittest.mock import patch

from rest_framework.test import APITestCase

from rooms.models import Room

from .models import Allocation, TimetableDay


class AvailabilityAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.room = Room.objects.create(
            code="room-1",
            name="Demo Lecture Theatre",
            zone="Demo Faculty",
            room_type="Lecture Theatre",
            capacity=100,
            size_category="small",
        )

        cls.day = TimetableDay.objects.create(
            room=cls.room,
            date=date(2026, 11, 10),
            coverage_start=time(8),
            coverage_end=time(18),
            is_published=True,
        )

        cls.morning = Allocation.objects.create(
            timetable=cls.day,
            title="CSC 101 Lecture",
            start_time=time(8),
            end_time=time(10),
        )

        Allocation.objects.create(
            timetable=cls.day,
            title="CSC 201 Lecture",
            start_time=time(14),
            end_time=time(16),
        )

    def room_at(self, clock):
        response = self.client.get(
            "/api/rooms/room-1/",
            {"date": "2026-11-10", "time": clock},
        )
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_time_boundaries(self):
        cases = [
            ("07:59", "unknown"),
            ("08:00", "occupied"),
            ("10:00", "available"),
            ("14:00", "occupied"),
            ("16:00", "available"),
            ("18:00", "unknown"),
        ]

        for clock, expected_status in cases:
            with self.subTest(time=clock):
                self.assertEqual(
                    self.room_at(clock)["status"],
                    expected_status,
                )

    def test_soon_means_currently_free(self):
        data = self.room_at("13:30")

        self.assertEqual(data["status"], "soon")
        self.assertIsNone(data["currentSchedule"])
        self.assertEqual(
            data["nextSchedule"],
            "14:00 - CSC 201 Lecture",
        )

    def test_missing_or_unpublished_timetable_is_unknown(self):
        response = self.client.get(
            "/api/rooms/room-1/",
            {"date": "2026-11-11", "time": "09:00"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "unknown")

        self.day.is_published = False
        self.day.save()

        data = self.room_at("09:00")
        self.assertEqual(data["status"], "unknown")
        self.assertEqual(data["hourlySchedule"], [])

    def test_schedule_includes_free_gaps(self):
        slots = self.room_at("11:00")["hourlySchedule"]

        self.assertEqual(
            [slot["time"] for slot in slots],
            [
                "08:00 - 10:00",
                "10:00 - 14:00",
                "14:00 - 16:00",
                "16:00 - 18:00",
            ],
        )
        self.assertEqual(
            [slot["occupied"] for slot in slots],
            [True, False, True, False],
        )

    def test_cancelled_session_is_ignored(self):
        self.morning.is_cancelled = True
        self.morning.save()

        data = self.room_at("09:00")

        self.assertEqual(data["status"], "available")
        self.assertNotIn(
            "CSC 101 Lecture",
            [slot["event"] for slot in data["hourlySchedule"]],
        )

    def test_empty_published_day_is_free_within_coverage(self):
        self.day.allocations.all().delete()

        data = self.room_at("09:00")

        self.assertEqual(data["status"], "available")
        self.assertEqual(len(data["hourlySchedule"]), 1)
        self.assertEqual(
            data["hourlySchedule"][0]["time"],
            "08:00 - 18:00",
        )
        self.assertFalse(data["hourlySchedule"][0]["occupied"])

    def test_invalid_query_returns_400(self):
        invalid_queries = [
            {"date": "2026-11-10"},
            {"time": "09:00"},
            {"date": "not-a-date", "time": "09:00"},
            {"date": "2026-11-10", "time": "25:00"},
        ]

        for query in invalid_queries:
            with self.subTest(query=query):
                response = self.client.get(
                    "/api/rooms/room-1/",
                    query,
                )
                self.assertEqual(response.status_code, 400)

    def test_list_uses_requested_time(self):
        response = self.client.get(
            "/api/rooms/",
            {"date": "2026-11-10", "time": "09:00"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["status"], "occupied")
        self.assertEqual(
            response.data[0]["availabilityAt"],
            "2026-11-10T09:00:00+01:00",
        )

    @patch("rooms.views.timezone.now")
    def test_default_uses_current_lagos_time(self, mock_now):
        # 08:00 UTC is 09:00 in Lagos.
        mock_now.return_value = datetime(
            2026, 11, 10, 8, 0, tzinfo=UTC,
        )

        response = self.client.get("/api/rooms/room-1/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "occupied")
        self.assertEqual(
            response.data["availabilityAt"],
            "2026-11-10T09:00:00+01:00",
        )

