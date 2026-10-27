from django.core.exceptions import ValidationError
from django.db import models

from .services.locking import lock_rooms


class Course(models.Model):
    code = models.CharField(max_length=30, unique=True)
    title = models.CharField(max_length=200)
    department = models.CharField(max_length=150)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.title}"


class TimetableDay(models.Model):
    # Keep the existing model name/admin URL while each row now represents
    # one scheduled class, rather than a day containing separate lectures.
    room = models.ForeignKey(
        "rooms.Room", on_delete=models.PROTECT, related_name="timetable_days",
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    # Legacy entries may have no course/session. The admin requires both on save.
    course = models.ForeignKey(
        Course, on_delete=models.PROTECT, related_name="timetables", null=True, blank=True,
    )
    academic_session = models.CharField(max_length=30, blank=True)
    is_cancelled = models.BooleanField(
        default=False,
        help_text="Cancel this class to release its time slot while keeping the timetable record.",
    )

    class Meta:
        verbose_name = "Timetable"
        verbose_name_plural = "Timetables"
        ordering = ["date", "start_time", "room__code"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(start_time__lt=models.F("end_time")),
                name="timetable_start_before_end",
            ),
        ]

    @property
    def title(self):
        return str(self.course) if self.course_id else "Scheduled class"

    def __str__(self):
        return f"{self.room.name} — {self.date} — {self.start_time:%H:%M}"

    def clean(self):
        super().clean()
        if self.start_time is None or self.end_time is None:
            return
        if self.start_time >= self.end_time:
            raise ValidationError({"end_time": "End time must be after start time."})
        if not self.is_cancelled and self.room_id and self.date:
            conflicts = TimetableDay.objects.filter(
                room_id=self.room_id, date=self.date,
                is_cancelled=False,
                start_time__lt=self.end_time, end_time__gt=self.start_time,
            ).exclude(pk=self.pk)
            if conflicts.exists():
                raise ValidationError("This room already has a timetable entry overlapping that time.")
            from bookings.models import Reservation
            if Reservation.objects.filter(
                room_id=self.room_id, date=self.date, status=Reservation.Status.APPROVED,
                is_archived=False, start_time__lt=self.end_time, end_time__gt=self.start_time,
            ).exists():
                raise ValidationError("This time overlaps an approved reservation. Cancel that reservation or choose another time.")

    def save(self, *args, **kwargs):
        room_ids = [self.room_id]
        if self.pk:
            room_ids += list(type(self).objects.filter(pk=self.pk).values_list("room_id", flat=True))
        with lock_rooms(room_ids):
            self.full_clean()
            return super().save(*args, **kwargs)
