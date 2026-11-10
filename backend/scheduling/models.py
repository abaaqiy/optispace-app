from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import models

from .services.locking import lock_rooms
from config.clocks import clock_label


class Course(models.Model):
    code = models.CharField(max_length=30, unique=True)
    title = models.CharField(max_length=200, blank=True)
    title_pending = models.BooleanField(
        default=False,
        verbose_name="Title awaiting confirmation",
        help_text="Use only when the course code is confirmed but its title is unknown. Enter the title later to resolve it.",
    )
    department = models.CharField(max_length=150)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} — {self.title or 'Title awaiting confirmation'}"

    def clean(self):
        super().clean()
        self.title = self.title.strip()
        if self.title:
            self.title_pending = False
        elif not self.title_pending:
            raise ValidationError({"title": "Enter a title or explicitly mark it as awaiting confirmation."})


class TimetableImageImport(models.Model):
    """Shared provenance for classes confirmed together, not a new admin category."""
    filename = models.CharField(max_length=255)
    department = models.CharField(max_length=150, blank=True)
    faculty = models.CharField(max_length=150, blank=True)
    academic_session = models.CharField(max_length=30)
    semester = models.CharField(max_length=20, blank=True)
    source_version = models.CharField(max_length=100, blank=True)
    first_date = models.DateField()
    last_date = models.DateField()
    exclude_dates = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return " · ".join(filter(None, (
            self.department, self.academic_session, self.semester, self.source_version,
        )))


class TimetableImageDraft(models.Model):
    """Private, expiring review state; deliberately not an admin category."""
    key = models.CharField(max_length=64, primary_key=True, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='timetable_image_drafts')
    filename = models.CharField(max_length=255)
    document = models.JSONField()
    image = models.BinaryField(editable=False)
    saved_at = models.DateTimeField()
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ['-saved_at']

    def __str__(self):
        return self.filename


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
    image_import = models.ForeignKey(
        TimetableImageImport, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="classes", editable=False,
    )
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
        return f"{self.room.name} — {self.date} — {clock_label(self.start_time)}"

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
