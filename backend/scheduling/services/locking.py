from contextlib import contextmanager

from django.db import transaction

from rooms.models import Room


@contextmanager
def lock_rooms(room_ids):
    """Serialize timetable and reservation changes for the same rooms."""
    with transaction.atomic():
        list(Room.objects.select_for_update().filter(
            pk__in=[pk for pk in room_ids if pk is not None],
        ).order_by("pk"))
        yield
