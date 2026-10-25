"""Legacy reservation records retained for history; booking functionality is retired."""
from uuid import uuid4

from django.conf import settings
from django.db import models



def reservation_reference():
    return f"OAU-{uuid4().hex}"


class Reservation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    reference = models.CharField(max_length=36, unique=True, default=reservation_reference, editable=False)
    room = models.ForeignKey("rooms.Room", on_delete=models.PROTECT, related_name="reservations")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reservations")
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    purpose = models.CharField(max_length=200)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="reviewed_reservations",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=500, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="cancelled_reservations",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["room", "date", "status"], name="reservation_room_date_status")]
        constraints = [
            models.CheckConstraint(condition=models.Q(start_time__lt=models.F("end_time")), name="reservation_start_before_end"),
            models.CheckConstraint(condition=models.Q(status__in=["pending", "approved", "rejected", "cancelled"]), name="reservation_valid_status"),
        ]

    def __str__(self):
        return f"{self.reference} — {self.room} — {self.date}"
