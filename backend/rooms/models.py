from django.core.validators import MinValueValidator
from django.db import models


class Facility(models.Model):
    class Code(models.TextChoices):
        AC = "ac", "Air conditioning"
        PROJECTOR = "projector", "Projector"
        POWER = "power", "Power supply"
        AUDIO = "audio", "Audio system"
        WIFI = "wifi", "Wi-Fi"

    code = models.CharField(
        max_length=20,
        choices=Code.choices,
        unique=True,
    )

    class Meta:
        ordering = ["code"]
        verbose_name_plural = "Facilities"

    def __str__(self):
        return self.get_code_display()


class Room(models.Model):
    class SizeCategory(models.TextChoices):
        SMALL = "small", "Small"
        LARGE = "large", "Large"

    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=200)
    zone = models.CharField(max_length=150)
    room_type = models.CharField(max_length=100)

    capacity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )

    size_category = models.CharField(
        max_length=10,
        choices=SizeCategory.choices,
    )

    facilities = models.ManyToManyField(
        Facility,
        blank=True,
        related_name="rooms",
    )

    class Meta:
        ordering = ["code"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(capacity__gte=1),
                name="room_capacity_positive",
            ),
        ]

    def __str__(self):
        return f"{self.code} — {self.name}"

