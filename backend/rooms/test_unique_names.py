from datetime import date, time

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from scheduling.models import TimetableDay
from .catalog import room_identity_key
from .models import Building, Room


class RoomNameUniquenessTests(TestCase):
    def setUp(self):
        self.building = Building.objects.create(name='Test academic building', campus_zone='Faculty of Science')
        self.room = self.create_room('CH 102', 'stable-room-code')

    def create_room(self, name, code):
        return Room.objects.create(name=name, code=code, building=self.building, room_type='Classroom',
                                   capacity=60, size_category='large')

    def test_normalised_name_and_documented_aliases_cannot_create_a_second_room(self):
        for name in ('ch102', ' CH 102 ', 'CH-102', 'Chemistry Lecture Theatre 102 (CH 102)'):
            with self.subTest(name=name), self.assertRaisesMessage(ValidationError, 'already exists'):
                self.create_room(name, 'another-code')
        self.assertEqual(Room.objects.count(), 1)
        self.assertEqual(self.room.name_key, room_identity_key('CH102'))

    def test_different_room_can_be_saved_and_rename_preserves_ids_and_timetables(self):
        other = self.create_room('CH 110', 'other-code')
        entry = TimetableDay.objects.create(room=self.room, date=date(2030, 1, 7), start_time=time(8), end_time=time(9))
        self.room.name = 'Chemistry Lecture Theatre 102 (CH 102)'
        self.room.save(update_fields=['name'])
        self.room.refresh_from_db()
        entry.refresh_from_db()
        self.assertEqual(self.room.code, 'stable-room-code')
        self.assertEqual(entry.room_id, self.room.pk)
        self.assertNotEqual(self.room.name_key, other.name_key)
        other.name = 'CH 102'
        with self.assertRaisesMessage(ValidationError, 'already exists'):
            other.save()

    def test_database_blocks_duplicate_name_on_bulk_insert_and_update(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Room.objects.bulk_create([Room(name='ch102', code='bulk-code', name_key='forged-other-key',
                building=self.building, room_type='Classroom', capacity=30, size_category='small')])
        other = self.create_room('CH 110', 'other-code')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Room.objects.filter(pk=other.pk).update(name='CH-102')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Room.objects.filter(pk=other.pk).update(name_key=self.room.name_key)

    def test_missing_identity_is_rejected_even_by_bulk_insert(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Room.objects.bulk_create([Room(name='New teaching room', code='empty-key-code', building=self.building,
                room_type='Classroom', capacity=30, size_category='small')])
