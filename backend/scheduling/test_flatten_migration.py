from datetime import date, time

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class FlattenTimetableMigrationTests(TransactionTestCase):
    def test_multiple_classes_keep_courses_times_and_sessions(self):
        before = ("scheduling", "0003_simplify_timetables")
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate([before])
        apps = executor.loader.project_state([before, *[node for node in latest if node[0] != "scheduling"]]).apps
        Building = apps.get_model("rooms", "Building")
        Room = apps.get_model("rooms", "Room")
        Course = apps.get_model("scheduling", "Course")
        Day = apps.get_model("scheduling", "TimetableDay")
        Lecture = apps.get_model("scheduling", "Allocation")
        building = Building.objects.create(name="Migration building", campus_zone="Science")
        room = Room.objects.create(name="Migration room", code="migrate", building=building, room_type="Classroom", capacity=30, size_category="small")
        course = Course.objects.create(code="CSC101", title="Computing", department="Computing")
        day = Day.objects.create(room=room, date=date(2030, 1, 15), coverage_start=time(8), coverage_end=time(18))
        Lecture.objects.create(timetable=day, title="Original title", course=course, academic_session="2029/2030", start_time=time(9), end_time=time(11))
        Lecture.objects.create(timetable=day, title="Legacy without course", start_time=time(12), end_time=time(13))
        Lecture.objects.create(timetable=day, title="Cancelled", start_time=time(14), end_time=time(15), is_cancelled=True)
        Day.objects.create(room=room, date=date(2030, 1, 16), coverage_start=time(8), coverage_end=time(18))
        try:
            MigrationExecutor(connection).migrate(latest)
            from .models import TimetableDay
            self.assertEqual(TimetableDay.objects.count(), 2)
            first = TimetableDay.objects.get(pk=day.pk)
            self.assertEqual(first.room_id, room.pk)
            self.assertEqual(first.course_id, course.pk)
            self.assertEqual(first.academic_session, "2029/2030")
            self.assertEqual((first.start_time, first.end_time), (time(9), time(11)))
            second = TimetableDay.objects.exclude(pk=day.pk).get()
            self.assertEqual((second.start_time, second.end_time), (time(12), time(13)))
            self.assertIsNone(second.course_id)
            self.assertNotIn("scheduling_allocation", connection.introspection.table_names())
            self.assertEqual(self.client.get("/api/rooms/migrate/", {"date": "2030-01-15", "time": "08:45"}).json()["status"], "available")
            self.assertEqual(len(self.client.get("/api/schedules/", {"date": "2030-01-15"}).json()), 2)
            self.assertEqual(self.client.get("/api/rooms/migrate/", {"date": "2030-01-16", "time": "09:00"}).json()["status"], "unknown")
        finally:
            MigrationExecutor(connection).migrate(latest)
