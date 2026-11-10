import hashlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .services.course_catalog import (
    COURSE_CATALOGUE, HANDBOOK_COURSES, HANDBOOK_SOURCES,
    catalogue_payload, handbook_file,
)


class CatalogueTests(SimpleTestCase):
    def test_curated_data_integrity(self):
        seen = set()
        for item in HANDBOOK_COURSES:
            source = HANDBOOK_SOURCES[item['source_id']]
            self.assertTrue(1 <= item['page'] <= source['pages'])
            self.assertRegex(item['code'], r'^[A-Z]{2,5}\d{3}$')
            self.assertRegex(source['sha256'], r'^[a-f0-9]{64}$')
            self.assertEqual(Path(source['filename']).name, source['filename'])
            key = item['source_id'], item['code'], item['title'].casefold()
            self.assertNotIn(key, seen)
            seen.add(key)

    @override_settings(DEBUG=False, COURSE_HANDBOOK_DIRECTORY='/configured')
    def test_production_does_not_link_or_serve_local_handbooks(self):
        payload = catalogue_payload(lambda source: '/reference/' + source)
        self.assertTrue(all(not source['source_url'] for source in payload['course_sources'].values()))
        with self.assertRaises(Http404):
            handbook_file(next(iter(HANDBOOK_SOURCES)))

    @override_settings(DEBUG=True, COURSE_HANDBOOK_DIRECTORY='/configured')
    def test_payload_keeps_reference_paths_private_and_data_compact(self):
        payload = catalogue_payload(lambda source: '/reference/' + source)
        self.assertEqual(len(payload['course_catalogue']), len(COURSE_CATALOGUE) + len(HANDBOOK_COURSES))
        self.assertNotIn('/configured', json.dumps(payload))
        self.assertNotIn('sha256', json.dumps(payload))
        self.assertTrue(all(source['source_url'].startswith('/reference/') for source in payload['course_sources'].values()))


class HandbookFileTests(SimpleTestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.data = b'%PDF-1.7\n local test reference'
        (self.root / 'reference.pdf').write_bytes(self.data)
        self.source = {'filename': 'reference.pdf', 'sha256': hashlib.sha256(self.data).hexdigest()}
        override = override_settings(DEBUG=True, COURSE_HANDBOOK_DIRECTORY=str(self.root))
        override.enable()
        self.addCleanup(override.disable)
        patcher = patch.dict(HANDBOOK_SOURCES, {'test-reference': self.source})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_exact_file_and_zip_member(self):
        stream, name = handbook_file('test-reference')
        self.assertEqual(stream.read(), self.data)
        self.assertEqual(name, 'reference.pdf')
        with ZipFile(self.root / 'archive.zip', 'w') as archive:
            archive.writestr('nested/reference.pdf', self.data)
        self.source.update(filename='archive.zip', member='nested/reference.pdf')
        stream, name = handbook_file('test-reference')
        self.assertEqual(stream.read(), self.data)
        self.assertEqual(name, 'reference.pdf')
        self.assertFalse((self.root / 'nested').exists())

    def test_missing_replaced_unknown_and_traversing_sources_are_rejected(self):
        for key in ('missing', '../reference.pdf', '/etc/passwd'):
            with self.assertRaises(Http404):
                handbook_file(key)
        (self.root / 'reference.pdf').write_bytes(b'%PDF-1.7 replaced edition')
        with self.assertRaises(Http404):
            handbook_file('test-reference')
        self.source['filename'] = 'missing.pdf'
        with self.assertRaises(Http404):
            handbook_file('test-reference')
        self.source['filename'] = '../outside.pdf'
        with self.assertRaises(Http404):
            handbook_file('test-reference')

    def test_symlink_outside_root_is_rejected(self):
        with TemporaryDirectory() as outside:
            target = Path(outside) / 'outside.pdf'
            target.write_bytes(self.data)
            (self.root / 'link.pdf').symlink_to(target)
            self.source['filename'] = 'link.pdf'
            with self.assertRaises(Http404):
                handbook_file('test-reference')


class HandbookPermissionTests(TestCase):
    def test_manual_course_add_edit_and_popup_offer_the_same_sourced_catalogue(self):
        from .models import Course
        user = get_user_model().objects.create_superuser('course-admin', 'course-admin@oauife.edu.ng', 'local-test')
        self.client.force_login(user)
        course = Course.objects.create(code='PUL101', title='', title_pending=True, department='Law')
        for url, query in (
            (reverse('admin:scheduling_course_add'), {}),
            (reverse('admin:scheduling_course_add'), {'_popup': '1'}),
            (reverse('admin:scheduling_course_change', args=[course.pk]), {}),
        ):
            response = self.client.get(url, query)
            self.assertContains(response, 'manual-course-catalogue')
            self.assertContains(response, 'scheduling/course_admin.js')
            self.assertEqual(response.context['course_suggestions']['course_catalogue'], COURSE_CATALOGUE + HANDBOOK_COURSES)
        course.refresh_from_db()
        self.assertEqual(course.title, '')

    def test_manual_handbook_access_requires_course_edit_permission(self):
        from django.contrib.auth.models import Permission
        url = reverse('admin:scheduling_course_handbook', args=['test-reference'])
        self.assertEqual(self.client.get(url).status_code, 302)
        user = get_user_model().objects.create_user('course-reader', 'course-reader@student.oauife.edu.ng', 'local-test', is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(url).status_code, 403)
        user.user_permissions.add(Permission.objects.get(codename='add_course'))
        with patch('scheduling.admin.handbook_file', return_value=(io.BytesIO(b'%PDF-test'), 'test.pdf')):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn('private', response['Cache-Control'])
            self.assertIn('no-store', response['Cache-Control'])
            self.assertEqual(b''.join(response.streaming_content), b'%PDF-test')
            self.assertEqual(self.client.post(url).status_code, 405)

    def test_reference_requires_staff_and_import_permission(self):
        url = reverse('admin:scheduling_timetableday_course_handbook', args=['test-reference'])
        self.assertEqual(self.client.get(url).status_code, 302)
        user = get_user_model().objects.create_user('reader', 'reader@student.oauife.edu.ng', 'example-password', is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(url).status_code, 403)
        user.is_superuser = True
        user.email = 'reader@oauife.edu.ng'
        user.save()
        with patch('scheduling.document_admin.handbook_file', return_value=(io.BytesIO(b'%PDF-test'), 'test.pdf')):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/pdf')
            self.assertIn('private', response['Cache-Control'])
            self.assertIn('no-store', response['Cache-Control'])
            self.assertEqual(b''.join(response.streaming_content), b'%PDF-test')
            self.assertEqual(self.client.post(url).status_code, 405)
