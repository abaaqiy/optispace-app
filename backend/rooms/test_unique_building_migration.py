from datetime import date, time

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class BuildingNameMigrationTests(TransactionTestCase):
    def test_upgrade_preserves_buildings_and_room_links_and_refuses_to_remove_duplicates(self):
        before = ('rooms', '0004_unique_room_names')
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        targets = [before, *[node for node in latest if node[0] != 'rooms']]
        executor.migrate(targets)
        apps = executor.loader.project_state(targets).apps
        Building = apps.get_model('rooms', 'Building')
        Room = apps.get_model('rooms', 'Room')
        Timetable = apps.get_model('scheduling', 'TimetableDay')
        building = Building.objects.create(name='Academic Teaching Block', campus_zone='Faculty of Science')
        duplicate = Building.objects.create(name='Academic-Teaching-Block', campus_zone='Faculty of Science')
        room = Room.objects.create(name='Teaching Room 101', name_key='teachingroom101', code='room101',
                                   building=building, capacity=50, room_type='Classroom', size_category='small')
        entry = Timetable.objects.create(room=room, date=date(2030, 1, 7), start_time=time(8), end_time=time(9))
        try:
            with self.assertRaisesMessage(RuntimeError, 'Resolve duplicate building names'):
                MigrationExecutor(connection).migrate(latest)
            self.assertEqual(Building.objects.count(), 2)
            self.assertEqual(Room.objects.get(pk=room.pk).building_id, building.pk)
            Building.objects.filter(pk=duplicate.pk).update(name='Another Teaching Block')
            MigrationExecutor(connection).migrate(latest)
            from .models import Building as UpdatedBuilding, Room as UpdatedRoom
            from scheduling.models import TimetableDay
            self.assertEqual(UpdatedBuilding.objects.get(pk=building.pk).name_key, 'academicteachingblock')
            self.assertEqual(UpdatedRoom.objects.get(pk=room.pk).building_id, building.pk)
            self.assertEqual(TimetableDay.objects.get(pk=entry.pk).room_id, room.pk)
        finally:
            Building.objects.filter(pk=duplicate.pk).update(name='Another Teaching Block')
            MigrationExecutor(connection).migrate(latest)
