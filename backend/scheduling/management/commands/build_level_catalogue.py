"""Rebuild programme/Part evidence from the pinned local OAU handbooks."""
import hashlib
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from django.core.management.base import BaseCommand, CommandError
from scheduling.services.course_catalog import DATA_DIRECTORY, HANDBOOK_SOURCES
from scheduling.services.handbook_levels import extract_level_entries


class Command(BaseCommand):
    help = 'Index course-to-Part evidence from the reviewed curriculum page manifest.'

    def add_arguments(self, parser):
        parser.add_argument('--directory', required=True)
        parser.add_argument('--output', default=str(DATA_DIRECTORY / 'course_levels.json'))

    def handle(self, *args, **options):
        root = Path(options['directory']).resolve()
        profiles = json.loads((DATA_DIRECTORY / 'level_curricula.json').read_text())
        result = []
        with TemporaryDirectory(prefix='optispace-levels-') as temp:
            for profile in profiles:
                source = HANDBOOK_SOURCES[profile['source_id']]
                path = root / source['filename']
                if not path.is_file():
                    raise CommandError(f"Missing handbook: {source['filename']}")
                data = path.read_bytes()
                if source.get('member'):
                    with ZipFile(path) as archive:
                        data = archive.read(source['member'])
                if hashlib.sha256(data).hexdigest() != source['sha256']:
                    raise CommandError(f"Handbook edition changed: {source['filename']}. Review the manifest first.")
                pdf = Path(temp) / 'source.pdf'
                pdf.write_bytes(data)
                try:
                    text = subprocess.run(['pdftotext', '-layout', str(pdf), '-'], check=True, capture_output=True, text=True, timeout=60).stdout
                except (OSError, subprocess.SubprocessError) as error:
                    raise CommandError(f"Cannot read {source['filename']}: {error}") from error
                entries = extract_level_entries(text.split('\f'), profile)
                if not entries:
                    raise CommandError(f"No explicit curriculum entries for {profile['programme']}")
                result.append({**{key: value for key, value in profile.items() if key != 'spans'}, 'entries': entries})
                self.stdout.write(f"{profile['programme']}: {len(entries)} course/Part evidence entries")
        Path(options['output']).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        self.stdout.write(self.style.SUCCESS(f"Indexed {len(result)} programme profiles."))
