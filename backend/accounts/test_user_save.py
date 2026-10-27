from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import User


class UserSaveTests(TestCase):
    password = "Tide-Cloud-482-Quartz!"

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="timestamp-test",
            email="timestamp@student.oauife.edu.ng",
            password=cls.password,
            role=User.Role.STUDENT,
        )

    def test_login_timestamp_does_not_revalidate_account(self):
        with patch.object(
            User,
            "full_clean",
            side_effect=AssertionError(
                "Login timestamp updates must not revalidate account fields."
            ),
        ):
            signed_in = self.client.login(
                username=self.user.username,
                password=self.password,
            )

        self.assertTrue(signed_in)

        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.last_login)

    def test_email_update_still_requires_valid_oau_domain(self):
        original_email = self.user.email
        self.user.email = "invalid@gmail.com"

        with self.assertRaises(ValidationError):
            self.user.save(update_fields=["email"])

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, original_email)

