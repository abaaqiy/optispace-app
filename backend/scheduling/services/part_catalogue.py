"""Use the same verified departmental Part evidence for review and import scope."""
import json
import re
import unicodedata

from .course_catalog import DATA_DIRECTORY, HANDBOOK_SOURCES
from .timetable_import import ImportProblem


LEVEL_PROFILES = json.loads((DATA_DIRECTORY / 'course_levels.json').read_text(encoding='utf-8'))
PART_VIEWS = {'all', 'unassigned', '1', '2', '3', '4', '5', '6'}
PART_NUMBERS = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, '1V': 4, 'V': 5, 'VI': 6,
                'ONE': 1, 'TWO': 2, 'THREE': 3, 'FOUR': 4, 'FIVE': 5, 'SIX': 6}


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


def department_key(value):
    text = unicodedata.normalize('NFKC', str(value or '')).lower()
    text = re.sub(r'\([^)]*\)', '', text).replace('&', ' and ')
    text = re.sub(r'[^a-z0-9]+', ' ', text).strip()
    text = re.sub(r'^(?:(?:the )?(?:department|dept|faculty|school)(?: of)?\s+)+', '', text)
    text = re.sub(r'^(?:b sc|bsc|b eng|beng|b a|ba|ll b|llb)\s+', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def department_profiles(department, heading='', *, profiles=LEVEL_PROFILES, sources=HANDBOOK_SOURCES):
    """Exact/combined department matching, with historical programme restrictions."""
    def names(profile):
        return {department_key(value) for value in (
            profile['programme'], sources.get(profile['source_id'], {}).get('department', ''),
            *profile.get('department_aliases', []),
        ) if department_key(value)}

    key = department_key(department)
    found = [profile for profile in profiles if key and key in names(profile)]
    if key and not found:
        components = [department_key(value) for value in re.split(r'\s*(?:/|&|,|\band\b)\s*', str(department), flags=re.I)
                      if department_key(value)]
        groups = [[profile for profile in profiles if component in names(profile)] for component in components]
        if len(components) > 1 and all(groups):
            found = list({profile['id']: profile for group in groups for profile in group}.values())
    context = re.sub(r'[^a-z0-9]', '', f'{department} {heading}'.lower())
    return [profile for profile in found
            if not any(term in context for term in profile.get('excluded_programmes', []))
            and (not profile.get('required_programmes')
                 or any(term in context for term in profile['required_programmes']))]


def row_course_code(row, pending):
    proposal = next((item for item in pending.get('courses', []) if item.get('key') == row.get('course')), None)
    value = proposal.get('code', '') if proposal else row.get('course') or row.get('course_text') or ''
    return re.sub(r'\s+', '', str(value)).upper()


def row_parts(row, profiles, pending):
    """Manual assignment, then explicit image heading, then unambiguous handbook evidence."""
    code = row_course_code(row, pending)
    if isinstance(row.get('level_override'), list) and row.get('level_override_code') == code:
        return sorted(row['level_override'])
    if row.get('class_group_kind') == 'part':
        text = re.sub(r'\b(?:PARTS?|LEVELS?)\b', '', str(row.get('class_group', '')).upper()).strip()
        tokens = re.split(r'\s*(?:/|&|,|\+|\bAND\b)\s*', text)
        parts = [PART_NUMBERS.get(token, int(token) if re.fullmatch('[1-6]', token) else 0) for token in tokens]
        if parts and 0 not in parts:
            return sorted(set(parts))
    parts = {entry['level'] for profile in profiles for entry in profile['entries'] if entry['code'] == code}
    return sorted(parts) if len(parts) == 1 else []


def part_label(view):
    if view == 'all':
        return 'All extracted entries'
    if view == 'unassigned':
        return 'Unassigned / uncertain'
    return f'Part {view} ({view}00 level)'


def import_selection(rows, options, pending, metadata=None):
    """Keep full row positions but exclude other Parts from this validation/import."""
    view = part_options(options)['level_view']
    profiles = department_profiles(options.get('department', ''), (metadata or {}).get('heading_text', ''))
    indices = []
    selected_rows = []
    for index, row in enumerate(rows):
        parts = row_parts(row, profiles, pending)
        matches = view == 'all' or (not parts if view == 'unassigned' else int(view) in parts)
        include = not row.get('skip') and matches
        if include:
            indices.append(index)
        selected_rows.append(row.copy() if include else {**row, 'skip': True})
    if not indices:
        raise ImportProblem(f'No retained entries remain in {part_label(view)}. Choose another Part or All extracted entries.')
    used = {kind: {rows[index].get(field) for index in indices if isinstance(rows[index].get(field), str)}
            for kind, field in (('courses', 'course'), ('rooms', 'room'))}
    selected_pending = {kind: [record for record in pending.get(kind, [])
                              if isinstance(record.get('key'), str) and record['key'] in used[kind]]
                        for kind in ('courses', 'rooms')}
    buildings = {record.get('building') for record in selected_pending['rooms']
                 if isinstance(record.get('building'), str)}
    selected_pending['buildings'] = [record for record in pending.get('buildings', [])
                                     if isinstance(record.get('key'), str) and record['key'] in buildings]
    # The signed scope is recomputed at confirmation, rather than trusting posted indices.
    scope = {'view': view, 'indices': indices}
    return selected_rows, selected_pending, scope
