from datetime import date, time

from django.core.exceptions import ValidationError
from django.test import TestCase

from rooms.models import Room

from .models import Allocation, TimetableDay


class SchedulingTests(TestCase):
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
            date=date(2026, 10, 22),
            coverage_start=time(8, 0),
            coverage_end=time(18, 0),
        )

    def create_allocation(self, start_hour, end_hour, **extra):
        return Allocation.objects.create(
            timetable=self.day,
            title="Demo lecture",
            start_time=time(start_hour, 0),
            end_time=time(end_hour, 0),
            **extra,
        )

    def test_timetable_starts_unpublished(self):
        self.assertFalse(self.day.is_published)

    def test_duplicate_room_date_is_rejected(self):
        with self.assertRaises(ValidationError):
            TimetableDay.objects.create(
                room=self.room,
                date=self.day.date,
                coverage_start=time(8, 0),
                coverage_end=time(18, 0),
            )

    def test_end_must_be_after_start(self):
        for start_hour, end_hour in [(10, 10), (11, 10)]:
            with self.subTest(start=start_hour, end=end_hour):
                with self.assertRaises(ValidationError):
                    self.create_allocation(start_hour, end_hour)

    def test_overlapping_allocations_are_rejected(self):
        self.create_allocation(8, 10)

        with self.assertRaises(ValidationError):
            self.create_allocation(9, 11)

    def test_adjacent_allocations_are_allowed(self):
        self.create_allocation(8, 10)
        self.create_allocation(10, 12)

        self.assertEqual(self.day.allocations.count(), 2)

    def test_allocation_must_fit_inside_coverage(self):
        for start_hour, end_hour in [(7, 9), (17, 19)]:
            with self.subTest(start=start_hour, end=end_hour):
                with self.assertRaises(ValidationError):
                    self.create_allocation(start_hour, end_hour)

    def test_cancelled_allocation_does_not_block_time(self):
        self.create_allocation(8, 10, is_cancelled=True)
        self.create_allocation(8, 10)

        active = self.day.allocations.filter(is_cancelled=False)
        self.assertEqual(active.count(), 1)

    def test_coverage_cannot_exclude_active_allocations(self):
        self.create_allocation(8, 10)
        self.day.coverage_start = time(9, 0)

        with self.assertRaises(ValidationError):
            self.day.save()

    def test_editing_allocation_does_not_conflict_with_itself(self):
        allocation = self.create_allocation(8, 10)
        allocation.title = "Updated lecture title"
        allocation.save()

        allocation.refresh_from_db()
        self.assertEqual(allocation.title, "Updated lecture title")

