"""Continue reviewing the remaining Parts after one validated batch is imported."""
from datetime import timedelta

from django.utils import timezone

from rooms.catalog import room_identity_key
from rooms.models import Building, Room
from scheduling.models import Course

from .document_drafts import DOCUMENT_TTL, draft_token
from .document_review import normalise


def continue_after_import(draft, document, scope, resolved):
    imported = set(scope['indices'])
    rows = document.get('review_rows', document['rows'])
    remaining = [row.copy() for index, row in enumerate(rows) if index not in imported]
    if not any(not row.get('skip') for row in remaining):
        draft.delete()
        return None

    pending = {kind: [record.copy() for record in document.get('pending', {}).get(kind, [])]
               for kind in ('courses', 'rooms', 'buildings')}
    # Share records created by this batch with every still-unimported Part.
    # Existing proposals for those identities are also reusable, not duplicates.
    redirects = {**resolved['courses'], **resolved['rooms'], **resolved['buildings']}
    course_codes = set(Course.objects.values_list('code', flat=True))
    rooms = {room.name_key: room.code for room in Room.objects.all()}
    buildings = {}
    for building in Building.objects.all():
        buildings.setdefault(normalise(building.name), []).append((str(building.pk), building.campus_zone))
    for record in pending['courses']:
        code = ''.join(str(record.get('code', '')).split()).upper()
        if isinstance(record.get('key'), str) and code in course_codes:
            redirects[record['key']] = code
    for record in pending['rooms']:
        code = rooms.get(room_identity_key(str(record.get('name', ''))))
        if isinstance(record.get('key'), str) and code:
            redirects[record['key']] = code
    for record in pending['buildings']:
        matches = buildings.get(normalise(record.get('name', '')), [])
        if isinstance(record.get('key'), str) and len(matches) == 1:
            redirects[record['key']] = matches[0][0]
    for row in remaining:
        for field in ('course', 'room'):
            if isinstance(row.get(field), str) and row[field] in redirects:
                row[field] = redirects[row[field]]
    for kind in ('courses', 'rooms', 'buildings'):
        pending[kind] = [record for record in pending[kind]
                         if not isinstance(record.get('key'), str) or record['key'] not in redirects]
    for record in pending['rooms']:
        if isinstance(record.get('building'), str) and record['building'] in redirects:
            record['building'] = redirects[record['building']]
        elif record.get('building') == 'new':
            # Reopen legacy per-room building details as a shared saved choice.
            matches = buildings.get(normalise(record.get('building_name', '')), [])
            if len(matches) == 1 and matches[0][1] == record.get('campus_zone'):
                record['building'] = matches[0][0]
                record.pop('building_name', None)
                record.pop('campus_zone', None)

    imported_editor_ids = {rows[index]['editor_id'] for index in imported
                           if isinstance(rows[index].get('editor_id'), str)}
    editor = {}
    for key, value in document.get('editor_state', {}).items():
        if any(editor_id and key.startswith(f'part:{editor_id}:') for editor_id in imported_editor_ids):
            continue
        if any(key.startswith(f'record:{kind}:{record_key}:')
               for kind in ('course', 'room', 'building') for record_key in redirects):
            continue
        editor[key] = redirects.get(value, value)
    history = document.get('imported_batches', [])
    document.update(review_rows=remaining, pending=pending, editor_state=editor,
                    coverage_checked=False,
                    imported_batches=[*history, {'view': scope['view'], 'entries': len(imported),
                                                'imported_at': timezone.now().isoformat()}])
    document['review_options'] = {**document.get('review_options', {}), 'level_view': 'all'}
    # Older reviews must not be able to confirm the same signed batch again.
    for key in ('preview_version', 'preview_records', 'preview_scope'):
        document.pop(key, None)
    stored = document.copy()
    stored['pages'] = [{key: value for key, value in page.items() if key != 'image'} for page in document['pages']]
    draft.document = stored
    draft.saved_at = timezone.now()
    # A partial import is a save, so the remaining work retains the usual lifetime.
    draft.expires_at = draft.saved_at + timedelta(seconds=DOCUMENT_TTL)
    draft.save(update_fields=['document', 'saved_at', 'expires_at'])
    return draft_token(draft)
