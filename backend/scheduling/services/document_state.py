"""Bounded review state shared by manual save and background autosave."""
import json

from .document_extract import MAX_DRAFT_ROWS
from .timetable_import import ImportProblem


def read_review_state(data):
    def reject_constant(value):
        raise ValueError('Invalid JSON constant')

    def decode(key, default, limit, message):
        raw = data.get(key, default)
        if len(raw) > limit:
            raise ImportProblem('The review is too large. Split the image into smaller sections.')
        try:
            return json.loads(raw, parse_constant=reject_constant)
        except (ValueError, TypeError, RecursionError) as error:
            raise ImportProblem(message) from error

    rows = decode('rows', '[]', 700_000, 'Review data could not be read. Reload the document.')
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ImportProblem('Review data is invalid. Reload the document.')
    if len(rows) > MAX_DRAFT_ROWS:
        raise ImportProblem(f'Review at most {MAX_DRAFT_ROWS} rows per image.')
    pending = decode('pending', '{"courses": [], "rooms": []}', 300_000, 'Proposed courses and rooms could not be read.')
    if not isinstance(pending, dict) or set(pending) - {'courses', 'rooms'} or any(
        not isinstance(pending.get(key, []), list) or len(pending.get(key, [])) > 300
        or any(not isinstance(item, dict) for item in pending.get(key, [])) for key in ('courses', 'rooms')
    ):
        raise ImportProblem('Invalid proposed course/room records.')
    editor = decode('editor_state', '{}', 300_000, 'Unfinished editor fields could not be read.')
    if not isinstance(editor, dict) or len(editor) > 6000 or any(
        len(key) > 250 or not isinstance(value, (str, bool)) or isinstance(value, str) and len(value) > 2000
        for key, value in editor.items()
    ):
        raise ImportProblem('Invalid unfinished editor fields.')
    options = {key: data.get(key, '')[:2000] for key in ('teaching_semester', 'department', 'faculty', 'source_version')}
    options['mode'] = 'weekly'
    return {'review_rows': rows, 'pending': pending, 'review_options': options,
            'coverage_checked': data.get('coverage_checked') == 'yes', 'editor_state': editor}
