"""Reject overlapping departmental image submissions before preview and under the import lock."""
import re

from scheduling.models import TimetableImageSubmission

from .part_catalogue import department_key, part_label, part_options
from .timetable_import import ImportProblem


def submission_identity(options):
    key = department_key(options.get('department', ''))
    if not key:
        raise ImportProblem('Enter the department in Confirm shared details before validating the image.')
    return {'department_key': key,
            'academic_session': re.sub(r'\s+', '', options['academic_session']),
            'semester': options['semester'].strip().title()}


def scope_parts(view):
    return list(range(7)) if view == 'all' else [0 if view == 'unassigned' else int(view)]


def check_submission(options, scope):
    view = part_options({'level_view': scope['view']})['level_view']
    identity = submission_identity(options)
    previous = list(TimetableImageSubmission.objects.filter(
        **identity, part__in=scope_parts(view),
    ).select_related('image_import').order_by('part'))
    if previous:
        full = any(item.image_import and item.image_import.review_scope == 'all' for item in previous)
        labels = 'the complete timetable' if full else ', '.join(
            part_label('unassigned' if item.part == 0 else str(item.part)) for item in previous
        )
        continuation = (' Select an unsubmitted Part to continue; All extracted entries is blocked once a Part is submitted.'
                        if view == 'all' and not full else ' Use Timetables to edit or cancel the existing classes.')
        raise ImportProblem(
            f'{options["department"].strip()} — {identity["academic_session"]} {identity["semester"]}: '
            f'{labels} has already been submitted. This import would submit the same Part again.' + continuation
        )
    return identity


def record_submission(source, options, scope):
    # All overlapping scopes share a database uniqueness constraint. The caller
    # holds the image-import transaction/advisory lock until classes and draft save.
    identity = check_submission(options, scope)
    TimetableImageSubmission.objects.bulk_create([
        TimetableImageSubmission(**identity, part=part, image_import=source) for part in scope_parts(scope['view'])
    ])


def submitted_parts(options):
    """UI summary; backend validation remains authoritative."""
    key = department_key(options.get('department', ''))
    if not key:
        return []
    return list(TimetableImageSubmission.objects.filter(
        department_key=key,
        academic_session=re.sub(r'\s+', '', options.get('academic_session', '')),
        semester=options.get('semester', '').strip().title(),
    ).order_by('part').values_list('part', flat=True))
