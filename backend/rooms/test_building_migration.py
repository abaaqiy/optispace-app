from datetime import date, time

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class RequiredBuildingMigrationTests(TransactionTestCase):
    before = ("rooms", "0002_building_room_room_number_alter_room_zone_and_more")
    after = ("rooms", "0003_require_building_remove_room_zone")

    def test_upgrade_preserves_relationships_and_stops_on_unassigned_rooms(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        executor.migrate([self.before])
        apps = executor.loader.project_state([self.before, *[node for node in latest if node[0] != "rooms"]]).apps
        Building = apps.get_model("rooms", "Building")
        Room = apps.get_model("rooms", "Room")
        building = Building.objects.create(name="Migration building", campus_zone="Building zone")
        room = Room.objects.create(code="migrate-me", name="Migration room", zone="Conflicting old zone", building=building, room_type="Classroom", capacity=25, size_category="small")
        missing = Room.objects.create(code="unassigned", name="Unassigned room", zone="Another zone", room_type="Classroom", capacity=25, size_category="small")
        Facility = apps.get_model("rooms", "Facility")
        facility = Facility.objects.create(code="wifi")
        room.facilities.add(facility)
        day = apps.get_model("scheduling", "TimetableDay").objects.create(room_id=room.pk, date=date(2030, 1, 1), start_time=time(8), end_time=time(18))
        try:
            with self.assertRaisesMessage(RuntimeError, "Rooms without buildings: unassigned"):
                MigrationExecutor(connection).migrate([self.after])
            self.assertEqual(Room.objects.get(pk=room.pk).zone, "Conflicting old zone")
            missing.building = building
            missing.save()
            executor = MigrationExecutor(connection)
            executor.migrate([self.after])
            migrated = executor.loader.project_state(latest).apps
            new_room = migrated.get_model("rooms", "Room").objects.get(pk=room.pk)
            self.assertEqual(new_room.building.campus_zone, "Building zone")
            self.assertEqual(new_room.code, "migrate-me")
            self.assertEqual(new_room.facilities.get().pk, facility.pk)
            self.assertEqual(migrated.get_model("scheduling", "TimetableDay").objects.get(pk=day.pk).room_id, room.pk)
            self.assertEqual(migrated.get_model("rooms", "Room").objects.count(), 2)
        finally:
            Room.objects.filter(pk=missing.pk).update(building_id=building.pk)
            MigrationExecutor(connection).migrate(latest)
