from datetime import date, time

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class SimplifyTimetableMigrationTests(TransactionTestCase):
    def test_former_drafts_and_live_timetables_keep_lectures_and_become_visible(self):
        before = ('scheduling', '0002_course_allocation_academic_session_allocation_course')
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate([before])
        state = executor.loader.project_state([before, *[node for node in latest if node[0] != 'scheduling']]).apps
        Building = state.get_model('rooms', 'Building')
        Room = state.get_model('rooms', 'Room')
        Day = state.get_model('scheduling', 'TimetableDay')
        Lecture = state.get_model('scheduling', 'Allocation')
        building = Building.objects.create(name='Migration building', campus_zone='Faculty of Science')
        room = Room.objects.create(name='Migration room', code='migration-room', building=building, room_type='Classroom', capacity=30, size_category='small')
        records = []
        for day_number, published in ((15, False), (16, True)):
            day = Day.objects.create(room=room, date=date(2030, 1, day_number), coverage_start=time(8), coverage_end=time(18), is_published=published)
            lecture = Lecture.objects.create(timetable=day, title='Preserved lecture', start_time=time(10), end_time=time(12))
            records.append((day.pk, lecture.pk, day_number))
        try:
            target = ('scheduling', '0003_simplify_timetables')
            executor = MigrationExecutor(connection)
            executor.migrate([target])
            apps = executor.loader.project_state([target, *[node for node in latest if node[0] != 'scheduling']]).apps
            Allocation = apps.get_model('scheduling', 'Allocation')
            TimetableDay = apps.get_model('scheduling', 'TimetableDay')
            self.assertEqual(TimetableDay.objects.count(), 2)
            self.assertEqual(Allocation.objects.count(), 2)
            self.assertNotIn('is_published', [field.name for field in TimetableDay._meta.fields])
            for day_id, lecture_id, day_number in records:
                lecture = Allocation.objects.get(pk=lecture_id)
                self.assertEqual(lecture.timetable_id, day_id)
                self.assertEqual(lecture.timetable.room_id, room.pk)
        finally:
            MigrationExecutor(connection).migrate(latest)
