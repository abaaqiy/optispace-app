from datetime import date, time

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from rooms.models import Building, Room
from .models import Course, TimetableDay


class TimetableAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser(username="timetable-admin", email="timetable-admin@oauife.edu.ng", password="Test-only-982!")
        cls.room = Room.objects.create(code="timetable-test", name="Test room", building=Building.objects.create(name="Science building", campus_zone="Science"), capacity=100, size_category="large", room_type="Classroom")
        cls.course = Course.objects.create(code="CSC101", title="Computing", department="Computer Science")

    def setUp(self):
        self.client.force_login(self.admin)

    def post_entry(self, entry=None, **extra):
        data = dict(room=self.room.pk, date="2030-01-15", start_time="10:00", end_time="12:00", course=self.course.pk, academic_session="2029/2030", _save="Save")
        data.update(extra)
        url = reverse("admin:scheduling_timetableday_change", args=[entry.pk]) if entry else reverse("admin:scheduling_timetableday_add")
        return self.client.post(url, data)

    def test_only_two_categories_and_timetable_cancellation_field(self):
        self.assertEqual({m.__name__ for m in admin.site._registry if m._meta.app_label == "scheduling"}, {"Course", "TimetableDay"})
        response = self.client.get(reverse("admin:scheduling_timetableday_add"))
        self.assertEqual(set(response.context["adminform"].form.fields), {"room", "date", "start_time", "end_time", "course", "academic_session", "is_cancelled"})
        self.assertEqual(response.context["inline_admin_formsets"], [])
        self.assertNotContains(response, "Add another Lecture")
        self.assertNotContains(response, "is_published")
        self.assertEqual(self.client.get("/admin/scheduling/allocation/").status_code, 404)

    def test_save_one_entry_updates_room_and_campus_schedule(self):
        self.assertEqual(self.post_entry().status_code, 302)
        entry = TimetableDay.objects.get()
        self.assertEqual(entry.course, self.course)
        self.assertEqual(entry.academic_session, "2029/2030")
        data = self.client.get("/api/rooms/timetable-test/", {"date": "2030-01-15", "time": "09:45"}).json()
        self.assertEqual(data["status"], "available")
        self.assertIsNone(data["reservedSeconds"])
        schedule = self.client.get("/api/schedules/", {"date": "2030-01-15"}).json()
        self.assertEqual(schedule[0]["purpose"], "CSC101 — Computing")
        self.assertEqual(schedule[0]["timeSlot"], "10:00 - 12:00")

    def test_course_session_and_valid_times_required(self):
        for extra in ({"course": ""}, {"academic_session": ""}, {"end_time": "09:00"}, {"course": 999999}):
            with self.subTest(extra=extra):
                response = self.post_entry(**extra)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context["adminform"].form.errors)
                self.assertFalse(TimetableDay.objects.exists())

    def test_multiple_classes_and_overlap_error_preserves_input(self):
        self.assertEqual(self.post_entry().status_code, 302)
        self.assertEqual(self.post_entry(start_time="12:00", end_time="14:00").status_code, 302)
        response = self.post_entry(start_time="11:00", end_time="13:00")
        self.assertContains(response, "overlapping")
        self.assertEqual(response.context["adminform"].form["start_time"].value(), "11:00")
        self.assertEqual(TimetableDay.objects.count(), 2)

    def test_all_six_fields_remain_editable(self):
        self.post_entry()
        entry = TimetableDay.objects.get()
        self.assertEqual(self.post_entry(entry, date="2030-01-16", start_time="09:00").status_code, 302)
        entry.refresh_from_db()
        self.assertEqual(entry.date, date(2030, 1, 16))
        self.assertEqual(entry.start_time, time(9))
        self.assertEqual(self.client.get("/api/schedules/", {"date": "2030-01-15"}).json(), [])

    def test_admin_can_cancel_and_restore_a_class_without_deleting_it(self):
        self.post_entry()
        entry = TimetableDay.objects.get()
        params = {"date": "2030-01-15", "time": "10:30"}
        self.assertEqual(self.client.get("/api/rooms/timetable-test/", params).json()["status"], "occupied")
        self.assertEqual(self.post_entry(entry, is_cancelled="on").status_code, 302)
        entry.refresh_from_db()
        self.assertTrue(entry.is_cancelled)
        self.assertEqual(self.client.get("/api/rooms/timetable-test/", params).json()["status"], "available")
        self.assertEqual(TimetableDay.objects.count(), 1)
        self.assertEqual(self.post_entry(entry).status_code, 302)
        self.assertEqual(self.client.get("/api/rooms/timetable-test/", params).json()["status"], "occupied")
