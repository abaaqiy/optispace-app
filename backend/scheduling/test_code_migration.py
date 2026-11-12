from datetime import date, time

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class UniqueCourseCodeMigrationTests(TransactionTestCase):
    def test_upgrade_normalises_codes_keeps_timetable_links_and_stops_on_conflicts(self):
        before = ('scheduling', '0010_shared_teaching_semesters')
        after = ('scheduling', '0011_unique_course_codes')
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        # Insert the historical room before the new identity column exists.
        room_before = ('rooms', '0003_require_building_remove_room_zone')
        targets = [before, room_before, *[node for node in latest if node[0] not in ('scheduling', 'rooms')]]
        executor.migrate(targets)
        apps = executor.loader.project_state(targets).apps
        Building = apps.get_model('rooms', 'Building')
        Room = apps.get_model('rooms', 'Room')
        Course = apps.get_model('scheduling', 'Course')
        Timetable = apps.get_model('scheduling', 'TimetableDay')
        building = Building.objects.create(name='Migration computing block', campus_zone='Computing')
        room = Room.objects.create(name='Migration room', code='code-migration', building=building,
                                   room_type='Classroom', capacity=60, size_category='large')
        course = Course.objects.create(code='csc 102', title='Original title', department='Computing')
        duplicate = Course.objects.create(code='CSC102', title='Conflicting title', department='Computing')
        entry = Timetable.objects.create(room=room, course=course, date=date(2030, 1, 7), start_time=time(8), end_time=time(9))
        try:
            with self.assertRaisesMessage(RuntimeError, 'Resolve duplicate course codes'):
                MigrationExecutor(connection).migrate([after])
            self.assertEqual(Course.objects.get(pk=course.pk).code, 'csc 102')
            self.assertEqual(Course.objects.count(), 2)
            duplicate.code = 'CSC201'
            duplicate.save()
            MigrationExecutor(connection).migrate(latest)
            from .models import Course as UpdatedCourse, TimetableDay
            updated = UpdatedCourse.objects.get(pk=course.pk)
            self.assertEqual(updated.code, 'CSC102')
            self.assertEqual(updated.title, 'Original title')
            self.assertEqual(TimetableDay.objects.get(pk=entry.pk).course_id, course.pk)
        finally:
            Course.objects.filter(pk=duplicate.pk).update(code='CSC201')
            MigrationExecutor(connection).migrate(latest)
