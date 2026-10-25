from django.test import TestCase
from django.urls import reverse

from .models import User


class AdministratorCreationTests(TestCase):
    def test_existing_superuser_can_add_and_promote_another_administrator(self):
        manager = User.objects.create_superuser(username="manager", email="manager@oauife.edu.ng", password="Original-Mgr-849!")
        self.client.force_login(manager)
        password = "Another-Manager-846!"
        response = self.client.post(reverse("admin:accounts_user_add"), {
            "username": "another-admin", "usable_password": "true",
            "password1": password, "password2": password,
            "email": "another-admin@oauife.edu.ng", "role": "lecturer",
            "first_name": "Another", "last_name": "Administrator", "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        account = User.objects.get(username="another-admin")
        self.assertTrue(account.check_password(password))
        self.assertFalse(account.is_superuser)
        response = self.client.post(reverse("admin:accounts_user_change", args=[account.pk]), {
            "username": account.username, "email": account.email, "role": "lecturer",
            "first_name": "Another", "last_name": "Administrator",
            "is_active": "on", "is_staff": "on", "is_superuser": "on",
            "date_joined_0": "2026-10-25", "date_joined_1": "10:00:00", "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        account.refresh_from_db()
        self.assertTrue(account.is_active and account.is_staff and account.is_superuser)
        self.client.logout()
        response = self.client.post("/api/auth/login/", {"email": account.email, "password": password})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["role"], "admin")
        self.assertEqual(self.client.get(reverse("admin:accounts_user_add")).status_code, 200)
