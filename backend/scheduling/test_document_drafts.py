from datetime import timedelta
from importlib import import_module
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.management import call_command
from django.core.cache.backends.filebased import FileBasedCache
from django.db import connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from .models import TimetableImageDraft
from .services.document_drafts import (
    DOCUMENT_SALT, DOCUMENT_TTL, load_document, save_document, saved_drafts,
)
from .services.timetable_import import ImportProblem


def document():
    return {'filename': 'restart-test.jpg', 'rows': [], 'review_rows': [{'course': 'CSC102', 'skip': True}],
            'pages': [{'width': 30, 'height': 20, 'image': b'private-image-data'}],
            'pending': {'courses': [{'code': 'CSC102', 'title_pending': True}], 'rooms': []},
            'review_options': {'semester': 'Rain', 'first_date': '2030-01-01'}}


class DurableDraftTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('draft-test', 'draft-test@oauife.edu.ng', 'test-only')

    def test_database_retains_image_edits_and_ownership_without_filesystem_cache(self):
        with patch('tempfile.gettempdir', side_effect=AssertionError('Draft storage must not use /tmp')):
            token = save_document(document(), self.user)
            self.assertEqual(load_document(token, self.user)[1], document())
            self.assertEqual(len(saved_drafts(self.user)), 1)
        stored = TimetableImageDraft.objects.get()
        self.assertEqual(bytes(stored.image), b'private-image-data')
        self.assertNotIn('image', stored.document['pages'][0])

    def test_other_owner_cannot_access_or_save_and_owner_deletion_removes_draft(self):
        token = save_document(document(), self.user)
        other = get_user_model().objects.create_superuser('other-draft', 'other-draft@oauife.edu.ng', 'test-only')
        self.assertEqual(saved_drafts(other), [])
        for operation in (lambda: load_document(token, other), lambda: save_document(document(), other, token=token)):
            with self.assertRaises(ImportProblem):
                operation()
        self.user.delete()
        self.assertFalse(TimetableImageDraft.objects.exists())

    def test_listing_renews_link_but_does_not_extend_database_expiry(self):
        save_document(document(), self.user)
        stored = TimetableImageDraft.objects.get()
        with patch('django.utils.timezone.now', return_value=stored.saved_at + timedelta(hours=6)):
            listed = saved_drafts(self.user)[0]
        stored.refresh_from_db()
        self.assertEqual(listed['expires_at'], stored.expires_at)
        # A freshly signed URL must not bypass the persisted expiration.
        fresh = signing.dumps({'key': stored.key, 'user': self.user.pk}, salt=DOCUMENT_SALT)
        with patch('django.utils.timezone.now', return_value=stored.expires_at):
            with self.assertRaises(ImportProblem):
                load_document(fresh, self.user)
            with self.assertRaises(ImportProblem):
                save_document(document(), self.user, token=fresh)
            self.assertEqual(saved_drafts(self.user), [])
        self.assertFalse(TimetableImageDraft.objects.exists())

    def test_lifetime_upgrade_extends_active_drafts_without_reviving_expired_ones(self):
        save_document(document(), self.user)
        active = TimetableImageDraft.objects.get()
        now = timezone.now()
        saved = now - timedelta(hours=6)
        TimetableImageDraft.objects.filter(pk=active.pk).update(
            saved_at=saved, expires_at=saved + timedelta(hours=7),
        )
        expired = TimetableImageDraft.objects.create(
            key='expired-before-upgrade', owner=self.user, filename='expired.jpg',
            document=active.document, image=active.image,
            saved_at=now - timedelta(hours=8), expires_at=now - timedelta(hours=1),
        )
        migrate = import_module('scheduling.migrations.0009_extend_image_draft_lifetime').extend_active_drafts
        with connection.schema_editor(atomic=False) as schema_editor:
            migrate(apps, schema_editor)
            migrate(apps, schema_editor)
        active.refresh_from_db()
        expired.refresh_from_db()
        self.assertEqual(active.saved_at, saved)
        self.assertEqual(active.expires_at, saved + timedelta(hours=24))
        self.assertEqual(active.document, document() | {'pages': [{'width': 30, 'height': 20}]})
        self.assertEqual(expired.expires_at, now - timedelta(hours=1))

    def test_cleanup_removes_expired_only_and_never_evicts_active_drafts(self):
        save_document(document(), self.user)
        stored = TimetableImageDraft.objects.get()
        TimetableImageDraft.objects.bulk_create([
            TimetableImageDraft(key=f'test-{i}', owner=self.user, filename='kept.jpg', document=stored.document,
                                image=b'image', saved_at=stored.saved_at, expires_at=stored.expires_at)
            for i in range(85)
        ])
        self.assertEqual(len(saved_drafts(self.user)), 86)  # Beyond the former cache limit.
        TimetableImageDraft.objects.filter(pk='test-0').update(expires_at=timezone.now() - timedelta(seconds=1))
        call_command('cleanup_image_drafts', verbosity=0)
        self.assertEqual(TimetableImageDraft.objects.count(), 85)
        self.assertTrue(TimetableImageDraft.objects.filter(pk=stored.pk).exists())

    def test_secret_rotation_can_reopen_active_draft_from_its_owner_list(self):
        save_document(document(), self.user)
        with override_settings(SECRET_KEY='new-local-test-secret'):
            fresh = saved_drafts(self.user)[0]['token']
            self.assertEqual(load_document(fresh, self.user)[1], document())

    def test_surviving_legacy_draft_migrates_once_with_original_owner_and_expiry(self):
        with TemporaryDirectory() as directory, patch('tempfile.gettempdir', return_value=directory):
            cache = FileBasedCache(str(Path(directory) / f'optispace-document-review-{os.getuid()}'), {'TIMEOUT': DOCUMENT_TTL})
            key = 'legacy-image'; now = timezone.now()
            token = signing.dumps({'key': key, 'user': self.user.pk}, salt=DOCUMENT_SALT)
            entry = {'token': token, 'filename': 'restart-test.jpg', 'saved_at': now,
                     'expires_at': now + timedelta(hours=4)}
            cache.set(key, document()); cache.set(f'image-drafts-user-{self.user.pk}', {key: entry})
            call_command('migrate_legacy_image_drafts', verbosity=0)
            stored = TimetableImageDraft.objects.get()
            self.assertEqual(stored.expires_at, entry['expires_at'])
            self.assertEqual(load_document(token, self.user)[1], document())
            self.assertIsNone(cache.get(key))
            call_command('migrate_legacy_image_drafts', verbosity=0)
            self.assertEqual(TimetableImageDraft.objects.count(), 1)


class DraftProcessRestartTests(TransactionTestCase):
    def test_fresh_python_process_reads_saved_draft_from_postgresql(self):
        user = get_user_model().objects.create_superuser('restart-draft', 'restart-draft@oauife.edu.ng', 'test-only')
        token = save_document(document(), user)
        # Independent interpreter and DB connection: no parent process memory or cache.
        program = '''
import json, sys
import django
from django.conf import settings
values = json.load(sys.stdin)
settings.DATABASES = {'default': values['database']}
settings.SECRET_KEY = values['secret']
django.setup()
from django.contrib.auth import get_user_model
from scheduling.services.document_drafts import load_document, saved_drafts
user = get_user_model().objects.get(pk=values['owner'])
payload = load_document(values['token'], user)[1]
print(json.dumps({'filename': payload['filename'], 'image_ok': payload['pages'][0]['image'] == b'private-image-data',
                  'review_rows': payload['review_rows'], 'pending': payload['pending'],
                  'options': payload['review_options'], 'listed': len(saved_drafts(user))}))
'''
        result = subprocess.run([sys.executable, '-c', program],
            cwd=Path(settings.BASE_DIR), env={**os.environ, 'DJANGO_SETTINGS_MODULE': 'config.settings'},
            input=json.dumps({'database': connection.settings_dict, 'secret': settings.SECRET_KEY,
                              'token': token, 'owner': user.pk}), text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        found = json.loads(result.stdout)
        self.assertTrue(found['image_ok'])
        self.assertEqual(found['listed'], 1)
        self.assertEqual(found['review_rows'], document()['review_rows'])
        self.assertEqual(found['pending'], document()['pending'])
        self.assertEqual(found['options'], document()['review_options'])
