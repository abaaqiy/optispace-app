from datetime import date, time

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from scheduling.models import TimetableDay
from .catalog import OTHER_CHOICE
from .forms import BuildingAdminForm
from .models import Building, Room


class BuildingUniquenessTests(TestCase):
    def setUp(self):
        self.building = Building.objects.create(name='Shared Teaching Block', campus_zone='Faculty of Science')

    def test_model_and_manual_form_reject_case_spacing_and_punctuation_duplicates(self):
        for name in ('shared teaching block', ' Shared Teaching Block ', 'Shared-Teaching-Block', 'SharedTeachingBlock'):
            with self.subTest(name=name):
                with self.assertRaisesMessage(ValidationError, 'already exists'):
                    Building.objects.create(name=name, campus_zone='Faculty of Technology')
                form = BuildingAdminForm(data={'name_0': OTHER_CHOICE, 'name_1': name, 'campus_zone': 'Faculty of Technology'})
                self.assertFalse(form.is_valid())
                self.assertIn('name', form.errors)
        self.assertEqual(Building.objects.count(), 1)

    def test_database_blocks_duplicate_bulk_writes_and_missing_identity(self):
        for name, key in (('shared-teaching-block', 'forged-key'), ('Another block', '')):
            with self.subTest(name=name), self.assertRaises(IntegrityError), transaction.atomic():
                Building.objects.bulk_create([Building(name=name, name_key=key, campus_zone='Faculty of Science')])
        other = Building.objects.create(name='Different block', campus_zone='Faculty of Science')
        with self.assertRaises(IntegrityError), transaction.atomic():
            Building.objects.filter(pk=other.pk).update(name='SharedTeachingBlock')

    def test_edit_preserves_room_and_timetable_links_and_saved_menu_choice(self):
        room = Room.objects.create(name='A shared room', code='shared-room', building=self.building,
                                   room_type='Classroom', capacity=30, size_category='small')
        entry = TimetableDay.objects.create(room=room, date=date(2030, 1, 7), start_time=time(8), end_time=time(9))
        old_id = self.building.pk
        self.building.name = 'Renamed Teaching Block'
        self.building.save(update_fields=['name'])
        self.building.refresh_from_db()
        self.assertEqual(self.building.name_key, 'renamedteachingblock')
        room.refresh_from_db()
        entry.refresh_from_db()
        self.assertEqual(room.building_id, old_id)
        self.assertEqual(entry.room_id, room.pk)
        self.assertEqual(BuildingAdminForm(instance=self.building).fields['name'].widget.decompress(self.building.name),
                         ['Renamed Teaching Block', ''])
