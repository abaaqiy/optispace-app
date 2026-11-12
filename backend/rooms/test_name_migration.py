from datetime import date, time

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class UniqueRoomNameMigrationTests(TransactionTestCase):
    def test_existing_names_get_keys_without_changing_rooms_links_or_facilities(self):
        before = ('rooms', '0003_require_building_remove_room_zone')
        after = ('rooms', '0004_unique_room_names')
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        targets = [before, *[node for node in latest if node[0] != 'rooms']]
        executor.migrate(targets)
        apps = executor.loader.project_state(targets).apps
        Building = apps.get_model('rooms', 'Building')
        Room = apps.get_model('rooms', 'Room')
        Facility = apps.get_model('rooms', 'Facility')
        Timetable = apps.get_model('scheduling', 'TimetableDay')
        building = Building.objects.create(name='Migration teaching block', campus_zone='Science')
        room = Room.objects.create(name='CH 102', code='stable-ch102', building=building, room_type='Classroom',
                                   capacity=60, size_category='large')
        duplicate = Room.objects.create(name='Chemistry Lecture Theatre 102 (CH 102)', code='duplicate-ch102',
                                        building=building, room_type='Classroom', capacity=45, size_category='small')
        facility = Facility.objects.create(code='wifi')
        room.facilities.add(facility)
        entry = Timetable.objects.create(room=room, date=date(2030, 1, 7), start_time=time(8), end_time=time(9))
        try:
            with self.assertRaisesMessage(RuntimeError, 'Resolve duplicate room names'):
                MigrationExecutor(connection).migrate([after])
            self.assertEqual(Room.objects.count(), 2, 'A conflicting upgrade must not remove a room')
            duplicate.name = 'CH 110'
            duplicate.save()
            MigrationExecutor(connection).migrate(latest)
            from .models import Room as UpdatedRoom
            from scheduling.models import TimetableDay
            updated = UpdatedRoom.objects.get(pk=room.pk)
            self.assertEqual(updated.name, 'CH 102')
            self.assertEqual(updated.code, 'stable-ch102')
            self.assertEqual(updated.name_key, 'chemistrylecturetheatre102ch102')
            self.assertEqual(TimetableDay.objects.get(pk=entry.pk).room_id, room.pk)
            self.assertEqual(list(updated.facilities.values_list('pk', flat=True)), [facility.pk])
        finally:
            Room.objects.filter(pk=duplicate.pk).update(name='CH 110')
            MigrationExecutor(connection).migrate(latest)
