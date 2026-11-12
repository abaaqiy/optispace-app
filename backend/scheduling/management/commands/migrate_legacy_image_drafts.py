"""One-time upgrade of surviving, trusted application cache files."""
import os
from pathlib import Path
import tempfile

from django.contrib.auth import get_user_model
from django.core import signing
from django.core.cache.backends.filebased import FileBasedCache
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from scheduling.models import TimetableImageDraft
from scheduling.services.document_drafts import DOCUMENT_SALT, DOCUMENT_TTL, document_fields


class Command(BaseCommand):
    help = 'Move surviving, unexpired legacy image drafts into the configured database without extending expiry.'

    def handle(self, *args, **options):
        directory = Path(tempfile.gettempdir()) / f'optispace-document-review-{os.getuid()}'
        if not directory.is_dir():
            self.stdout.write('No legacy draft directory found.')
            return
        cache = FileBasedCache(str(directory), {'TIMEOUT': DOCUMENT_TTL})
        moved = 0
        for user in get_user_model().objects.filter(is_staff=True).iterator():
            index_key = f'image-drafts-user-{user.pk}'
            index = cache.get(index_key, {})
            for key, entry in list(index.items()):
                try:
                    payload = signing.loads(entry['token'], salt=DOCUMENT_SALT, max_age=DOCUMENT_TTL)
                    if payload != {'key': key, 'user': user.pk} or len(key) > 64 or entry['expires_at'] <= timezone.now():
                        continue
                except (signing.BadSignature, KeyError, TypeError):
                    continue
                document = cache.get(key)
                if document is None:
                    continue
                with transaction.atomic():
                    draft, created = TimetableImageDraft.objects.get_or_create(key=key, defaults={
                        'owner': user, 'saved_at': entry['saved_at'], 'expires_at': entry['expires_at'],
                        **document_fields(document),
                    })
                    if draft.owner_id != user.pk:
                        continue
                # After a durable commit, retire the old copy so it cannot be resurrected.
                cache.delete(key)
                index.pop(key)
                moved += int(created)
            if index:
                cache.set(index_key, index)
            else:
                cache.delete(index_key)
        self.stdout.write(f'Migrated {moved} active legacy image draft(s). Original expiry times were preserved.')
