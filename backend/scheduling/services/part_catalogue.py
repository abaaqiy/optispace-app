"""Verified programme curriculum evidence for a view of the full image draft.

Part selection does not remove rows or change the full-image import planner.
"""
import json

from .course_catalog import DATA_DIRECTORY
from .timetable_import import ImportProblem


LEVEL_PROFILES = json.loads((DATA_DIRECTORY / 'course_levels.json').read_text(encoding='utf-8'))
PROFILE_IDS = {profile['id'] for profile in LEVEL_PROFILES}
PART_VIEWS = {'all', 'unassigned', '1', '2', '3', '4', '5', '6'}


def part_options(data):
    view = data.get('level_view', '')
    profile = data.get('level_profile', '')
    confirmed = data.get('level_profile_confirmed', '')
    if not isinstance(view, str) or view and view not in PART_VIEWS:
        raise ImportProblem('Select all entries, Part 1–6, or Unassigned for the review view.')
    view = view or 'all'
    if not isinstance(profile, str) or profile and profile not in PROFILE_IDS:
        raise ImportProblem('Select a programme from the handbook list.')
    if not isinstance(confirmed, str) or confirmed not in {'', 'yes'}:
        raise ImportProblem('Use the checkbox to confirm the applicable programme and handbook edition.')
    return {'level_view': view, 'level_profile': profile,
            'level_profile_confirmed': confirmed if profile else ''}


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
