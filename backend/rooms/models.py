from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.db import models

from .catalog import building_identity_key, room_identity_key


class Building(models.Model):
    name = models.CharField(max_length=200, unique=True)
    name_key = models.CharField(max_length=400, unique=True, editable=False)
    campus_zone = models.CharField(max_length=150)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=~models.Q(name_key=''), name='building_name_key_required'),
            models.UniqueConstraint(
                models.Func(models.functions.Lower('name'), models.Value('[^a-z0-9]'),
                            models.Value(''), models.Value('g'), function='REGEXP_REPLACE',
                            output_field=models.CharField()),
                name='building_name_normalised_unique',
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        self.name_key = building_identity_key(self.name)
        if not self.name_key:
            raise ValidationError({'name': 'Enter a building name containing letters or numbers.'})
        if type(self).objects.filter(name_key=self.name_key).exclude(pk=self.pk).exists():
            raise ValidationError({'name': 'This building already exists. Select or edit its existing record.'})

    def save(self, *args, **kwargs):
        self.clean()
        if kwargs.get('update_fields') is not None and 'name' in kwargs['update_fields']:
            kwargs['update_fields'] = {*kwargs['update_fields'], 'name_key'}
        return super().save(*args, **kwargs)


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
    name_key = models.CharField(max_length=400, unique=True, editable=False)
    building = models.ForeignKey(
        Building, on_delete=models.PROTECT,
        related_name="rooms",
    )
    room_number = models.CharField(max_length=50, blank=True)
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
            models.CheckConstraint(condition=~models.Q(name_key=''), name='room_name_key_required'),
            models.UniqueConstraint(
                models.Func(models.functions.Lower('name'), models.Value('[^a-z0-9]'),
                            models.Value(''), models.Value('g'), function='REGEXP_REPLACE',
                            output_field=models.CharField()),
                name='room_name_normalised_unique',
            ),
            models.CheckConstraint(
                condition=models.Q(capacity__gte=1),
                name="room_capacity_positive",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        self.name_key = room_identity_key(self.name)
        if not self.name_key:
            raise ValidationError({'name': 'Enter a room name containing letters or numbers.'})
        if type(self).objects.filter(name_key=self.name_key).exclude(pk=self.pk).exists():
            raise ValidationError({'name': 'This room already exists. Select or edit its existing record.'})

    def save(self, *args, **kwargs):
        self.clean()
        if kwargs.get('update_fields') is not None and 'name' in kwargs['update_fields']:
            kwargs['update_fields'] = {*kwargs['update_fields'], 'name_key'}
        return super().save(*args, **kwargs)
