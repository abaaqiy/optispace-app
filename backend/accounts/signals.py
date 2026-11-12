"""Remove account sessions and history when their owning records are deleted."""

from django.contrib.admin.models import LogEntry
from django.contrib.auth import SESSION_KEY
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.models import Session
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from bookings.models import Reservation

from .models import User


@receiver(pre_delete, sender=User)
@receiver(pre_delete, sender=Reservation)
def delete_object_history(sender, instance, using, **kwargs):
    # Admin history uses generic object IDs, so it is not a normal FK cascade.
    content_type = ContentType.objects.db_manager(using).get_for_model(sender)
    LogEntry.objects.using(using).filter(
        content_type_id=content_type.pk, object_id=str(instance.pk)
    ).delete()


@receiver(pre_delete, sender=User)
def delete_account_sessions(sender, instance, using, **kwargs):
    # Django's database sessions store the user ID in signed session data.
    # Removing only matching sessions leaves other users signed in.
    sessions = Session.objects.using(using)
    matching = []
    for session in sessions.iterator(chunk_size=200):
        if session.get_decoded().get(SESSION_KEY) == str(instance.pk):
            matching.append(session.pk)
        if len(matching) == 200:
            sessions.filter(pk__in=matching).delete()
            matching.clear()
    if matching:
        sessions.filter(pk__in=matching).delete()
