"""Durable image review state in the configured PostgreSQL database."""
from datetime import timedelta
import secrets

from django.core import signing
from django.db import transaction
from django.utils import timezone

from scheduling.models import TimetableImageDraft
from .timetable_import import ImportProblem

DOCUMENT_SALT = 'scheduling.image-review.v3'
DOCUMENT_TTL = 24 * 60 * 60
UNAVAILABLE = (
    'This review expired or is invalid. Reopen Your saved image drafts to find an active copy. '
    'If it is not listed, upload the image again. Drafts expire 24 hours after their last save; '
    'restarting the app or computer does not remove saved drafts.'
)


def draft_token(draft):
    return signing.dumps({'key': draft.key, 'user': draft.owner_id, 'version': draft.saved_at.isoformat()}, salt=DOCUMENT_SALT)


class DraftConflict(ImportProblem):
    pass


def check_version(token, draft):
    expected = signing.loads(token, salt=DOCUMENT_SALT, max_age=DOCUMENT_TTL).get('version')
    if expected != draft.saved_at.isoformat():
        raise DraftConflict('This draft changed in another tab. Keep this page open, copy any unsaved edits, then reopen the saved draft before continuing.')


def cleanup_expired_drafts():
    return TimetableImageDraft.objects.filter(expires_at__lte=timezone.now()).delete()[0]


def unpack_document(draft):
    document = draft.document.copy()
    document['pages'] = [{**document['pages'][0], 'image': bytes(draft.image)}]
    return document


def get_draft(token, user, *, lock=False, metadata_only=False):
    try:
        payload = signing.loads(token, salt=DOCUMENT_SALT, max_age=DOCUMENT_TTL)
        if payload['user'] != user.pk or not isinstance(payload['key'], str):
            raise signing.BadSignature
        query = TimetableImageDraft.objects.select_for_update() if lock else TimetableImageDraft.objects
        if metadata_only:
            query = query.defer('image')
        draft = query.get(key=payload['key'], owner=user)
        if draft.expires_at <= timezone.now():
            raise TimetableImageDraft.DoesNotExist
        return draft
    except (signing.BadSignature, KeyError, TypeError, TimetableImageDraft.DoesNotExist) as error:
        raise ImportProblem(UNAVAILABLE) from error


def load_document(token, user):
    draft = get_draft(token, user)
    return {'key': draft.key, 'user': draft.owner_id, 'token': draft_token(draft)}, unpack_document(draft)


def document_fields(document):
    pages = document['pages']
    if len(pages) != 1:
        raise ImportProblem('A draft must contain one lecture timetable image.')
    stored = {**document, 'pages': [{key: value for key, value in pages[0].items() if key != 'image'}]}
    return {'filename': document.get('filename', 'Timetable image')[:255], 'document': stored, 'image': pages[0]['image']}


def save_document(document, user, *, token=None):
    """Save atomically; saving cannot resurrect an expired/imported draft."""
    fields = document_fields(document)
    with transaction.atomic():
        draft = get_draft(token, user, lock=True) if token else TimetableImageDraft(key=secrets.token_urlsafe(32), owner=user)
        if token:
            check_version(token, draft)
        now = timezone.now()
        for key, value in fields.items():
            setattr(draft, key, value)
        draft.saved_at = now
        draft.expires_at = now + timedelta(seconds=DOCUMENT_TTL)
        draft.save()
    # Expiry, rather than a cache-size limit, is the only automatic removal rule.
    cleanup_expired_drafts()
    return draft_token(draft)


def autosave_document(token, user, state):
    """Update only review metadata, without loading or rewriting the source image."""
    with transaction.atomic():
        draft = get_draft(token, user, lock=True, metadata_only=True)
        unchanged = all(draft.document.get(key, {} if key == 'editor_state' else None) == value
                        for key, value in state.items())
        # A successful response can be lost in transit. Retrying identical state
        # returns the current token without extending expiry or invalidating preview.
        if not unchanged:
            check_version(token, draft)
            draft.document.update(state)
            draft.document['preview_version'] = secrets.token_urlsafe(16)
            draft.document.pop('preview_records', None)
            draft.saved_at = timezone.now()
            draft.expires_at = draft.saved_at + timedelta(seconds=DOCUMENT_TTL)
            draft.save(update_fields=['document', 'saved_at', 'expires_at'])
        return {'token': draft_token(draft), 'saved_at': draft.saved_at.isoformat(),
                'expires_at': draft.expires_at.isoformat()}


def saved_drafts(user):
    cleanup_expired_drafts()
    return [{'token': draft_token(draft), 'filename': draft.filename, 'saved_at': draft.saved_at,
             'expires_at': draft.expires_at}
            for draft in TimetableImageDraft.objects.filter(owner=user, expires_at__gt=timezone.now())
            .only('key', 'owner_id', 'filename', 'saved_at', 'expires_at')]
