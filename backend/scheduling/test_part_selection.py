"""Selected Parts validate/import independently while preserving the remaining draft."""
import json
import shutil
import subprocess
from datetime import date, timedelta
from pathlib import Path
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import signing
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from rooms.models import Building, Room
from .models import AcademicSemester, Course, TimetableDay, TimetableImageDraft, TimetableImageImport
from .services.course_catalog import HANDBOOK_SOURCES
from .services.document_drafts import DOCUMENT_SALT, save_document
from .services.document_extract import parse_table
from .services.document_state import read_review_state
from .services.handbook_levels import extract_level_entries, heading_level
from .services.part_catalogue import LEVEL_PROFILES, department_profiles, import_selection, part_options, row_parts
from .services.timetable_import import ImportProblem
from .test_document_import import grid


class PartCatalogueTests(SimpleTestCase):
    def test_handbook_programmes_and_evidence_are_pinned_separately(self):
        self.assertEqual(len(LEVEL_PROFILES), 19)
        self.assertEqual(len({profile['id'] for profile in LEVEL_PROFILES}), 19)
        for profile in LEVEL_PROFILES:
            self.assertIn(profile['source_id'], HANDBOOK_SOURCES)
            self.assertTrue(profile['entries'])
            for entry in profile['entries']:
                self.assertRegex(entry['code'], r'^[A-Z]{2,5}\d{3}$')
                self.assertIn(entry['level'], range(1, 7))
                self.assertGreater(entry['page'], 0)
        chemistry = next(profile for profile in LEVEL_PROFILES if profile['id'] == 'chemistry-2023')
        industrial = next(profile for profile in LEVEL_PROFILES if profile['id'] == 'industrial-chemistry-2023')
        self.assertIn(('CSC201', 3), {(entry['code'], entry['level']) for entry in chemistry['entries']})
        self.assertIn(('MAC201', 4), {(entry['code'], entry['level']) for entry in chemistry['entries']})
        self.assertIn(('MAC201', 2), {(entry['code'], entry['level']) for entry in industrial['entries']})
        self.assertNotIn('ICH308', {entry['code'] for entry in industrial['entries']})
        law = next(profile for profile in LEVEL_PROFILES if profile['id'] == 'law-llb')
        self.assertEqual({entry['level'] for entry in law['entries'] if entry['code'] == 'PUL101'}, {1, 2})
        pharmacy = next(profile for profile in LEVEL_PROFILES if profile['id'] == 'pharmacy-bpharm-2019')
        self.assertIn('not PharmD', pharmacy['programme'])

    def test_curriculum_parser_uses_part_headings_not_prerequisites(self):
        self.assertEqual(heading_level('HARMATTAN SEMESTER – PART 1'), 1)
        self.assertEqual(heading_level('PART 1V'), 4)
        self.assertIsNone(heading_level('Students admitted to Part II'))
        pages = ['PART II\nMTH201 Mathematics    3    MTH102\nPHL201 is a prerequisite for PHL204\nPART III\nCSC201 Computing 2 0 3 3']
        result = extract_level_entries(pages, {'spans': [{'first': 1, 'last': 1}]})
        self.assertEqual({(entry['code'], entry['level']) for entry in result}, {('MTH201', 2), ('CSC201', 3)})

    def test_parallel_curriculum_tables_keep_both_semesters(self):
        pages = ['PART II\nBCH 201  Cell Biology  2 0 0 2        BCH 204 Cell Biology II 2 0 0 2\n'
                 'PART IV\nBCH 401 Enzymology  2 1 0 3        BCH 402 Immunology 2 0 0 2']
        result = extract_level_entries(pages, {'spans': [{'first': 1, 'last': 1, 'columns': 2, 'shared_heading': True}]})
        self.assertEqual({(entry['code'], entry['level']) for entry in result},
                         {('BCH201', 2), ('BCH204', 2), ('BCH401', 4), ('BCH402', 4)})

    def test_explicit_part_metadata_preserves_existing_courses_venues_and_times(self):
        table = grid(('DAY', 'PART', '8-9am', '9-10am'), ('Monday', 'II', 'PMB201 (B217)', 'PCL202 (B217)'))
        rows, _, _ = parse_table(table)
        self.assertEqual([(row['course_text'], row['room_text'], row['start_time']) for row in rows],
                         [('PMB201', 'B217', '08:00'), ('PCL202', 'B217', '09:00')])
        self.assertTrue(all(row['class_group_kind'] == 'part' for row in rows))
        table = grid(('DAY', 'CLASS', '8-9am', '9-10am'), ('Monday', 'III', 'CSC201 STEP A', 'MAC201 STEP B'))
        self.assertTrue(all(row['class_group_kind'] == 'group' for row in parse_table(table)[0]))

    def test_review_state_validates_only_new_part_fields_and_keeps_old_drafts_compatible(self):
        self.assertEqual(part_options({}), {'level_view': 'all'})
        for changes in ({'level_view': '7'}, {'level_view': []}):
            with self.assertRaises(ImportProblem):
                part_options(changes)
        self.assertEqual(part_options({'level_view': '3', 'level_profile': 'industrial-chemistry-2023',
                                       'level_profile_confirmed': ''}), {'level_view': '3'})
        for parts in ([True], [7], ['3'], [3, 3], 'III', None):
            with self.assertRaises(ImportProblem):
                read_review_state({'rows': json.dumps([{'level_override': parts, 'level_override_code': 'CSC201'}])})
        rows = [{'course_text': 'CSC201', 'level_override': [3], 'level_override_code': 'CSC201', 'reviewed': True}]
        state = read_review_state({'rows': json.dumps(rows), 'level_view': '3', 'department': 'Chemistry',
                                   'level_profile': 'chemistry-2023', 'level_profile_confirmed': 'yes'})
        self.assertEqual(state['review_rows'], rows)
        self.assertEqual(state['review_options']['level_view'], '3')
        self.assertEqual(state['review_options']['department'], 'Chemistry')
        self.assertNotIn('level_profile', state['review_options'])
        self.assertNotIn('level_profile_confirmed', state['review_options'])

    def test_selection_uses_department_evidence_without_course_digit_guessing(self):
        rows = [{'course': code} for code in ('CHM102', 'ICH202', 'CSC201', 'CHM304', 'MAC201', 'ICH308')]
        rows.append({'course': 'CHM102', 'skip': True})
        pending = {'courses': [], 'rooms': []}
        for view, expected in (('1', [0]), ('2', [1]), ('3', [2]), ('unassigned', [3, 4, 5]), ('all', list(range(6)))):
            with self.subTest(view=view):
                selected, _, scope = import_selection(rows, {'department': 'Chemistry', 'level_view': view}, pending)
                self.assertEqual(scope, {'view': view, 'indices': expected})
                self.assertEqual([i for i, row in enumerate(selected) if not row.get('skip')], expected)
                self.assertNotIn('skip', rows[0], 'Selection must not modify saved rows')
        with self.assertRaisesMessage(ImportProblem, 'No retained entries'):
            import_selection(rows, {'department': 'Chemistry', 'level_view': '5'}, pending)
        with self.assertRaisesMessage(ImportProblem, 'No retained entries'):
            import_selection(rows, {'department': 'Architecture', 'level_view': '1'}, pending)

    def test_manual_and_image_parts_take_priority_and_shared_classes_are_selected_once(self):
        profiles = department_profiles('Chemistry')
        pending = {'courses': [{'key': 'draft-course-12345678', 'code': 'ICH 308'}]}
        self.assertEqual(row_parts({'course': 'CHM304', 'class_group_kind': 'part', 'class_group': 'Part III / IV'}, profiles, pending), [3, 4])
        self.assertEqual(row_parts({'course': 'ICH308', 'class_group_kind': 'group', 'class_group': 'III'}, profiles, pending), [])
        shared = {'course': 'draft-course-12345678', 'class_group_kind': 'part', 'class_group': 'II',
                  'level_override': [1, 3], 'level_override_code': 'ICH308'}
        for view in ('1', '3', 'all'):
            self.assertEqual(import_selection([shared], {'level_view': view}, pending)[2]['indices'], [0])
        self.assertEqual(row_parts({**shared, 'level_override_code': 'CHM304'}, profiles, pending), [2])
        self.assertEqual(row_parts({**shared, 'level_override': []}, profiles, pending), [])

    def test_only_selected_references_are_staged_and_malformed_fields_still_reach_validation(self):
        rows = [{'course': 'draft-course-12345678', 'room': 'draft-room-12345678', 'class_group_kind': 'part', 'class_group': 'I'},
                {'course': 'draft-course-87654321', 'room': 'draft-room-87654321', 'class_group_kind': 'part', 'class_group': 'II'}]
        pending = {'courses': [{'key': 'draft-course-12345678', 'code': 'CHM102'}, {'key': 'draft-course-87654321'}],
                   'rooms': [{'key': 'draft-room-12345678', 'building': 'draft-building-12345678'}, {'key': 'draft-room-87654321'}],
                   'buildings': [{'key': 'draft-building-12345678'}, {'key': 'draft-building-87654321'}]}
        _, selected, _ = import_selection(rows, {'level_view': '1'}, pending)
        self.assertEqual(selected, {kind: [records[0]] for kind, records in pending.items()})
        pending['rooms'][0]['building'] = []
        self.assertEqual(import_selection(rows, {'level_view': '1'}, pending)[1]['buildings'], [])
        rows[0]['course'] = []
        selected_rows, selected_pending, _ = import_selection(rows, {'level_view': '1'}, pending)
        self.assertEqual(selected_rows[0]['course'], [])
        self.assertEqual(selected_pending['courses'], [])

    @skipUnless(shutil.which('node'), 'Node is required for frontend/backend Part parity checks')
    def test_server_selection_agrees_with_the_editor_for_every_departmental_curriculum(self):
        root = Path(__file__).parent
        cases = []
        departments = {source['department'] for source in HANDBOOK_SOURCES.values() if source.get('department')}
        for department in sorted(departments | {'Chemistry / Industrial Chemistry', 'Architecture'}):
            profiles = department_profiles(department)
            rows = [{'course': code} for code in sorted({entry['code'] for profile in profiles for entry in profile['entries']})]
            rows.extend([{'course': 'ZZZ999'}, {'course': 'ZZZ999', 'class_group_kind': 'part', 'class_group': 'Part III / IV'},
                         {'course': 'ZZZ999', 'level_override': [1, 6], 'level_override_code': 'ZZZ999'}])
            cases.append({'department': f'Department of {department.upper().replace(" AND ", " & ")} (OAU)', 'rows': rows})
        cases.extend({'department': 'Pharmacy', 'heading': heading, 'rows': [{'course': 'PCL202'}, {'course': 'PMB201'}]}
                     for heading in ('', 'B.Pharm timetable', 'Doctor of Pharmacy (PharmD)', 'B.Pharm revised to PharmD'))
        programme = """
const fs = require('fs'), vm = require('vm');
const values = JSON.parse(fs.readFileSync(0, 'utf8'));
const context = {window: {}};
vm.runInNewContext(fs.readFileSync(values.script, 'utf8'), context);
const tool = context.window.OptispacePartSelection;
process.stdout.write(JSON.stringify(values.cases.map(item => {
  const profiles = tool.detect(item.department, values.profiles, values.sources, item.heading || '').profiles;
  return {ids: profiles.map(p => p.id), parts: item.rows.map(row => tool.classify(row, profiles, {}).parts)};
})));
"""
        result = subprocess.run(['node', '-e', programme], input=json.dumps({
            'script': str(root / 'static/scheduling/part_selection.js'), 'profiles': LEVEL_PROFILES,
            'sources': HANDBOOK_SOURCES, 'cases': cases,
        }), text=True, capture_output=True, check=True, timeout=20)
        for case, actual in zip(cases, json.loads(result.stdout), strict=True):
            profiles = department_profiles(case['department'], case.get('heading', ''))
            self.assertEqual(actual['ids'], [profile['id'] for profile in profiles], case['department'])
            self.assertEqual(actual['parts'], [row_parts(row, profiles, {}) for row in case['rows']], case['department'])


class PartViewWorkflowTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('part-view', 'part-view@oauife.edu.ng', 'local-part-test')
        self.client.force_login(self.admin)
        building = Building.objects.create(name='Part selection block', campus_zone='Faculty of Science')
        self.room = Room.objects.create(name='Part selection classroom', code='part-room', building=building,
                                       capacity=60, room_type='Classroom', size_category='small')
        Course.objects.create(code='CSC201', title='Computing', department='Test programme')
        Course.objects.create(code='MAC201', title='Management', department='Test programme')
        semester = AcademicSemester.objects.create(academic_session='2029/2030', semester='Rain',
            first_date=date(2030, 1, 7), last_date=date(2030, 1, 14))
        base = {'room': self.room.code, 'day': 'Monday', 'start_time': '08:00', 'end_time': '09:00',
                'reviewed': True, 'skip': False}
        self.rows = [{**base, 'course': 'CSC201', 'course_text': 'CSC201', 'editor_id':'row-3'},
                     {**base, 'course': 'MAC201', 'course_text': 'MAC201', 'day':'Tuesday', 'editor_id':'row-4',
                      'class_group_kind': 'part', 'class_group': 'IV'}]
        self.options = {'teaching_semester': str(semester.pk), 'level_view':'3', 'department':'Chemistry'}
        document = {'filename':'part-selection.jpg', 'rows':self.rows, 'notices':[],
            'review_options':self.options, 'pages':[{'image':b'private-test-image', 'width':100, 'height':100}]}
        self.token = save_document(document, self.admin)
        self.url = reverse('admin:scheduling_timetableday_document')
        self.autosave = reverse('admin:scheduling_timetableday_autosave')

    def payload(self, **changes):
        return {'document_token':self.token, 'rows':json.dumps(self.rows), 'coverage_checked':'yes',
                **self.options, **changes}

    def test_level_view_and_full_extraction_survive_autosave_and_reboot_style_resume(self):
        response = self.client.post(self.autosave, self.payload(level_view='4', editor_state=json.dumps({'part:row-4:MAC201:4':True})))
        self.assertEqual(response.status_code, 200)
        reopened = self.client.get(self.url, {'review':response.json()['token']})
        self.assertEqual(reopened.context['rows'], self.rows)
        self.assertEqual(reopened.context['options']['level_view'], '4')
        self.assertEqual(reopened.context['options']['department'], 'Chemistry')
        self.assertEqual(reopened.context['editor_state'], {'part:row-4:MAC201:4':True})
        self.assertEqual(reopened.context['level_profiles'], LEVEL_PROFILES)
        for text in ('1. Confirm shared details', '2. Resolve missing courses and venues once',
                     '3. Compare the weekly preview with the image', 'Check shared headings once',
                     'Review clear entries by day', 'Review extracted entries',
                     'Level / Part:', 'All extracted entries'):
            self.assertContains(reopened, text)
        self.assertNotContains(reopened, 'id="level-profile"')
        self.assertNotContains(reopened, 'id="level-profile-confirmed"')
        self.assertFalse(TimetableDay.objects.exists())
        self.assertEqual(bytes(TimetableImageDraft.objects.get().image), b'private-test-image')

    def validate(self, rows=None, **changes):
        self.token = self.client.get(self.url, {'review': self.token}).context['document_token']
        response = self.client.post(self.url, {'action': 'review', **self.payload(
            rows=json.dumps(self.rows if rows is None else rows), **changes)})
        self.token = response.context['document_token']
        return response

    def confirm(self, preview, **changes):
        return self.client.post(self.url, {'action': 'confirm', 'document_token': preview.context['document_token'],
            'preview': preview.context['preview_token'], **changes})

    def test_selected_part_ignores_unreviewed_other_parts_and_preserves_them_for_a_second_import(self):
        hidden = [self.rows[0], {**self.rows[1], 'reviewed': False, 'end_time_input': '9:', 'source': 'original image cell'}]
        editor = {'part:row-4:MAC201:4': True, 'record:room:unresolved:capacity': '45'}
        preview = self.validate(hidden, editor_state=json.dumps(editor))
        self.assertEqual(preview.context['errors'], [])
        self.assertEqual(len(preview.context['plan'].rows), 2)
        self.assertEqual(preview.context['selected_entry_count'], 1)
        self.assertEqual(preview.context['other_entry_count'], 1)
        self.assertContains(preview, 'Part 3 (300 level) validated')
        self.assertContains(preview, '1 other weekly entries will remain')
        self.assertFalse(TimetableDay.objects.exists())
        response = self.confirm(preview)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(list(TimetableDay.objects.values_list('course__code', flat=True)), ['CSC201', 'CSC201'])
        reopened = self.client.get(response['Location'])
        self.token = reopened.context['document_token']
        self.assertEqual(reopened.context['rows'], hidden[1:])
        self.assertEqual(reopened.context['document']['rows'], self.rows)
        self.assertEqual(reopened.context['document']['pages'][0]['image'], b'private-test-image')
        self.assertEqual(reopened.context['editor_state'], editor)
        self.assertFalse(reopened.context['coverage_checked'])
        self.assertEqual(reopened.context['options']['level_view'], 'all')
        draft = TimetableImageDraft.objects.get()
        self.assertEqual(draft.expires_at - draft.saved_at, timedelta(hours=24))
        self.assertContains(reopened, 'Part 3 (1 weekly entries)')
        second = self.validate([{**hidden[1], 'reviewed': True, 'end_time': '09:00'}], level_view='4')
        self.assertEqual(second.context['errors'], [])
        self.assertEqual(len(second.context['plan'].rows), 1)
        self.assertEqual(self.confirm(second).status_code, 302)
        self.assertEqual(TimetableDay.objects.count(), 3)
        self.assertFalse(TimetableImageDraft.objects.exists())

    def test_100_level_import_requires_only_100_level_review_and_leaves_invalid_other_proposals(self):
        Course.objects.create(code='CHM102', title='Chemistry', department='Chemistry')
        Course.objects.create(code='ICH202', title='Industrial Chemistry', department='Chemistry')
        rows = [{**self.rows[0], 'course': 'CHM102', 'course_text': 'CHM102'},
                {**self.rows[1], 'course': 'ICH202', 'course_text': 'ICH202', 'class_group': 'II', 'reviewed': False},
                {**self.rows[1], 'course': 'draft-course-87654321', 'room': 'draft-room-87654321',
                 'class_group': 'II', 'reviewed': False, 'day': 'Wednesday'}]
        pending = {'courses': [{'key': 'draft-course-87654321', 'code': 'ICH308', 'title': ''}],
                   'rooms': [{'key': 'draft-room-87654321', 'name': '', 'building': 'draft-building-87654321', 'capacity': ''}],
                   'buildings': [{'key': 'draft-building-87654321', 'name': '', 'campus_zone': ''}]}
        preview = self.validate(rows, level_view='1', pending=json.dumps(pending))
        self.assertEqual(preview.context['errors'], [])
        self.assertEqual({row.course.code for row in preview.context['plan'].rows}, {'CHM102'})
        self.assertEqual(preview.context['document']['preview_records'], {'buildings': [], 'courses': [], 'rooms': []})
        imported = self.confirm(preview)
        self.assertEqual(imported.status_code, 302)
        reopened = self.client.get(imported['Location'])
        self.assertEqual(reopened.context['rows'], rows[1:])
        self.assertEqual(reopened.context['pending'], pending)
        self.assertEqual(set(TimetableDay.objects.values_list('course__code', flat=True)), {'CHM102'})

    def test_remaining_skipped_rows_and_legacy_shared_building_details_survive_partial_import(self):
        bkey, rkey = 'draft-building-12345678', 'draft-room-12345678'
        rows = [{**self.rows[0], 'room': rkey}, {**self.rows[1], 'room': 'draft-room-87654321', 'reviewed': False},
                {**self.rows[1], 'course': '', 'room': '', 'skip': True, 'source': 'Preserved skipped cell'}]
        pending = {'courses': [],
                   'rooms': [{'key': rkey, 'name': 'First Parts room', 'building': bkey, 'room_type': 'Classroom',
                              'capacity': '50', 'size_category': 'small'},
                             {'key': 'draft-room-87654321', 'name': 'Second Parts room', 'building': 'new',
                              'building_name': 'LEGACY SHARED BLOCK', 'campus_zone': 'Faculty of Science',
                              'room_type': 'Classroom', 'capacity': '40', 'size_category': 'small'},
                             {'name': self.room.name, 'key': []}],
                   'buildings': [{'key': bkey, 'name': 'Legacy shared block', 'campus_zone': 'Faculty of Science'}]}
        preview = self.validate(rows, pending=json.dumps(pending))
        self.assertEqual(preview.context['errors'], [])
        response = self.confirm(preview)
        self.assertEqual(response.status_code, 302)
        reopened = self.client.get(response['Location'])
        self.assertEqual(reopened.context['rows'], rows[1:])
        room = reopened.context['pending']['rooms'][0]
        self.assertEqual(room['building'], str(Building.objects.get(name='Legacy shared block').pk))
        self.assertNotIn('building_name', room)
        self.assertEqual(reopened.context['pending']['rooms'][1], {'name': self.room.name, 'key': []})

    def test_all_entries_still_requires_every_retained_level_to_be_reviewed(self):
        blocked = self.validate([self.rows[0], {**self.rows[1], 'reviewed': False}], level_view='all')
        self.assertIn('Review row 2', ' '.join(blocked.context['errors']))
        self.assertFalse(TimetableDay.objects.exists())
        preview = self.validate(level_view='all')
        self.assertEqual(preview.context['errors'], [])
        self.assertEqual(len(preview.context['plan'].rows), 3)
        self.assertEqual(preview.context['other_entry_count'], 0)
        self.assertEqual(self.confirm(preview).status_code, 302)
        self.assertEqual(TimetableDay.objects.count(), 3)
        self.assertFalse(TimetableImageDraft.objects.exists())

    def test_selected_unreviewed_or_invalid_entries_are_blocked_using_original_row_numbers(self):
        for changes, message in (({'reviewed': False}, 'Review row 2'),
                                 ({'room': []}, 'Review row 2: invalid field value'),
                                 ({'room': ''}, 'Review row 2: select an existing course and room'),
                                 ({'end_time': ''}, 'Review row 2: both start and end time')):
            with self.subTest(changes=changes):
                response = self.validate([self.rows[1], {**self.rows[0], **changes}])
                self.assertIn(message, ' '.join(response.context['errors']))
                self.assertFalse(TimetableDay.objects.exists())

    def test_signed_scope_cannot_be_changed_after_validation_or_replayed_after_partial_import(self):
        preview = self.validate()
        confirmed = signing.loads(preview.context['preview_token'], salt=DOCUMENT_SALT + '.apply')
        self.assertEqual(confirmed['scope'], {'view': '3', 'indices': [0]})
        draft = TimetableImageDraft.objects.get()
        draft.document['review_options']['level_view'] = 'all'
        draft.save(update_fields=['document'])
        blocked = self.confirm(preview)
        self.assertIn('preview is invalid or expired', ' '.join(blocked.context['errors']))
        self.assertFalse(TimetableDay.objects.exists())
        preview = self.validate()
        # Submitted indices, view and rows cannot widen a server-validated scope.
        self.assertEqual(self.confirm(preview, level_view='all', rows=json.dumps(self.rows),
                                     scope=json.dumps({'view': 'all', 'indices': [0, 1]})).status_code, 302)
        self.assertEqual(TimetableDay.objects.count(), 2)
        replayed = self.confirm(preview)
        self.assertIn('preview is invalid or expired', ' '.join(replayed.context['errors']))
        self.assertEqual(TimetableDay.objects.count(), 2)

    def test_autosave_changes_invalidate_the_scoped_preview(self):
        preview = self.validate()
        saved = self.client.post(self.autosave, self.payload(level_view='4'))
        self.assertEqual(saved.status_code, 200)
        self.assertNotIn('preview_scope', TimetableImageDraft.objects.get().document)
        blocked = self.confirm(preview)
        self.assertIn('preview is invalid or expired', ' '.join(blocked.context['errors']))
        self.assertFalse(TimetableDay.objects.exists())

    def test_failure_to_save_remaining_draft_rolls_back_imported_classes(self):
        preview = self.validate()
        with patch('scheduling.document_admin.continue_after_import', side_effect=IntegrityError('test-only failure')):
            with self.assertRaises(IntegrityError):
                self.confirm(preview)
        self.assertFalse(TimetableDay.objects.exists())
        self.assertFalse(TimetableImageImport.objects.exists())
        self.assertEqual(TimetableImageDraft.objects.count(), 1)

    def test_records_created_in_one_part_are_reused_by_remaining_rows_and_unfinished_building_fields(self):
        bkey, rkey, ckey = ('draft-building-12345678', 'draft-room-12345678', 'draft-course-12345678')
        other_rkey = 'draft-room-87654321'
        rows = [{**self.rows[0], 'course': ckey, 'room': rkey, 'class_group_kind': 'part', 'class_group': 'I'},
                {**self.rows[1], 'course': ckey, 'room': rkey, 'class_group': 'II', 'reviewed': False},
                {**self.rows[1], 'course': ckey, 'room': other_rkey, 'class_group': 'II', 'day': 'Wednesday', 'reviewed': False},
                {**self.rows[1], 'course': 'MAC201', 'room': '', 'class_group': 'II', 'day': 'Thursday', 'reviewed': False}]
        pending = {'courses': [{'key': ckey, 'code': 'CHM102', 'title': 'Chemistry', 'department': 'Chemistry'}],
                   'rooms': [{'key': rkey, 'name': 'Shared Part classroom', 'building': bkey,
                              'capacity': '50', 'room_type': 'Classroom', 'size_category': 'small'},
                             {'key': other_rkey, 'name': 'Other Part classroom', 'building': bkey,
                              'capacity': '40', 'room_type': 'Classroom', 'size_category': 'small'}],
                   'buildings': [{'key': bkey, 'name': 'Reusable Parts block', 'campus_zone': 'Faculty of Science'}]}
        editor = {f'record:room:{other_rkey}:capacity': '55', 'record:room:unfinished:building': bkey,
                  f'record:course:{ckey}:title': 'Already committed title',
                  f'record:building:{bkey}:name': 'Reusable Parts block'}
        preview = self.validate(rows, level_view='1', pending=json.dumps(pending), editor_state=json.dumps(editor))
        self.assertEqual(preview.context['errors'], [])
        self.assertFalse(Course.objects.filter(code='CHM102').exists())
        response = self.confirm(preview)
        self.assertEqual(response.status_code, 302)
        building = Building.objects.get(name='Reusable Parts block')
        self.assertEqual(building.rooms.count(), 1)
        reopened = self.client.get(response['Location'])
        self.token = reopened.context['document_token']
        self.assertEqual([row['course'] for row in reopened.context['rows']], ['CHM102', 'CHM102', 'MAC201'])
        self.assertEqual(reopened.context['rows'][0]['room'], rkey)
        self.assertFalse(reopened.context['rows'][0]['reviewed'])
        self.assertEqual(reopened.context['pending'], {'courses': [], 'buildings': [],
                         'rooms': [{**pending['rooms'][1], 'building': str(building.pk)}]})
        self.assertEqual(reopened.context['editor_state'], {f'record:room:{other_rkey}:capacity': '55',
                         'record:room:unfinished:building': str(building.pk)})
        second_rows = [{**row, 'room': row['room'] or rkey, 'reviewed': True} for row in reopened.context['rows']]
        second = self.validate(second_rows, level_view='2', pending=json.dumps(reopened.context['pending']))
        self.assertEqual(second.context['errors'], [])
        self.assertEqual(self.confirm(second).status_code, 302)
        self.assertEqual(Course.objects.filter(code='CHM102').count(), 1)
        self.assertEqual(Building.objects.filter(name='Reusable Parts block').count(), 1)
        self.assertEqual(building.rooms.count(), 2)
        self.assertEqual(TimetableDay.objects.count(), 5)
        self.assertFalse(TimetableImageDraft.objects.exists())

    def test_shared_class_assigned_to_multiple_parts_is_imported_once_and_not_offered_again(self):
        rows = [{**self.rows[0], 'level_override': [1, 2], 'level_override_code': 'CSC201'},
                {**self.rows[1], 'class_group': 'II', 'reviewed': False}]
        preview = self.validate(rows, level_view='1')
        self.assertEqual(preview.context['errors'], [])
        response = self.confirm(preview)
        self.assertEqual(self.client.get(response['Location']).context['rows'], rows[1:])
        self.assertEqual(TimetableDay.objects.count(), 2)

    def test_invalid_part_selection_does_not_save_and_other_accounts_cannot_access_it(self):
        self.assertEqual(self.client.post(self.autosave, self.payload(level_view='injected-view')).status_code, 400)
        self.assertNotIn('review_rows', TimetableImageDraft.objects.get().document)
        other = get_user_model().objects.create_superuser('other-part', 'other-part@oauife.edu.ng', 'local-part-test')
        self.client.force_login(other)
        self.assertEqual(self.client.post(self.autosave, self.payload()).status_code, 400)
        self.client.logout()
        self.assertEqual(self.client.get(self.url, {'review':self.token}).status_code, 302)

    def test_older_saved_profile_and_unchecked_confirmation_do_not_block_department_based_review(self):
        draft = TimetableImageDraft.objects.get()
        draft.document['review_options'].update(level_profile='industrial-chemistry-2023', level_profile_confirmed='')
        draft.save(update_fields=['document'])
        reopened = self.client.get(self.url, {'review':self.token})
        self.assertEqual(reopened.status_code, 200)
        self.assertEqual(reopened.context['rows'], self.rows)
        self.assertEqual(reopened.context['options']['department'], 'Chemistry')
        self.assertNotContains(reopened, 'id="level-profile"')
        self.assertNotContains(reopened, 'id="level-profile-confirmed"')
        response = self.client.post(self.autosave, self.payload())
        self.assertEqual(response.status_code, 200)
        draft.refresh_from_db()
        self.assertEqual(draft.document['review_rows'], self.rows)
        self.assertEqual(draft.document['review_options']['level_view'], '3')
        self.assertNotIn('level_profile', draft.document['review_options'])
        self.assertNotIn('level_profile_confirmed', draft.document['review_options'])
