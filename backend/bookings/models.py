from datetime import datetime
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from scheduling.services.locking import lock_rooms


def reservation_reference():
    return f"OAU-{uuid4().hex}"


class Reservation(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    reference = models.CharField(
        max_length=36, unique=True, default=reservation_reference, editable=False
    )
    room = models.ForeignKey(
        "rooms.Room", on_delete=models.PROTECT, related_name="reservations"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reservations"
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    purpose = models.CharField(max_length=200)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reviewed_reservations",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=500, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cancelled_reservations",
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    is_archived = models.BooleanField(default=False, editable=False)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [
            models.Index(
                fields=["room", "date", "status"], name="reservation_room_date_status"
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(start_time__lt=models.F("end_time")),
                name="reservation_start_before_end",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=["pending", "approved", "rejected", "cancelled"]
                ),
                name="reservation_valid_status",
            ),
        ]

    def __str__(self):
        return f"{self.reference} — {self.room} — {self.date}"

    @property
    def starts_at(self):
        return timezone.make_aware(
            datetime.combine(self.date, self.start_time),
            timezone.get_default_timezone(),
        )

    @property
    def ends_at(self):
        return timezone.make_aware(
            datetime.combine(self.date, self.end_time), timezone.get_default_timezone()
        )

    @property
    def title(self):
        # Public room schedules must not disclose a requester's purpose or identity.
        return "Approved reservation"

    @property
    def is_cancelled(self):
        return self.is_archived or self.status != self.Status.APPROVED

    def validate_slot(self):
        from scheduling.models import TimetableDay

        if TimetableDay.objects.filter(
            room_id=self.room_id,
            date=self.date,
            is_cancelled=False,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time,
        ).exists():
            raise ValidationError(
                "This time overlaps a scheduled lecture. Choose another time."
            )
        overlaps = Reservation.objects.filter(
            room_id=self.room_id,
            date=self.date,
            is_archived=False,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time,
        ).exclude(pk=self.pk)
        if overlaps.filter(status=self.Status.APPROVED).exists():
            raise ValidationError(
                "This time overlaps an approved reservation. Choose another time."
            )
        if (
            self.status == self.Status.PENDING
            and overlaps.filter(
                user_id=self.user_id, status=self.Status.PENDING
            ).exists()
        ):
            raise ValidationError(
                "You already have a pending request for this room at that time."
            )

    def clean(self):
        super().clean()
        self.purpose = (self.purpose or "").strip()
        if not self.purpose:
            raise ValidationError({"purpose": "Enter the purpose of your reservation."})
        if not all(
            (self.room_id, self.user_id, self.date, self.start_time, self.end_time)
        ):
            return
        if self.start_time >= self.end_time:
            raise ValidationError(
                {"end_time": "End time must be after start time on the same day."}
            )

        original = Reservation.objects.filter(pk=self.pk).first() if self.pk else None
        if original:
            immutable = (
                "reference",
                "room_id",
                "user_id",
                "date",
                "start_time",
                "end_time",
                "purpose",
                "is_archived",
            )
            if any(
                getattr(original, field) != getattr(self, field) for field in immutable
            ):
                raise ValidationError(
                    "Reservation details cannot be edited. Cancel it and submit a new request."
                )
            if original.is_archived:
                raise ValidationError(
                    "This historical reservation is archived and cannot be changed."
                )
            allowed = {
                self.Status.PENDING: {
                    self.Status.PENDING,
                    self.Status.APPROVED,
                    self.Status.REJECTED,
                    self.Status.CANCELLED,
                },
                self.Status.APPROVED: {self.Status.APPROVED, self.Status.CANCELLED},
                self.Status.REJECTED: {self.Status.REJECTED},
                self.Status.CANCELLED: {self.Status.CANCELLED},
            }
            if self.status not in allowed[original.status]:
                raise ValidationError(
                    "This reservation cannot change to the requested status."
                )
        elif self.status != self.Status.PENDING or self.is_archived:
            raise ValidationError("New reservations must start as pending requests.")

        if self.status in (self.Status.APPROVED, self.Status.REJECTED):
            if (
                not self.reviewed_by_id
                or not self.reviewed_at
                or not self.reviewed_by.is_superuser
            ):
                raise ValidationError("An administrator must review this reservation.")
        if self.status == self.Status.CANCELLED and (
            not self.cancelled_by_id or not self.cancelled_at
        ):
            raise ValidationError(
                "The cancellation must record who cancelled it and when."
            )

        if not original or (
            self.status == self.Status.APPROVED and original.status != self.status
        ):
            if self.starts_at <= timezone.now():
                raise ValidationError(
                    "Reservations must start in the future (Africa/Lagos time)."
                )
            if not self.user.is_active or self.user.is_superuser:
                raise ValidationError(
                    "Only active student and lecturer accounts can request rooms."
                )
            if self.user.role == "student" and self.room.size_category != "small":
                raise ValidationError(
                    "Students can reserve smaller reading rooms only."
                )
            if self.user.role not in ("student", "lecturer"):
                raise ValidationError("This account cannot request rooms.")
            self.validate_slot()

    def save(self, *args, **kwargs):
        with lock_rooms([self.room_id]):
            self.full_clean()
            return super().save(*args, **kwargs)
