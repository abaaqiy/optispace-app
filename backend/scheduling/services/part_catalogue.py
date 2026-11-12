"""Verified programme curriculum evidence for a view of the full image draft.

Part selection does not remove rows or change the full-image import planner.
"""
import json

from .course_catalog import DATA_DIRECTORY
from .timetable_import import ImportProblem


LEVEL_PROFILES = json.loads((DATA_DIRECTORY / 'course_levels.json').read_text(encoding='utf-8'))
PART_VIEWS = {'all', 'unassigned', '1', '2', '3', '4', '5', '6'}


def part_options(data):
    view = data.get('level_view', '')
    if not isinstance(view, str) or view and view not in PART_VIEWS:
        raise ImportProblem('Select all entries, Part 1–6, or Unassigned for the review view.')
    view = view or 'all'
    # Older drafts can contain the retired profile and confirmation controls.
    # Departmental matching is now automatic; discard those fields on save.
    return {'level_view': view}


def validate_part_assignments(rows):
    for row in rows:
        if 'level_override' not in row:
            continue
        parts = row['level_override']
        code = row.get('level_override_code', '')
        if (not isinstance(parts, list) or len(parts) > 6
                or any(type(part) is not int or part not in range(1, 7) for part in parts)
                or len(set(parts)) != len(parts)
                or not isinstance(code, str) or len(code) > 30):
            raise ImportProblem('Choose valid Parts 1–6 for each manual assignment.')
