from datetime import date, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase, SimpleTestCase

from rooms.models import Building, Room
from scheduling.models import Course, TimetableDay, TimetableImageImport
from scheduling.services.document_heading import parse_heading
from scheduling.services.document_plan import image_plan, apply_image
from scheduling.services.timetable_import import ImportProblem


class HeadingTests(SimpleTestCase):
    def test_chemistry_heading_and_pharmacy_heading(self):
        found = parse_heading('DEPARTMENT OF CHEMISTRY, FACULTY OF SCIENCE\nFIRST DRAFT 2021/2022 Rain Semester Lecture Timetable')
        self.assertEqual([found[key] for key in ('department', 'faculty', 'academic_session', 'semester', 'source_version')],
                         ['Chemistry', 'Faculty of Science', '2021/2022', 'Rain', 'First Draft'])
        found = parse_heading('FACULTY OF PHARMACY, OBAFEMI AWOLOWO UNIVERSITY\nLECTURES AND PRACTICAL TIMETABLE FOR RAIN SEMESTER 2024/2025 SESSION')
        self.assertEqual(found['faculty'], 'Faculty of Pharmacy')
        self.assertEqual(found['department'], '')
        self.assertEqual(found['academic_session'], '2024/2025')

    def test_conflicting_or_missing_metadata_is_not_invented(self):
        found = parse_heading('2021/2022 and 2022/2023 Rain / Harmattan')
        self.assertEqual(found['academic_session'], '')
        self.assertEqual(found['semester'], '')


class ImagePlanTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(username='imageplan', email='imageplan@oauife.edu.ng', password='Test-admin-728!')
        self.building = Building.objects.create(name='Chemistry test building', campus_zone='Faculty of Science')
        self.options = {'mode': 'weekly', 'academic_session': '2029/2030', 'first_date': '2030-01-07',
                        'last_date': '2030-01-14', 'exclude_dates': '', 'department': 'Chemistry',
                        'faculty': 'Faculty of Science', 'semester': 'Rain', 'source_version': 'First Draft'}
        self.pending = {
            'courses': [{'key': 'draft-course-12345678', 'code': 'CHM 102', 'title': 'Introductory Chemistry', 'department': 'Chemistry'}],
            'rooms': [{'key': 'draft-room-12345678', 'name': 'CH 220', 'building': str(self.building.pk),
                       'room_type': 'Classroom', 'room_number': '220', 'capacity': '70', 'size_category': 'large', 'facilities': []}],
        }
        self.rows = [{'course': 'draft-course-12345678', 'room': 'draft-room-12345678', 'day': 'Monday',
                      'start_time': '08:00', 'end_time': '09:00', 'reviewed': True}]

    def preview(self):
        return image_plan(self.rows, self.options, self.pending, self.admin)

    def confirm(self, fingerprint, log=lambda *args: None):
        return apply_image(self.rows, self.options, self.pending, fingerprint, self.admin, 'test.jpg', log)

    def test_preview_writes_nothing_and_confirm_saves_references_dates_and_metadata(self):
        plan, staged, _, fingerprint = self.preview()
        self.assertEqual(len(plan.rows), 2)
        self.assertFalse(Room.objects.exists())
        self.assertFalse(Course.objects.exists())
        self.assertFalse(TimetableDay.objects.exists())
        result = self.confirm(fingerprint)
        self.assertEqual(result['Add'], 2)
        self.assertEqual(Room.objects.count(), 1)
        self.assertEqual(Course.objects.get().code, 'CHM102')
        self.assertEqual(TimetableDay.objects.count(), 2)
        source = TimetableImageImport.objects.get()
        self.assertEqual(source.faculty, 'Faculty of Science')
        self.assertEqual(source.semester, 'Rain')
        self.assertEqual(source.classes.count(), 2)

    def test_new_building_is_shared_by_new_rooms_and_saved_only_at_confirmation(self):
        self.pending['rooms'][0].update(building='new', building_name='New teaching block', campus_zone='Central Campus')
        self.pending['rooms'].append({**self.pending['rooms'][0], 'key': 'draft-room-87654321', 'name': 'Teaching 221'})
        self.rows.append({**self.rows[0], 'room': 'draft-room-87654321'})
        _, staged, _, fingerprint = self.preview()
        self.assertEqual(len(staged['buildings']), 1)
        self.assertEqual(Building.objects.count(), 1)
        self.confirm(fingerprint)
        self.assertEqual(Building.objects.count(), 2)
        self.assertEqual(len(set(Room.objects.values_list('building_id', flat=True))), 1)
        self.assertEqual(Room.objects.first().building.campus_zone, 'Central Campus')

    def test_failure_rolls_back_new_building_room_course_and_timetables(self):
        self.pending['rooms'][0].update(building='new', building_name='New block', campus_zone='Central Campus')
        *_, fingerprint = self.preview()
        with patch.object(TimetableDay, 'save', side_effect=IntegrityError('test failure')):
            with self.assertRaises(ImportProblem):
                self.confirm(fingerprint)
        self.assertEqual(Building.objects.count(), 1)
        self.assertFalse(Room.objects.exists())
        self.assertFalse(Course.objects.exists())
        self.assertFalse(TimetableImageImport.objects.exists())

    def test_duplicate_or_missing_fields_or_permissions_block_creation(self):
        self.pending['rooms'][0]['capacity'] = ''
        with self.assertRaisesMessage(ImportProblem, 'capacity'):
            self.preview()
        self.pending['rooms'][0]['capacity'] = '70'
        Course.objects.create(code='chm102', title='Already exists', department='Chemistry')
        with self.assertRaisesMessage(ImportProblem, 'already exists'):
            self.preview()
        Course.objects.all().delete()
        with patch.object(self.admin, 'has_perm', return_value=False):
            with self.assertRaisesMessage(ImportProblem, 'permission'):
                self.preview()

    def test_new_conflict_after_preview_prevents_all_writes(self):
        room = Room.objects.create(name='Existing', code='existing', building=self.building, room_type='Classroom', capacity=10, size_category='small')
        self.rows[0]['room'] = room.code
        self.pending['rooms'] = []
        *_, fingerprint = self.preview()
        TimetableDay.objects.create(room=room, date=date(2030, 1, 7), start_time=time(8), end_time=time(9))
        with self.assertRaisesMessage(ImportProblem, 'overlaps'):
            self.confirm(fingerprint)
        self.assertFalse(Course.objects.exists())
        self.assertEqual(TimetableDay.objects.count(), 1)

    def test_overlapping_proposed_classes_rejected_before_saving(self):
        self.rows.append({**self.rows[0], 'start_time': '08:30', 'end_time': '09:30'})
        with self.assertRaisesMessage(ImportProblem, 'overlaps'):
            self.preview()
        self.assertFalse(Room.objects.exists())

    def test_record_added_after_preview_is_not_duplicated(self):
        *_, fingerprint = self.preview()
        Course.objects.create(code='CHM102', title='Existing course', department='Chemistry')
        with self.assertRaises(ImportProblem):
            self.confirm(fingerprint)
        self.assertEqual(Course.objects.count(), 1)
        self.assertFalse(Room.objects.exists())

    def test_unused_proposals_are_not_created(self):
        self.pending['courses'].append({'key': 'draft-course-87654321', 'code': 'Not used'})
        *_, fingerprint = self.preview()
        self.confirm(fingerprint)
        self.assertEqual(Course.objects.count(), 1)

    def test_full_teaching_period_can_exceed_csv_thousand_class_limit(self):
        self.options['last_date'] = '2031-01-07'
        self.rows = [{**self.rows[0], 'start_time': f'{hour:02d}:{minute:02d}',
                      'end_time': f'{hour:02d}:{minute + 10:02d}'}
                     for hour in range(8, 13) for minute in (0, 10, 20, 30)]
        plan, _, _, _ = self.preview()
        self.assertGreater(len(plan.rows), 1000)
        self.assertFalse(TimetableDay.objects.exists())
