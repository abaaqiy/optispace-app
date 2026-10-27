from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

from .email_policy import validate_oau_account_email


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        LECTURER = "lecturer", "Lecturer"

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.STUDENT,
        help_text="Superusers are treated as application administrators.",
    )

    department = models.CharField(
        max_length=150,
        blank=True,
    )

    institutional_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Student matric number or lecturer staff ID.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                condition=~models.Q(email=""),
                name="unique_user_email_ci",
            ),
            models.UniqueConstraint(
                fields=["role", "institutional_id"],
                condition=~models.Q(institutional_id=""),
                name="unique_role_institutional_id",
            ),
        ]

    def clean(self):
        super().clean()

        self.institutional_id = (
            self.institutional_id or ""
        ).strip().upper()

        try:
            self.email = validate_oau_account_email(self)
        except ValidationError as error:
            raise ValidationError({
                "email": error.messages,
            }) from error

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")

        # Django updates only this timestamp after successful login.
        # It is not creating an account or changing its email/role.
        is_login_timestamp_update = (
            not self._state.adding
            and update_fields is not None
            and set(update_fields) == {"last_login"}
        )

        if not is_login_timestamp_update:
            self.full_clean()

        return super().save(*args, **kwargs)

