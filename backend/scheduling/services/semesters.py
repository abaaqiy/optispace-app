"""Use centrally configured teaching dates for every reviewed image import."""
from scheduling.models import AcademicSemester

from .timetable_import import ImportProblem


def suggested_semester(options):
    """Suggest only an exact session/semester match, never infer teaching dates."""
    return AcademicSemester.objects.filter(
        academic_session=options.get('academic_session', ''), semester=options.get('semester', ''),
    ).values_list('pk', flat=True).first()


def semester_options(options, *, lock=False):
    value = str(options.get('teaching_semester', ''))
    if not value.isascii() or not value.isdigit() or len(value) > 18:
        raise ImportProblem('Select a saved teaching semester. Set its dates once in Semester settings, then return to this draft.')
    query = AcademicSemester.objects.select_for_update() if lock else AcademicSemester.objects
    try:
        semester = query.get(pk=int(value))
    except AcademicSemester.DoesNotExist as error:
        raise ImportProblem('This teaching semester no longer exists. Select a saved semester and validate again.') from error
    # Ignore dates/session submitted by an old page or stored in an older draft.
    return {
        'mode': 'weekly', 'teaching_semester': str(semester.pk),
        'department': options.get('department', ''), 'faculty': options.get('faculty', ''),
        'source_version': options.get('source_version', ''),
        'academic_session': semester.academic_session, 'semester': semester.semester,
        'first_date': semester.first_date.isoformat(), 'last_date': semester.last_date.isoformat(),
        'exclude_dates': semester.exclude_dates,
    }
