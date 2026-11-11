from datetime import date, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase, SimpleTestCase
from django.urls import reverse

from rooms.models import Building, Room
from scheduling.models import AcademicSemester, Course, TimetableDay, TimetableImageImport
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
        self.semester = AcademicSemester.objects.create(
            academic_session='2029/2030', semester='Rain', first_date=date(2030, 1, 7), last_date=date(2030, 1, 14),
        )
        self.options = {'mode': 'weekly', 'teaching_semester': str(self.semester.pk), 'department': 'Chemistry',
                        'faculty': 'Faculty of Science', 'source_version': 'First Draft'}
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

    def shared_building(self):
        key = 'draft-building-12345678'
        self.pending['buildings'] = [{'key': key, 'name': 'New teaching block', 'campus_zone': 'Faculty of Science'}]
        self.pending['rooms'][0]['building'] = key
        self.pending['rooms'].append({**self.pending['rooms'][0], 'key': 'draft-room-87654321', 'name': 'Teaching 221'})
        self.rows.append({**self.rows[0], 'room': 'draft-room-87654321'})
        return key

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
        self.assertEqual(source.teaching_semester, self.semester)
        self.assertEqual(source.first_date, self.semester.first_date)
        self.assertEqual(source.last_date, self.semester.last_date)
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

    def test_explicit_shared_building_creates_once_regardless_of_room_order(self):
        key = self.shared_building()
        self.pending['rooms'].reverse()
        self.pending['buildings'][0].update(name='Verified shared block', campus_zone='Faculty of Technology')
        _, staged, _, fingerprint = self.preview()
        self.assertEqual(len(staged['buildings']), 1)
        self.assertEqual(len(staged['rooms']), 2)
        self.assertIs(staged['rooms'][0][1].building, staged['rooms'][1][1].building)
        self.assertEqual(Building.objects.count(), 1)
        self.assertFalse(Room.objects.exists())
        self.assertTrue(all(room['building'] == key for room in self.pending['rooms']))
        counts = self.confirm(fingerprint)
        self.assertEqual(counts['buildings'], 1)
        building = Building.objects.get(name='Verified shared block')
        self.assertEqual(building.campus_zone, 'Faculty of Technology')
        self.assertEqual(building.rooms.count(), 2)
        self.assertEqual(TimetableDay.objects.count(), 4)

    def test_shared_building_survives_skipping_or_removing_original_room(self):
        self.shared_building()
        self.rows[0]['skip'] = True
        # The second room owns an independent reference, not a link through the first room.
        self.pending['rooms'].pop(0)
        self.pending['buildings'].append({'key': 'draft-building-87654321', 'name': '', 'campus_zone': ''})
        *_, fingerprint = self.preview()
        counts = self.confirm(fingerprint)
        self.assertEqual(counts['buildings'], 1)
        self.assertEqual(list(Room.objects.values_list('name', flat=True)), ['Teaching 221'])
        self.assertEqual(Building.objects.get(name='New teaching block').rooms.count(), 1)
        self.assertEqual(TimetableDay.objects.count(), 2)

    def test_unreferenced_shared_buildings_are_not_created(self):
        self.pending['buildings'] = [{'key': 'draft-building-12345678', 'name': '', 'campus_zone': ''}]
        *_, fingerprint = self.preview()
        self.assertEqual(self.confirm(fingerprint)['buildings'], 0)
        self.assertEqual(Building.objects.count(), 1)

    def test_missing_shared_building_is_reported_without_saving(self):
        self.pending['rooms'][0]['building'] = 'draft-building-12345678'
        with self.assertRaisesMessage(ImportProblem, 'prepared building is missing'):
            self.preview()
        self.assertFalse(Room.objects.exists())
        self.assertFalse(Course.objects.exists())

    def test_shared_building_permissions_and_field_validation_are_enforced(self):
        self.shared_building()
        with patch.object(self.admin, 'has_perm', side_effect=lambda permission: permission != 'rooms.add_building'):
            with self.assertRaisesMessage(ImportProblem, 'permission to create buildings'):
                self.preview()
        self.pending['buildings'][0]['campus_zone'] = ''
        with self.assertRaisesMessage(ImportProblem, 'campus_zone'):
            self.preview()
        self.pending['buildings'][0]['campus_zone'] = ['Invalid']
        with self.assertRaisesMessage(ImportProblem, 'invalid field values'):
            self.preview()
        self.assertEqual(Building.objects.count(), 1)
        self.assertFalse(Room.objects.exists())

    def test_duplicate_shared_names_deduplicate_but_conflicting_campus_areas_are_rejected(self):
        self.shared_building()
        self.pending['buildings'].append({**self.pending['buildings'][0], 'key': 'draft-building-87654321', 'name': 'NEW TEACHING BLOCK'})
        self.pending['rooms'][1]['building'] = 'draft-building-87654321'
        _, staged, _, _ = self.preview()
        self.assertEqual(len(staged['buildings']), 1)
        self.pending['buildings'][1]['campus_zone'] = 'Faculty of Technology'
        with self.assertRaisesMessage(ImportProblem, 'conflicting campus areas'):
            self.preview()
        self.assertFalse(Room.objects.exists())

    def test_invalid_shared_identifiers_are_rejected(self):
        self.shared_building()
        for key in ('saved-building-1', 'draft-building-?', self.pending['buildings'][0]['key']):
            with self.subTest(key=key):
                self.pending['buildings'].append({'key': key})
                with self.assertRaisesMessage(ImportProblem, 'invalid or repeated identifier'):
                    self.preview()
                self.pending['buildings'].pop()

    def test_shared_building_added_after_preview_requires_refresh_without_duplicate_writes(self):
        self.shared_building()
        *_, fingerprint = self.preview()
        Building.objects.create(name='New teaching block', campus_zone='Faculty of Science')
        with self.assertRaisesMessage(ImportProblem, 'already exists'):
            self.confirm(fingerprint)
        self.assertEqual(Building.objects.count(), 2)
        self.assertFalse(Room.objects.exists())
        self.assertFalse(Course.objects.exists())

    def test_shared_building_import_failure_rolls_back_all_rooms_and_classes(self):
        self.shared_building()
        *_, fingerprint = self.preview()
        with patch.object(TimetableDay, 'save', side_effect=IntegrityError('test failure')):
            with self.assertRaises(ImportProblem):
                self.confirm(fingerprint)
        self.assertEqual(Building.objects.count(), 1)
        self.assertFalse(Room.objects.exists())
        self.assertFalse(Course.objects.exists())
        self.assertFalse(TimetableImageImport.objects.exists())

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

    def test_duplicate_proposals_with_same_codes_or_room_aliases_cannot_be_imported(self):
        duplicate = {**self.pending['courses'][0], 'key': 'draft-course-87654321', 'code': 'chm102'}
        self.pending['courses'].append(duplicate)
        self.rows.append({**self.rows[0], 'course': duplicate['key'], 'day': 'Tuesday'})
        with self.assertRaisesMessage(ImportProblem, 'repeats another proposed'):
            self.preview()
        self.pending['courses'].pop()
        self.rows.pop()
        room = {**self.pending['rooms'][0], 'key': 'draft-room-87654321',
                'name': 'Chemistry Room 220 (CH 220)'}
        self.pending['rooms'].append(room)
        self.rows.append({**self.rows[0], 'room': room['key'], 'day': 'Tuesday'})
        with self.assertRaisesMessage(ImportProblem, 'repeats another proposed'):
            self.preview()
        self.assertFalse(Room.objects.exists())
        self.assertFalse(Course.objects.exists())

    def test_earlier_duplicate_details_are_preserved_but_never_create_a_second_record(self):
        duplicate = {**self.pending['rooms'][0], 'key': 'draft-room-87654321',
                     'duplicate_of': self.pending['rooms'][0]['key'], 'capacity': '45'}
        self.pending['rooms'].append(duplicate)
        *_, fingerprint = self.preview()
        self.confirm(fingerprint)
        self.assertEqual(Room.objects.count(), 1)
        self.assertEqual(Room.objects.get().capacity, 70)
        self.assertEqual(self.pending['rooms'][1]['capacity'], '45')
        self.rows[0]['room'] = duplicate['key']
        with self.assertRaisesMessage(ImportProblem, 'earlier duplicate proposal'):
            self.preview()

    def test_confirmed_code_with_unknown_title_imports_and_keeps_room_occupied(self):
        self.pending['courses'][0].update(code='PUL301', title='', title_pending=True, department='Public Law')
        *_, fingerprint = self.preview()
        self.confirm(fingerprint)
        course = Course.objects.get()
        self.assertEqual(course.title, '')
        self.assertTrue(course.title_pending)
        room = Room.objects.get()
        response = self.client.get(f'/api/rooms/{room.code}/', {'date': '2030-01-07', 'time': '08:30'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'occupied')
        self.assertIn('PUL301 — Title awaiting confirmation', response.json()['currentSchedule'])

    def test_unknown_title_requires_explicit_boolean_confirmation(self):
        for value in (False, 'false', 'true', 1, None):
            with self.subTest(value=value):
                self.pending['courses'][0].update(title='', title_pending=value)
                with self.assertRaises(ImportProblem):
                    self.preview()
        self.assertFalse(Course.objects.exists())

    def test_skipped_unknown_course_needs_no_title_and_creates_no_record(self):
        self.pending['courses'].append({'key': 'draft-course-87654321', 'code': 'CSC999', 'title': ''})
        self.rows.append({'course': 'draft-course-87654321', 'skip': True})
        *_, fingerprint = self.preview()
        self.confirm(fingerprint)
        self.assertEqual(list(Course.objects.values_list('code', flat=True)), ['CHM102'])
        self.assertEqual(TimetableDay.objects.count(), 2)

    def test_admin_can_finish_pending_title_without_changing_timetable_links(self):
        self.pending['courses'][0].update(code='CSC102', title='', title_pending=True, department='Computing')
        *_, fingerprint = self.preview()
        self.confirm(fingerprint)
        course = Course.objects.get()
        ids = list(TimetableDay.objects.values_list('pk', flat=True))
        self.client.force_login(self.admin)
        listing = reverse('admin:scheduling_course_changelist')
        self.assertContains(self.client.get(listing, {'title_pending__exact': '1'}), course.code)
        response = self.client.post(reverse('admin:scheduling_course_change', args=[course.pk]), {
            'code': course.code, 'title': 'Confirmed computing course', 'department': 'Computing',
            'title_pending': 'on', '_save': 'Save',
        })
        self.assertEqual(response.status_code, 302)
        course.refresh_from_db()
        self.assertFalse(course.title_pending)
        self.assertEqual(course.title, 'Confirmed computing course')
        self.assertEqual(list(TimetableDay.objects.filter(course=course).values_list('pk', flat=True)), ids)
        self.assertEqual(self.client.get(listing, {'title_pending__exact': '1'}).context['cl'].result_count, 0)

    def test_manual_course_admin_also_requires_pending_confirmation(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('admin:scheduling_course_add'), {
            'code': 'DSS101', 'title': '', 'department': 'Demography', '_save': 'Save',
        })
        self.assertContains(response, 'Enter a title or explicitly mark it as awaiting confirmation.')
        self.assertFalse(Course.objects.exists())

    def test_full_teaching_period_can_exceed_csv_thousand_class_limit(self):
        self.semester.last_date = date(2031, 1, 7)
        self.semester.save()
        self.rows = [{**self.rows[0], 'start_time': f'{hour:02d}:{minute:02d}',
                      'end_time': f'{hour:02d}:{minute + 10:02d}'}
                     for hour in range(8, 13) for minute in (0, 10, 20, 30)]
        plan, _, _, _ = self.preview()
        self.assertGreater(len(plan.rows), 1000)
        self.assertFalse(TimetableDay.objects.exists())

    def test_semester_changes_invalidate_preview_and_preserve_all_records(self):
        *_, fingerprint = self.preview()
        self.semester.last_date = date(2030, 1, 21)
        self.semester.save()
        with self.assertRaisesMessage(ImportProblem, 'changed after preview'):
            self.confirm(fingerprint)
        self.assertFalse(TimetableDay.objects.exists())
        self.assertFalse(Room.objects.exists())
        self.assertFalse(Course.objects.exists())
        *_, updated = self.preview()
        self.assertEqual(self.confirm(updated)['Add'], 3)
        # No dated class is created after the configured final teaching day.
        self.assertFalse(TimetableDay.objects.filter(date__gt=self.semester.last_date).exists())

    def test_two_departments_share_semester_dates_without_reentering_dates(self):
        *_, first = self.preview()
        self.confirm(first)
        self.options.update(department='Computing', faculty='Faculty of Computing Science and Engineering')
        self.pending['courses'][0].update(code='CSC102', title='Computing', department='Computing')
        self.pending['rooms'][0].update(name='Computing room', key='draft-room-87654321')
        self.rows[0]['room'] = 'draft-room-87654321'
        *_, second = self.preview()
        self.confirm(second)
        self.assertEqual(TimetableImageImport.objects.filter(teaching_semester=self.semester).count(), 2)
        for source in TimetableImageImport.objects.all():
            self.assertEqual(list(source.classes.order_by('date').values_list('date', flat=True)),
                             [date(2030, 1, 7), date(2030, 1, 14)])
