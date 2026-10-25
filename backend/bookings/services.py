from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from scheduling.services.locking import lock_rooms

from .models import Reservation


def change_reservation(reference, actor, action, note=""):
    """Room locks are shared with lecture writes; approval never uses stale data."""
    if not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied("Sign in with an active account.")
    room_id = Reservation.objects.values_list("room_id", flat=True).get(reference=reference)
    with lock_rooms([room_id]):
        reservation = Reservation.objects.select_for_update().get(reference=reference)
        if action in ("approve", "reject"):
            if not actor.is_superuser:
                raise PermissionDenied("Only administrators can review reservations.")
            if reservation.status != Reservation.Status.PENDING:
                raise ValidationError("This request has already been reviewed or cancelled. Refresh the reservations list.")
            if action == "approve":
                reservation.status = Reservation.Status.APPROVED
            else:
                reservation.status = Reservation.Status.REJECTED
            reservation.reviewed_by = actor
            reservation.reviewed_at = timezone.now()
            reservation.review_note = note.strip()
        elif action == "cancel":
            if actor.pk != reservation.user_id and not actor.is_superuser:
                raise PermissionDenied("You can only cancel your own reservations.")
            if reservation.status not in (Reservation.Status.PENDING, Reservation.Status.APPROVED):
                raise ValidationError("Only pending or approved reservations can be cancelled.")
            if reservation.starts_at <= timezone.now():
                raise ValidationError("Reservations cannot be cancelled after their start time.")
            reservation.status = Reservation.Status.CANCELLED
            reservation.cancelled_by = actor
            reservation.cancelled_at = timezone.now()
        else:
            raise ValidationError("Unknown reservation action.")
        reservation.save()
        return reservation
