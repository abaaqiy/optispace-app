from datetime import date, time

from django.core.exceptions import ValidationError
from django.test import TestCase

from rooms.models import Building, Room
from .models import Course, TimetableDay


class SchedulingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.room = Room.objects.create(code="test", name="Test room", building=Building.objects.create(name="Test building", campus_zone="Science"), capacity=100, size_category="large", room_type="Classroom")
        cls.course = Course.objects.create(code="CSC101", title="Computing", department="Computer Science")

    def entry(self, start=8, end=10, **extra):
        return TimetableDay.objects.create(room=self.room, date=date(2030, 1, 15), start_time=time(start), end_time=time(end), course=self.course, academic_session="2029/2030", **extra)

    def test_end_must_be_after_start(self):
        for start, end in [(10, 10), (11, 10)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValidationError):
                self.entry(start, end)

    def test_overlaps_rejected_but_adjacent_classes_allowed(self):
        self.entry()
        for start, end in [(8, 10), (9, 11), (7, 11)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValidationError):
                self.entry(start, end)
        self.entry(10, 12)
        self.assertEqual(TimetableDay.objects.count(), 2)

    def test_same_time_on_another_date_is_allowed(self):
        entry = self.entry()
        entry.pk = None
        entry.date = date(2030, 1, 16)
        entry.save()
        self.assertEqual(TimetableDay.objects.count(), 2)

    def test_edit_can_move_room_date_and_times(self):
        entry = self.entry()
        entry.date = date(2030, 1, 16)
        entry.start_time = time(9)
        entry.save()
        entry.refresh_from_db()
        self.assertEqual(entry.date, date(2030, 1, 16))
        self.assertEqual(entry.start_time, time(9))
        self.assertEqual(entry.title, "CSC101 — Computing")

    def test_moving_to_an_occupied_room_is_rejected(self):
        self.entry()
        other = Room.objects.create(code="other", name="Other room", building=self.room.building, capacity=30, size_category="small", room_type="Classroom")
        entry = TimetableDay.objects.create(room=other, date=date(2030, 1, 15), start_time=time(8), end_time=time(10))
        entry.room = self.room
        with self.assertRaises(ValidationError):
            entry.save()
        entry.refresh_from_db()
        self.assertEqual(entry.room, other)

    def test_cancelled_class_can_be_replaced_but_cannot_be_restored_over_another(self):
        cancelled = self.entry(is_cancelled=True)
        replacement = self.entry()
        cancelled.is_cancelled = False
        with self.assertRaises(ValidationError):
            cancelled.save()
        cancelled.refresh_from_db()
        self.assertTrue(cancelled.is_cancelled)
        replacement.is_cancelled = True
        replacement.save()
        cancelled.is_cancelled = False
        cancelled.save()
        self.assertFalse(TimetableDay.objects.get(pk=cancelled.pk).is_cancelled)
