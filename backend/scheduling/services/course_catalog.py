"""Reviewed title evidence for any OAU department; never guessed from OCR.

Suggestions neither create Course records nor establish the applicable curriculum.
See docs/course-title-sources.md for coverage and verification instructions.
"""
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from django.conf import settings
from django.http import Http404

DATA_DIRECTORY = Path(__file__).resolve().parent.parent / 'data'

COURSE_CATALOGUE = json.loads(
    (DATA_DIRECTORY / 'course_titles.json').read_text(encoding='utf-8')
)
HANDBOOK_COURSES = json.loads((DATA_DIRECTORY / 'handbook_courses.json').read_text(encoding='utf-8'))
HANDBOOK_SOURCES = {
    source['id']: source
    for source in json.loads((DATA_DIRECTORY / 'handbook_sources.json').read_text(encoding='utf-8'))
}


def catalogue_payload(source_url):
    """Send shared source metadata once, rather than once per course."""
    enabled = settings.DEBUG and bool(settings.COURSE_HANDBOOK_DIRECTORY)
    sources = {
        key: {
            'source_title': source['filename'],
            'source_url': source_url(key) if enabled else '',
            'notes': source.get('notes', ''),
            **{field: source[field] for field in ('department', 'faculty', 'edition', 'programme')},
        }
        for key, source in HANDBOOK_SOURCES.items()
    }
    return {'course_catalogue': COURSE_CATALOGUE + HANDBOOK_COURSES, 'course_sources': sources}


def catalogue_coverage():
    faculties = Counter()
    for course in HANDBOOK_COURSES:
        faculties[HANDBOOK_SOURCES[course['source_id']]['faculty']] += 1
    for course in COURSE_CATALOGUE:
        faculties[course['faculty']] += 1
    return {
        'codes': len({item['code'] for item in COURSE_CATALOGUE + HANDBOOK_COURSES}),
        'handbooks': len(HANDBOOK_SOURCES),
        'faculties': sorted(faculties),
    }


def handbook_file(source_id):
    """Read an allowlisted local reference; never accept a request-supplied path.

    Checksums pin page links to the edition used for the title catalogue. A replaced
    file must be reviewed before it can be served as evidence for existing entries.
    """
    source = HANDBOOK_SOURCES.get(source_id)
    directory = settings.COURSE_HANDBOOK_DIRECTORY
    if not source or not settings.DEBUG or not directory:
        raise Http404('This handbook reference is available only in configured local development.')
    try:
        root = Path(directory).resolve(strict=True)
        file = (root / source['filename']).resolve(strict=True)
        if not file.is_relative_to(root) or not file.is_file() or file.stat().st_size > 100 * 1024 * 1024:
            raise ValueError
        member = source.get('member')
        if member:
            with ZipFile(file) as archive:
                entry = archive.getinfo(member)
                if entry.file_size > 80 * 1024 * 1024:
                    raise ValueError
                data = archive.read(entry)
        else:
            data = file.read_bytes()
        if not data.startswith(b'%PDF-') or hashlib.sha256(data).hexdigest() != source['sha256']:
            raise ValueError
    except (OSError, KeyError, ValueError, BadZipFile, RuntimeError) as error:
        raise Http404('The matching handbook edition is missing or changed. Restore it or review the new edition.') from error
    return io.BytesIO(data), Path(member or source['filename']).name
