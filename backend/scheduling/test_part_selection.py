"""The Part selector adds a view without changing the full-image workflow."""
import json
from datetime import date

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from rooms.models import Building, Room
from .models import AcademicSemester, Course, TimetableDay, TimetableImageDraft
from .services.course_catalog import HANDBOOK_SOURCES
from .services.document_drafts import save_document
from .services.document_extract import parse_table
from .services.document_state import read_review_state
from .services.handbook_levels import extract_level_entries, heading_level
from .services.part_catalogue import LEVEL_PROFILES, part_options
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
        self.assertEqual(part_options({}), {'level_view': 'all', 'level_profile': '', 'level_profile_confirmed': ''})
        for changes in ({'level_view': '7'}, {'level_view': []}, {'level_profile': 'unknown'},
                        {'level_profile_confirmed': 'true'}):
            with self.assertRaises(ImportProblem):
                part_options(changes)
        for parts in ([True], [7], ['3'], [3, 3], 'III', None):
            with self.assertRaises(ImportProblem):
                read_review_state({'rows': json.dumps([{'level_override': parts, 'level_override_code': 'CSC201'}])})
        rows = [{'course_text': 'CSC201', 'level_override': [3], 'level_override_code': 'CSC201', 'reviewed': True}]
        state = read_review_state({'rows': json.dumps(rows), 'level_view': '3', 'level_profile': 'chemistry-2023',
                                   'level_profile_confirmed': 'yes'})
        self.assertEqual(state['review_rows'], rows)
        self.assertEqual(state['review_options']['level_view'], '3')


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
                     {**base, 'course': 'MAC201', 'course_text': 'MAC201', 'day':'Tuesday', 'editor_id':'row-4'}]
        self.options = {'teaching_semester': str(semester.pk), 'level_view':'3', 'level_profile':'chemistry-2023',
                        'level_profile_confirmed':'yes'}
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
        self.assertEqual(reopened.context['editor_state'], {'part:row-4:MAC201:4':True})
        self.assertEqual(reopened.context['level_profiles'], LEVEL_PROFILES)
        for text in ('1. Confirm shared details', '2. Resolve missing courses and venues once',
                     '3. Compare the weekly preview with the image', 'Check shared headings once',
                     'Review clear entries by day', 'Review extracted entries'):
            self.assertContains(reopened, text)
        self.assertFalse(TimetableDay.objects.exists())
        self.assertEqual(bytes(TimetableImageDraft.objects.get().image), b'private-test-image')

    def test_final_validation_still_requires_hidden_parts_review_and_imports_whole_image(self):
        hidden = [self.rows[0], {**self.rows[1], 'reviewed':False}]
        blocked = self.client.post(self.url, {'action':'review', **self.payload(rows=json.dumps(hidden))})
        self.assertIn('Review row 2', ' '.join(blocked.context['errors']))
        self.assertFalse(TimetableDay.objects.exists())
        self.token = blocked.context['document_token']
        preview = self.client.post(self.url, {'action':'review', **self.payload()})
        self.assertEqual(preview.context['errors'], [])
        self.assertEqual(len(preview.context['plan'].rows), 3)
        response = self.client.post(self.url, {'action':'confirm', 'document_token':preview.context['document_token'],
                                             'preview':preview.context['preview_token']})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(TimetableDay.objects.count(), 3)
        self.assertFalse(TimetableImageDraft.objects.exists())

    def test_invalid_part_selection_does_not_save_and_other_accounts_cannot_access_it(self):
        self.assertEqual(self.client.post(self.autosave, self.payload(level_profile='injected-profile')).status_code, 400)
        self.assertNotIn('review_rows', TimetableImageDraft.objects.get().document)
        other = get_user_model().objects.create_superuser('other-part', 'other-part@oauife.edu.ng', 'local-part-test')
        self.client.force_login(other)
        self.assertEqual(self.client.post(self.autosave, self.payload()).status_code, 400)
        self.client.logout()
        self.assertEqual(self.client.get(self.url, {'review':self.token}).status_code, 302)
