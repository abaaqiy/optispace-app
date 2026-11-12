from datetime import date, timedelta
from importlib import import_module
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.urls import reverse

from rooms.forms import BuildingAdminForm, RoomAdminForm
from rooms.models import Building, Room
from .models import AcademicSemester, Course, TimetableDay, TimetableImageDraft, TimetableImageImport, TimetableImageSubmission
from .services.document_drafts import save_document
from .services.document_plan import apply_image, image_plan
from .services.document_review import prepare_rows, references
from .services.document_submissions import check_submission
from .services.timetable_import import ImportProblem


class ImageSubmissionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('submission-admin', 'submission@oauife.edu.ng', 'test-only')
        self.building = Building.objects.create(name='Shared Teaching Block', campus_zone='Faculty of Science')
        self.room = Room.objects.create(name='Shared Teaching Room', code='shared-room', building=self.building,
                                       room_type='Classroom', capacity=50, size_category='small')
        Course.objects.create(code='CHM102', title='Chemistry', department='Chemistry')
        Course.objects.create(code='CHM202', title='Chemistry II', department='Chemistry')
        self.semester = AcademicSemester.objects.create(academic_session='2029/2030', semester='Rain',
            first_date=date(2030, 1, 7), last_date=date(2030, 1, 14))
        self.options = {'department': 'Chemistry', 'teaching_semester': str(self.semester.pk)}
        self.rows = [{'course': 'CHM102', 'room': self.room.code, 'day': 'Monday', 'start_time': '08:00',
                      'end_time': '09:00', 'reviewed': True}]
        self.pending = {'courses': [], 'rooms': [], 'buildings': []}

    def import_batch(self, view='1', rows=None, options=None, pending=None):
        rows, options, pending = rows or self.rows, options or self.options, pending or self.pending
        scope = {'view': view, 'indices': list(range(len(rows)))}
        *_, fingerprint = image_plan(rows, options, pending, self.user, scope=scope)
        return apply_image(rows, options, pending, fingerprint, self.user, 'timetable.jpg', lambda *args: None, scope=scope)

    def test_part_submission_blocks_repeat_and_full_image_but_allows_another_part(self):
        self.import_batch()
        self.assertEqual(list(TimetableImageSubmission.objects.values_list('part', flat=True)), [1])
        for view in ('1', 'all'):
            with self.subTest(view=view), self.assertRaisesMessage(ImportProblem, 'already been submitted'):
                image_plan(self.rows, self.options, self.pending, self.user, scope={'view': view})
        changed_rows = [{**self.rows[0], 'course': 'CHM202', 'day': 'Tuesday'}]
        self.import_batch('2', rows=changed_rows)
        self.assertEqual(sorted(TimetableImageSubmission.objects.values_list('part', flat=True)), [1, 2])
        self.assertEqual(TimetableDay.objects.count(), 3)

    def test_full_submission_blocks_every_part_and_unassigned_even_with_changed_file_or_times(self):
        self.import_batch('all')
        changed = [{**self.rows[0], 'day': 'Wednesday', 'start_time': '12:00', 'end_time': '13:00'}]
        for view in ('all', '1', '2', '6', 'unassigned'):
            with self.subTest(view=view), self.assertRaisesMessage(ImportProblem, 'complete timetable'):
                image_plan(changed, self.options, self.pending, self.user, scope={'view': view})
        self.assertEqual(TimetableImageSubmission.objects.count(), 7)
        self.assertEqual(TimetableDay.objects.count(), 2)

    def test_department_and_session_normalisation_does_not_allow_repeat_submission(self):
        self.import_batch()
        for department in ('CHEMISTRY', ' Department of Chemistry (OAU) ', 'B.Sc Chemistry'):
            with self.subTest(department=department), self.assertRaisesMessage(ImportProblem, 'already been submitted'):
                image_plan(self.rows, {**self.options, 'department': department, 'source_version': 'Revised'},
                           self.pending, self.user, scope={'view': '1'})
        with self.assertRaisesMessage(ImportProblem, 'already been submitted'):
            check_submission({'department': 'Chemistry', 'academic_session': '2029 / 2030', 'semester': 'rain'}, {'view': '1'})

    def test_different_department_session_or_semester_can_reuse_saved_course_room_and_building(self):
        self.import_batch()
        options = {**self.options, 'department': 'Physics'}
        self.import_batch(options=options, rows=[{**self.rows[0], 'day': 'Tuesday'}])
        other_semester = AcademicSemester.objects.create(academic_session='2029/2030', semester='Harmattan',
            first_date=date(2030, 2, 4), last_date=date(2030, 2, 4))
        self.import_batch(options={**self.options, 'teaching_semester': str(other_semester.pk)})
        other_session = AcademicSemester.objects.create(academic_session='2030/2031', semester='Rain',
            first_date=date(2031, 1, 6), last_date=date(2031, 1, 6))
        self.import_batch(options={**self.options, 'teaching_semester': str(other_session.pk)})
        self.assertEqual(TimetableImageSubmission.objects.count(), 4)
        self.assertEqual(Building.objects.count(), 1)
        self.assertEqual(Room.objects.count(), 1)
        self.assertEqual(Course.objects.count(), 2)

    def test_second_confirmation_loses_to_first_submission_even_if_both_validated_earlier(self):
        second_rows = [{**self.rows[0], 'day': 'Thursday'}]
        scope = {'view': '1', 'indices': [0]}
        *_, fingerprint = image_plan(second_rows, self.options, self.pending, self.user, scope=scope)
        self.import_batch()
        with self.assertRaisesMessage(ImportProblem, 'already been submitted'):
            apply_image(second_rows, self.options, self.pending, fingerprint, self.user, 'second-image.jpg', lambda *args: None, scope=scope)
        self.assertEqual(TimetableDay.objects.count(), 2)
        self.assertEqual(TimetableImageSubmission.objects.count(), 1)

    def test_existing_classes_from_another_importer_cannot_be_submitted_again_under_new_part(self):
        self.import_batch()
        with self.assertRaisesMessage(ImportProblem, 'already saved in Timetables'):
            image_plan(self.rows, {**self.options, 'department': 'Another department'}, self.pending, self.user, scope={'view': '2'})
        self.assertEqual(TimetableDay.objects.count(), 2)
        self.assertEqual(TimetableImageSubmission.objects.count(), 1)

    def test_cancelled_or_deleted_classes_do_not_clear_submission_protection(self):
        self.import_batch()
        TimetableDay.objects.all().update(is_cancelled=True)
        with self.assertRaisesMessage(ImportProblem, 'already been submitted'):
            self.import_batch()
        TimetableDay.objects.all().delete()
        TimetableImageImport.objects.all().delete()
        with self.assertRaisesMessage(ImportProblem, 'already been submitted'):
            self.import_batch()
        self.assertIsNone(TimetableImageSubmission.objects.get().image_import_id)

    def test_missing_department_blocks_import_but_draft_save_remains_allowed(self):
        with self.assertRaisesMessage(ImportProblem, 'Enter the department'):
            image_plan(self.rows, {**self.options, 'department': ''}, self.pending, self.user)
        token = save_document({'filename': 'incomplete.jpg', 'rows': self.rows,
            'review_options': {**self.options, 'department': ''}, 'pages': [{'image': b'image', 'width': 100, 'height': 100}]}, self.user)
        self.assertTrue(token)
        self.assertEqual(TimetableImageDraft.objects.count(), 1)

    def test_database_constraints_block_duplicate_claim_and_import_failure_rolls_it_back(self):
        self.import_batch()
        original = TimetableImageSubmission.objects.get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            TimetableImageSubmission.objects.create(department_key=original.department_key,
                academic_session=original.academic_session, semester=original.semester, part=1)
        rows = [{**self.rows[0], 'day': 'Thursday'}]
        scope = {'view': '2'}
        *_, fingerprint = image_plan(rows, self.options, self.pending, self.user, scope=scope)
        with patch.object(TimetableDay, 'save', side_effect=IntegrityError('test-only failure')):
            with self.assertRaises(ImportProblem):
                apply_image(rows, self.options, self.pending, fingerprint, self.user, 'failed-image.jpg', lambda *args: None, scope=scope)
        self.assertEqual(TimetableImageSubmission.objects.count(), 1)
        self.assertEqual(TimetableImageImport.objects.count(), 1)
        self.assertEqual(TimetableDay.objects.count(), 2)

    def test_new_import_references_are_in_manual_admin_autocomplete_and_next_department_image(self):
        self.client.force_login(self.user)
        pending = {'buildings': [{'key': 'draft-building-12345678', 'name': 'Imported Academic Block', 'campus_zone': 'Faculty of Science'}],
                   'rooms': [{'key': 'draft-room-12345678', 'name': 'Imported Study Room', 'building': 'draft-building-12345678',
                              'room_type': 'Practical teaching room', 'capacity': '60', 'size_category': 'large'}],
                   'courses': [{'key': 'draft-course-12345678', 'code': 'CHM104', 'title': 'Practical Chemistry', 'department': 'Chemistry'}]}
        rows = [{**self.rows[0], 'course': 'draft-course-12345678', 'room': 'draft-room-12345678'}]
        self.import_batch(rows=rows, pending=pending)
        building, room, course = Building.objects.get(name='Imported Academic Block'), Room.objects.get(name='Imported Study Room'), Course.objects.get(code='CHM104')
        for url, text in (('rooms_building_changelist', building.name), ('rooms_room_changelist', room.name),
                          ('scheduling_course_changelist', course.code)):
            self.assertContains(self.client.get(reverse(f'admin:{url}')), text)
        self.assertIn(building.name, dict(BuildingAdminForm().fields['name'].widget.widgets[0].choices))
        form = RoomAdminForm()
        self.assertIn(room.name, dict(form.fields['name'].widget.widgets[0].choices))
        self.assertIn(room.room_type, dict(form.fields['room_type'].widget.widgets[0].choices))
        for field, app, model, query, expected in (('building', 'rooms', 'room', building.name, str(building.pk)),
                                                  ('room', 'scheduling', 'timetableday', room.name, str(room.pk)),
                                                  ('course', 'scheduling', 'timetableday', course.code, str(course.pk))):
            response = self.client.get(reverse('admin:autocomplete'),
                {'app_label': app, 'model_name': model, 'field_name': field, 'term': query})
            self.assertEqual(response.status_code, 200)
            self.assertIn(expected, [item['id'] for item in response.json()['results']])
        token = save_document({'filename': 'physics.jpg', 'rows': [], 'review_options': {'department': 'Physics'},
            'pages': [{'image': b'image', 'width': 100, 'height': 100}]}, self.user)
        reopened = self.client.get(reverse('admin:scheduling_timetableday_document'), {'review': token})
        self.assertIn(building.name, reopened.context['creation_choices']['building_names'])
        self.assertIn(room.name, [item['name'] for item in reopened.context['creation_choices']['room_names']])
        self.assertIn(course.code, [item['value'] for item in reopened.context['references']['courses']])
        extracted = [{'course_text': course.code, 'room_text': room.name}]
        self.assertEqual(prepare_rows(extracted, references())[0]['room'], room.code)
        self.assertEqual(prepare_rows(extracted, references())[0]['course'], course.code)
        # Different timetable department, same saved space and service course.
        self.import_batch(options={**self.options, 'department': 'Physics'},
                          rows=[{**self.rows[0], 'course': course.code, 'room': room.code, 'day': 'Wednesday'}])
        self.assertEqual(Room.objects.filter(name=room.name).count(), 1)
        self.assertEqual(Building.objects.filter(name=building.name).count(), 1)
        self.assertEqual(Course.objects.filter(code=course.code).count(), 1)

    def test_upgrade_preserves_existing_part_from_draft_history_and_assumes_full_for_older_imports(self):
        when = self.semester.first_date
        source = TimetableImageImport.objects.create(filename='legacy-part.jpg', department='Chemistry',
            academic_session='2029/2030', semester='Rain', first_date=when, last_date=when,
            teaching_semester=self.semester)
        save_document({'filename': source.filename, 'rows': [],
            'review_options': {'department': 'Chemistry', 'teaching_semester': str(self.semester.pk)},
            'imported_batches': [{'view': '1', 'entries': 11, 'imported_at': (source.created_at + timedelta(seconds=1)).isoformat()}],
            'pages': [{'image': b'image', 'width': 100, 'height': 100}]}, self.user)
        other = TimetableImageImport.objects.create(filename='old-full.jpg', department='Physics',
            academic_session='2029/2030', semester='Rain', first_date=when, last_date=when)
        from django.apps import apps
        migration = import_module('scheduling.migrations.0012_track_image_submissions')
        with connection.schema_editor(atomic=False) as editor:
            migration.preserve_submissions(apps, editor)
            migration.preserve_submissions(apps, editor)
        source.refresh_from_db()
        self.assertEqual(source.review_scope, '1')
        self.assertEqual(list(source.submissions.values_list('part', flat=True)), [1])
        self.assertEqual(list(other.submissions.order_by('part').values_list('part', flat=True)), list(range(7)))
