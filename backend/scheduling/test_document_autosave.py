import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from rooms.models import Building, Room
from .models import AcademicSemester, Course, TimetableDay, TimetableImageDraft
from .services.document_drafts import load_document, save_document


class DocumentAutosaveTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('autosave-admin', 'autosave@oauife.edu.ng', 'Test-only-478!')
        self.client.force_login(self.admin)
        self.url = reverse('admin:scheduling_timetableday_autosave')
        self.review_url = reverse('admin:scheduling_timetableday_document')
        self.document = {'filename': 'autosave.jpg', 'rows': [], 'notices': [],
                         'pages': [{'image': b'original-private-image', 'width': 100, 'height': 100}]}
        self.token = save_document(self.document, self.admin)
        self.state = {'rows': json.dumps([{'course': '', 'start_time': '', 'start_time_input': '2:', 'reviewed': False}]),
                      'pending': json.dumps({'courses': [], 'rooms': []}),
                      'editor_state': json.dumps({'record:course:CSC102:title': 'Partly typed title'}),
                      'department': 'Computing', 'faculty': 'Faculty of Computing', 'teaching_semester': ''}

    def save(self, token=None, **changes):
        return self.client.post(self.url, {**self.state, 'document_token': token or self.token, **changes})

    def test_silent_autosave_persists_incomplete_edits_without_loading_or_updating_image(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.save()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(get_messages(response.wsgi_request)), [])
        draft_queries = [entry['sql'] for entry in queries if 'scheduling_timetableimagedraft' in entry['sql']]
        self.assertTrue(draft_queries)
        self.assertFalse(any('"image"' in query for query in draft_queries))
        draft = TimetableImageDraft.objects.get()
        self.assertEqual(bytes(draft.image), b'original-private-image')
        self.assertEqual(draft.document['review_rows'], json.loads(self.state['rows']))
        self.assertEqual(draft.document['editor_state'], json.loads(self.state['editor_state']))
        self.assertEqual(draft.expires_at - draft.saved_at, timedelta(hours=24))
        self.assertFalse(TimetableDay.objects.exists())
        self.assertFalse(Course.objects.exists())
        self.assertFalse(Room.objects.exists())
        self.assertFalse(Building.objects.exists())
        reopened = self.client.get(self.review_url, {'review': response.json()['token']})
        self.assertEqual(reopened.context['rows'], json.loads(self.state['rows']))
        self.assertEqual(reopened.context['editor_state'], json.loads(self.state['editor_state']))
        self.assertEqual(reopened.context['options']['department'], 'Computing')

    def test_stale_tabs_cannot_overwrite_autosave_or_manual_save(self):
        first = self.save()
        changed = self.save(department='Old tab overwrite')
        self.assertEqual(changed.status_code, 409)
        self.assertIn('another tab', changed.json()['error'])
        manual = self.client.post(self.review_url, {**self.state, 'action': 'save', 'document_token': first.json()['token']})
        self.assertEqual(manual.context['errors'], [])
        self.assertEqual(self.save(first.json()['token'], department='Late autosave').status_code, 409)
        self.assertEqual(TimetableImageDraft.objects.get().document['review_options']['department'], 'Computing')

    def test_validate_accepts_identical_edits_when_autosave_token_response_was_lost(self):
        building = Building.objects.create(name='Autosave teaching block', campus_zone='Faculty of Science')
        room = Room.objects.create(name='Autosave classroom', code='autosave-room', building=building,
                                   capacity=60, room_type='Classroom', size_category='small')
        Course.objects.create(code='CSC201', title='Computing', department='Computing')
        semester = AcademicSemester.objects.create(academic_session='2029/2030', semester='Rain',
            first_date='2030-01-07', last_date='2030-01-07')
        state = {**self.state, 'teaching_semester': str(semester.pk), 'coverage_checked': 'yes',
                 'level_view': '3', 'rows': json.dumps([{'course': 'CSC201', 'room': room.code,
                     'day': 'Monday', 'start_time': '08:00', 'end_time': '09:00', 'reviewed': True}])}
        saved = self.save(**state)
        self.assertEqual(saved.status_code, 200)
        # The database saved these edits, but the page still has its older token.
        reviewed = self.client.post(self.review_url, {**state, 'action': 'review', 'document_token': self.token})
        self.assertEqual(reviewed.context['errors'], [])
        self.assertTrue(reviewed.context['preview_token'])
        self.assertEqual(len(reviewed.context['plan'].rows), 1)
        self.assertFalse(TimetableDay.objects.exists())

    def test_stale_draft_can_resume_identical_edits_after_programme_controls_are_removed(self):
        first = self.save()
        draft = TimetableImageDraft.objects.get()
        draft.document['review_options'].update(level_profile='chemistry-2023', level_profile_confirmed='yes')
        draft.save(update_fields=['document'])
        original_rows = draft.document['review_rows']
        original_pending = draft.document['pending']
        original_editor = draft.document['editor_state']
        # Reopening the old page removes only the controls retired by the update.
        # Its row and record corrections still match the newer saved draft.
        result = self.save()
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['saved_at'], first.json()['saved_at'])
        saved = self.client.post(self.review_url, {**self.state, 'action': 'save', 'document_token': self.token})
        self.assertEqual(saved.context['errors'], [])
        draft.refresh_from_db()
        self.assertEqual(draft.document['review_rows'], original_rows)
        self.assertEqual(draft.document['pending'], original_pending)
        self.assertEqual(draft.document['editor_state'], original_editor)
        self.assertNotIn('level_profile', draft.document['review_options'])
        self.assertNotIn('level_profile_confirmed', draft.document['review_options'])

    def test_retired_controls_do_not_allow_different_stale_edits_to_overwrite_saved_work(self):
        self.save()
        draft = TimetableImageDraft.objects.get()
        draft.document['review_options'].update(level_profile='chemistry-2023', level_profile_confirmed='yes')
        draft.save(update_fields=['document'])
        self.assertEqual(self.save(department='Different stale department').status_code, 409)
        self.assertEqual(TimetableImageDraft.objects.get().document['review_options']['department'], 'Computing')

    def test_stale_manual_validation_does_not_overwrite_different_saved_edits(self):
        self.assertEqual(self.save(department='Newer saved department').status_code, 200)
        unsaved_editor = {'record:course:CSC102:title': 'Unsaved title from the older page'}
        reviewed = self.client.post(self.review_url,
            {**self.state, 'action': 'review', 'document_token': self.token, 'coverage_checked': 'yes',
             'editor_state': json.dumps(unsaved_editor)})
        self.assertIn('another tab', ' '.join(reviewed.context['errors']))
        self.assertFalse(reviewed.context['preview_token'])
        self.assertEqual(reviewed.context['editor_state'], unsaved_editor)
        self.assertEqual(reviewed.context['document_token'], self.token)
        self.assertTrue(reviewed.context['draft_conflict'])
        self.assertContains(reviewed, 'Save my edits as a new draft')
        self.assertEqual(TimetableImageDraft.objects.get().document['review_options']['department'], 'Newer saved department')
        self.assertEqual(TimetableImageDraft.objects.get().document['editor_state'], json.loads(self.state['editor_state']))
        self.assertFalse(TimetableDay.objects.exists())

    def test_conflicting_page_can_save_all_edits_in_a_new_draft_without_overwriting_the_original(self):
        self.save(department='Newer saved department')
        original = TimetableImageDraft.objects.get()
        original_document, original_saved_at = original.document.copy(), original.saved_at
        edited_rows = [{'course': 'CSC201', 'course_text': 'CSC201', 'room': '', 'reviewed': True,
                        'editor_id': 'retained-edited-row', 'level_override': [3], 'level_override_code': 'CSC201'}]
        editor = {'record:course:CSC201:title': 'Unsaved course title'}
        recovered = self.client.post(self.review_url, {**self.state, 'action': 'recover', 'document_token': self.token,
            'rows': json.dumps(edited_rows), 'editor_state': json.dumps(editor), 'level_view': '3'})
        self.assertEqual(recovered.status_code, 302)
        self.assertEqual(TimetableImageDraft.objects.count(), 2)
        original.refresh_from_db()
        self.assertEqual(original.document, original_document)
        self.assertEqual(original.saved_at, original_saved_at)
        reopened = self.client.get(recovered['Location'])
        self.assertEqual(reopened.context['rows'], edited_rows)
        self.assertEqual(reopened.context['editor_state'], editor)
        self.assertEqual(reopened.context['options']['level_view'], '3')
        self.assertEqual(reopened.context['pending'], json.loads(self.state['pending']))
        self.assertEqual(reopened.context['document']['pages'][0]['image'], b'original-private-image')
        self.assertIn('Recovered edits', reopened.context['document']['filename'])
        self.assertFalse(TimetableDay.objects.exists())
        self.assertFalse(Course.objects.exists())

    def test_conflict_response_links_to_latest_saved_state_and_does_not_recover_for_other_owner(self):
        self.save()
        conflict = self.save(department='Different stale edits')
        self.assertEqual(conflict.status_code, 409)
        newest = conflict.json()['latest_token']
        self.assertEqual(load_document(newest, self.admin)[1]['review_options']['department'], 'Computing')
        other = get_user_model().objects.create_superuser('recovery-other', 'recovery-other@oauife.edu.ng', 'Test-only-519!')
        self.client.force_login(other)
        denied = self.client.post(self.review_url, {**self.state, 'action': 'recover', 'document_token': self.token})
        self.assertTrue(denied.context['errors'])
        self.assertEqual(TimetableImageDraft.objects.count(), 1)

    def test_shared_building_choices_and_links_survive_autosave_manual_save_and_resume(self):
        building_key = 'draft-building-12345678'
        pending = {'buildings': [{'key': building_key, 'name': 'Computing teaching block',
                                 'campus_zone': 'Faculty of Computing Science and Engineering'}],
                   'courses': [], 'rooms': [{'key': 'draft-room-12345678', 'name': 'STEP A', 'building': building_key}]}
        editor_state = {'record:room:stepb:building': building_key, 'record:room:stepb:capacity': '45'}
        state = {**self.state, 'pending': json.dumps(pending), 'editor_state': json.dumps(editor_state)}
        response = self.save(**state)
        self.assertEqual(response.status_code, 200)
        reopened = self.client.get(self.review_url, {'review': response.json()['token']})
        self.assertEqual(reopened.context['pending'], pending)
        self.assertEqual(reopened.context['editor_state'], editor_state)
        self.assertContains(reopened, 'id="prepared-buildings"')
        saved = self.client.post(self.review_url, {**state, 'action': 'save', 'document_token': response.json()['token']})
        self.assertEqual(saved.context['errors'], [])
        self.assertEqual(saved.context['pending'], pending)
        resumed = self.client.get(self.review_url, {'review': saved.context['document_token']})
        self.assertEqual(resumed.context['pending'], pending)
        self.assertFalse(Building.objects.exists())
        self.assertFalse(Room.objects.exists())
        self.assertFalse(TimetableDay.objects.exists())

    def test_repeated_request_is_safe_and_does_not_extend_idle_expiry(self):
        first = self.save()
        draft = TimetableImageDraft.objects.get()
        with patch('django.utils.timezone.now', return_value=timezone.now() + timedelta(hours=2)):
            retry = self.save()
        self.assertEqual(retry.status_code, 200)
        draft.refresh_from_db()
        self.assertEqual(draft.saved_at.isoformat(), first.json()['saved_at'])
        self.assertEqual(draft.expires_at.isoformat(), first.json()['expires_at'])
        self.assertEqual(load_document(retry.json()['token'], self.admin)[1]['editor_state'], json.loads(self.state['editor_state']))

    def test_new_edits_invalidate_preview_but_identical_retry_keeps_it(self):
        saved = self.save().json()['token']
        draft = TimetableImageDraft.objects.get()
        draft.document['preview_version'] = 'already-validated'
        draft.save(update_fields=['document'])
        self.assertEqual(self.save(saved).status_code, 200)
        draft.refresh_from_db()
        self.assertEqual(draft.document['preview_version'], 'already-validated')
        self.assertEqual(self.save(saved, coverage_checked='yes').status_code, 200)
        draft.refresh_from_db()
        self.assertNotEqual(draft.document['preview_version'], 'already-validated')

    def test_invalid_or_oversized_state_is_rejected_without_changing_saved_draft(self):
        for changes in ({'rows': '{broken'}, {'rows': '{}'}, {'rows': '[{"confidence":NaN}]'}, {'rows': json.dumps([{}] * 301)},
                        {'pending': '[]'}, {'pending': '{"buildings": {}}'}, {'pending': '{"buildings": [null]}'},
                        {'pending': json.dumps({'buildings': [{}] * 301})},
                        {'editor_state': '[]'}, {'editor_state': 'x' * 300001}):
            with self.subTest(fields=list(changes)):
                self.assertEqual(self.save(**changes).status_code, 400)
                self.assertNotIn('review_rows', TimetableImageDraft.objects.get().document)

    def test_owner_permissions_csrf_expiry_and_import_deletion_are_enforced(self):
        other = get_user_model().objects.create_superuser('autosave-other', 'other@oauife.edu.ng', 'Test-only-479!')
        self.client.force_login(other)
        self.assertEqual(self.save().status_code, 400)
        self.client.force_login(self.admin)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.admin)
        self.assertEqual(csrf.post(self.url, self.state).status_code, 403)
        self.assertEqual(self.client.get(self.url).status_code, 405)
        staff = get_user_model().objects.create_user('autosave-staff', 'staff@oauife.edu.ng', role='lecturer', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.save().status_code, 403)
        self.client.logout()
        self.assertEqual(self.save().status_code, 302)
        self.client.force_login(self.admin)
        TimetableImageDraft.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.save().status_code, 400)
        TimetableImageDraft.objects.all().delete()
        self.assertEqual(self.save().status_code, 400)
        self.assertFalse(TimetableImageDraft.objects.exists())
