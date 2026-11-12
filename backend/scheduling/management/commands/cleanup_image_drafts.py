from django.core.management.base import BaseCommand

from scheduling.services.document_drafts import cleanup_expired_drafts


class Command(BaseCommand):
    help = 'Delete only expired timetable image drafts and their stored images.'

    def handle(self, *args, **options):
        count = cleanup_expired_drafts()
        self.stdout.write(f'Removed {count} expired image draft(s).')
