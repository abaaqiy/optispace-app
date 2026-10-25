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
    room = models.ForeignKey(
        "rooms.Room",
        on_delete=models.PROTECT,
        related_name="timetable_days",
    )
    date = models.DateField()
    coverage_start = models.TimeField()
    coverage_end = models.TimeField()
    is_published = models.BooleanField(
        default=False,
        help_text=(
            "Publish only after verifying that the schedule is complete "
            "for this room, date, and coverage window."
        ),
    )

    class Meta:
        ordering = ["date", "room__code"]
        constraints = [
            models.UniqueConstraint(
                fields=["room", "date"],
                name="unique_room_timetable_date",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    coverage_start__lt=models.F("coverage_end")
                ),
                name="timetable_coverage_start_before_end",
            ),
        ]

    def __str__(self):
        return f"{self.room.code} — {self.date}"

    def clean(self):
        super().clean()

        if self.coverage_start is None or self.coverage_end is None:
            return

        if self.coverage_start >= self.coverage_end:
            raise ValidationError({
                "coverage_end": "Coverage must end after it starts.",
            })

        # Do not shorten coverage around existing active sessions.
        if self.pk:
            original = TimetableDay.objects.get(pk=self.pk)
            if (original.room_id, original.date) != (self.room_id, self.date):
                raise ValidationError("Create a new timetable to change its room or date.")

            outside_coverage = self.allocations.filter(
                is_cancelled=False,
            ).filter(
                models.Q(start_time__lt=self.coverage_start)
                | models.Q(end_time__gt=self.coverage_end)
            )

            if outside_coverage.exists():
                raise ValidationError(
                    "The coverage window must contain all active allocations."
                )

    def save(self, *args, **kwargs):
        with lock_rooms([self.room_id]):
            self.full_clean()
            return super().save(*args, **kwargs)


class Allocation(models.Model):
    timetable = models.ForeignKey(
        TimetableDay,
        on_delete=models.PROTECT,
        related_name="allocations",
    )
    title = models.CharField(max_length=200)
    course = models.ForeignKey(
        Course, on_delete=models.PROTECT, null=True, blank=True,
        related_name="allocations",
    )
    academic_session = models.CharField(max_length=30, blank=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_cancelled = models.BooleanField(default=False)

    class Meta:
        ordering = ["timetable__date", "start_time"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    start_time__lt=models.F("end_time")
                ),
                name="allocation_start_before_end",
            ),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()

        if (
            self.timetable_id is None
            or self.start_time is None
            or self.end_time is None
        ):
            return

        if self.start_time >= self.end_time:
            raise ValidationError({
                "end_time": "The session must end after it starts.",
            })

        # Cancelled sessions remain as records but do not reserve time.
        if self.is_cancelled:
            return

        timetable = TimetableDay.objects.filter(
            pk=self.timetable_id,
        ).first()

        if timetable is None:
            # Foreign-key validation handles a missing timetable.
            return

        if (
            self.start_time < timetable.coverage_start
            or self.end_time > timetable.coverage_end
        ):
            raise ValidationError(
                "The session must fit inside the timetable coverage window."
            )

        conflicts = Allocation.objects.filter(
            timetable_id=self.timetable_id,
            is_cancelled=False,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time,
        ).exclude(pk=self.pk)

        if conflicts.exists():
            raise ValidationError(
                "This room already has an allocation overlapping that time."
            )

        from bookings.models import Reservation

        if Reservation.objects.filter(
            room_id=timetable.room_id, date=timetable.date, status=Reservation.Status.APPROVED,
            start_time__lt=self.end_time, end_time__gt=self.start_time,
        ).exists():
            raise ValidationError("This lecture overlaps an approved reservation. Cancel or reschedule that reservation first.")

    def save(self, *args, **kwargs):
        room_ids = list(TimetableDay.objects.filter(
            pk=self.timetable_id,
        ).values_list("room_id", flat=True))
        if self.pk:
            room_ids += list(Allocation.objects.filter(pk=self.pk).values_list(
                "timetable__room_id", flat=True,
            ))
        with lock_rooms(room_ids):
            self.full_clean()
            return super().save(*args, **kwargs)

