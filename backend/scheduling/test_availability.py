from datetime import UTC, date, datetime, time
from unittest.mock import patch

from rest_framework.test import APITestCase

from rooms.models import Building, Room

from .models import Course, TimetableDay


class AvailabilityAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.room = Room.objects.create(
            code="room-1",
            name="Demo Seminar Hall",
            building=Building.objects.create(name="Demo building", campus_zone="Demo Faculty"),
            room_type="Seminar Hall",
            capacity=100,
            size_category="small",
        )

        cls.day_date = date(2026, 11, 10)
        course = Course.objects.create(code="CSC101", title="Computing", department="Computing")
        later = Course.objects.create(code="CSC201", title="Programming", department="Computing")
        cls.morning = TimetableDay.objects.create(room=cls.room, date=cls.day_date, course=course, start_time=time(8), end_time=time(10))
        cls.afternoon = TimetableDay.objects.create(room=cls.room, date=cls.day_date, course=later, start_time=time(14), end_time=time(16))

    def room_at(self, clock):
        response = self.client.get(
            "/api/rooms/room-1/",
            {"date": "2026-11-10", "time": clock},
        )
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_time_boundaries(self):
        cases = [
            ("07:59", "reserved"),
            ("08:00", "occupied"),
            ("10:00", "available"),
            ("13:44", "available"),
            ("13:45", "reserved"),
            ("13:59", "reserved"),
            ("14:00", "occupied"),
            ("16:00", "available"),
            ("18:00", "available"),
        ]

        for clock, expected_status in cases:
            with self.subTest(time=clock):
                self.assertEqual(
                    self.room_at(clock)["status"],
                    expected_status,
                )

    def test_reserved_countdown_before_a_lecture(self):
        data = self.room_at("13:45")

        self.assertEqual(data["status"], "reserved")
        self.assertEqual(data["reservedSeconds"], 900)
        self.assertEqual(data["reservedUntil"], "2026-11-10T14:00:00+01:00")
        self.assertIsNone(data["currentSchedule"])
        self.assertEqual(
            data["nextSchedule"],
            "14:00 - CSC201 — Programming",
        )

    def test_missing_timetable_is_unknown(self):
        response = self.client.get(
            "/api/rooms/room-1/",
            {"date": "2026-11-11", "time": "09:00"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "unknown")

    def test_schedule_includes_free_gaps(self):
        slots = self.room_at("11:00")["hourlySchedule"]

        self.assertEqual(
            [slot["time"] for slot in slots],
            [
                "00:00 - 07:45",
                "07:45 - 08:00",
                "08:00 - 10:00",
                "10:00 - 13:45",
                "13:45 - 14:00",
                "14:00 - 16:00",
                "16:00 - 00:00",
            ],
        )
        self.assertEqual(
            [slot["occupied"] for slot in slots],
            [False, True, True, False, True, True, False],
        )

    def test_deleted_entry_is_removed_from_status(self):
        self.morning.delete()

        data = self.room_at("09:00")

        self.assertEqual(data["status"], "available")
        self.assertNotIn(
            "CSC101 — Computing",
            [slot["event"] for slot in data["hourlySchedule"]],
        )

    def test_removing_all_entries_makes_the_date_unknown(self):
        TimetableDay.objects.all().delete()
        data = self.room_at("09:00")
        self.assertEqual(data["status"], "unknown")
        self.assertEqual(data["hourlySchedule"], [])

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


    def test_reserved_overrides_ongoing_lecture_for_back_to_back_sessions(self):
        TimetableDay.objects.create(room=self.room, date=self.day_date, start_time=time(10), end_time=time(11))
        self.assertEqual(self.room_at("09:44")["status"], "occupied")
        before = self.room_at("09:45")
        self.assertEqual(before["status"], "reserved")
        self.assertEqual(before["currentSchedule"], "CSC101 — Computing")
        self.assertEqual(before["reservedSeconds"], 900)
        started = self.room_at("10:00")
        self.assertEqual(started["status"], "occupied")
        self.assertEqual(started["currentSchedule"], "Scheduled class")
        self.assertIsNone(started["reservedSeconds"])

    def test_deleted_next_class_has_no_reserved_window(self):
        self.afternoon.delete()
        data = self.room_at("13:50")
        self.assertEqual(data["status"], "available")
        self.assertIsNone(data["reservedUntil"])

    def test_second_precision_and_server_timeline_match(self):
        with patch("rooms.views.timezone.now", return_value=datetime(2026, 11, 10, 12, 59, 59, 500000, tzinfo=UTC)):
            data = self.client.get("/api/rooms/room-1/").data
        self.assertEqual(data["reservedSeconds"], 1)
        self.assertEqual(data["status"], "reserved")
        periods = data["statusTimeline"]
        self.assertEqual(periods[0]["start"], "2026-11-10T00:00:00+01:00")
        self.assertEqual(periods[-1]["end"], "2026-11-11T00:00:00+01:00")
        for left, right in zip(periods, periods[1:]):
            self.assertEqual(left["end"], right["start"])
        self.assertEqual([period["status"] for period in periods], ["available", "reserved", "occupied", "available", "reserved", "occupied", "available"])

    def test_reserved_window_before_first_class(self):
        self.morning.start_time = time(8, 10)
        self.morning.save()
        self.assertEqual(self.room_at("07:54")["status"], "available")
        self.assertEqual(self.room_at("07:55")["reservedSeconds"], 900)
        self.assertEqual(self.room_at("08:00")["reservedSeconds"], 600)
        self.assertEqual(self.room_at("08:10")["status"], "occupied")

    def test_reserved_filter_excludes_other_statuses(self):
        params = {"date": "2026-11-10", "time": "13:45"}
        reserved = self.client.get("/api/rooms/", {**params, "status": "reserved"})
        self.assertEqual([item["id"] for item in reserved.data], [self.room.code])
        self.assertEqual(self.client.get("/api/rooms/", {**params, "status": "available"}).data, [])
        self.assertEqual(self.client.get("/api/rooms/", {**params, "status": "occupied"}).data, [])
        self.assertEqual(self.client.get("/api/rooms/", {"status": "soon"}).status_code, 400)

    def test_reserved_is_exclusive_to_seminar_and_event_halls(self):
        for kind in ("Lecture Theatre", "Classroom", "Reading Room", "Computer Laboratory", "Laboratory", "Studio", "Meeting Room", "Custom Hall"):
            with self.subTest(kind=kind):
                self.room.room_type = kind
                self.room.save()
                data = self.room_at("13:50")
                self.assertEqual(data["status"], "available")
                self.assertIsNone(data["reservedUntil"])
                self.assertFalse(any(slot["status"] == "reserved" for slot in data["statusTimeline"]))
                self.assertEqual(self.room_at("14:00")["status"], "occupied")
        for kind in ("Seminar Room", "Seminar Hall", "Event Hall", " seminar hall "):
            with self.subTest(kind=kind):
                self.room.room_type = kind
                self.room.save()
                self.assertEqual(self.room_at("13:50")["status"], "reserved")

    def test_lecture_room_stays_occupied_between_back_to_back_classes(self):
        self.room.room_type = "Lecture Theatre"
        self.room.save()
        TimetableDay.objects.create(room=self.room, date=self.day_date, start_time=time(10), end_time=time(11))
        for clock in ("09:45", "09:59", "10:00", "10:59"):
            self.assertEqual(self.room_at(clock)["status"], "occupied")
        self.assertEqual(self.room_at("11:00")["status"], "available")

    def test_cancellation_frees_time_and_restoring_reoccupies_it(self):
        self.morning.is_cancelled = True
        self.morning.save()
        data = self.room_at("09:00")
        self.assertEqual(data["status"], "available")
        self.assertIsNone(data["currentSchedule"])
        schedule = self.client.get("/api/schedules/", {"date": str(self.day_date)}).data
        self.assertEqual(schedule[0]["status"], "Cancelled")
        self.assertFalse(schedule[0]["isApproved"])
        self.morning.is_cancelled = False
        self.morning.save()
        self.assertEqual(self.room_at("09:00")["status"], "occupied")

    def test_all_cancelled_classes_leave_room_available_instead_of_unknown(self):
        for entry in (self.morning, self.afternoon):
            entry.is_cancelled = True
            entry.save()
        data = self.room_at("09:00")
        self.assertEqual(data["status"], "available")
        self.assertEqual([slot["status"] for slot in data["statusTimeline"]], ["available"])
        self.assertEqual(TimetableDay.objects.count(), 2)

    def test_cancelled_upcoming_event_has_no_reserved_warning(self):
        self.afternoon.is_cancelled = True
        self.afternoon.save()
        self.assertEqual(self.room_at("13:50")["status"], "available")
        self.assertIsNone(self.room_at("13:50")["reservedUntil"])

    def test_other_rooms_use_entire_school_timetable_independently_of_filters(self):
        other = Room.objects.create(code="other", name="Other classroom", building=self.room.building, capacity=30, size_category="large", room_type="Classroom")
        data = self.client.get("/api/rooms/other/", {"date": str(self.day_date), "time": "09:00"}).data
        self.assertEqual(data["status"], "available")
        filtered = self.client.get("/api/rooms/", {"date": str(self.day_date), "time": "09:00", "category": "large", "status": "available"}).data
        self.assertEqual([row["id"] for row in filtered], [other.code])

    def test_cancelling_one_class_does_not_release_an_active_replacement(self):
        self.morning.is_cancelled = True
        self.morning.save()
        TimetableDay.objects.create(room=self.room, date=self.day_date, start_time=time(8), end_time=time(10))
        data = self.room_at("09:00")
        self.assertEqual(data["status"], "occupied")
        self.assertEqual(data["currentSchedule"], "Scheduled class")
