from django.test import TestCase
from django.urls import reverse

from .models import User


class LecturerApprovalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.administrator = User.objects.create_superuser(
            username="approval-admin",
            email="approval-admin@oauife.edu.ng",
            password="Test-Only-Cloud-482!",
        )

        cls.lecturer = User.objects.create_user(
            username="approval-lecturer",
            email="approval-lecturer@oauife.edu.ng",
            password="Test-Only-Cloud-482!",
            role=User.Role.LECTURER,
            is_active=False,
        )

        cls.student = User.objects.create_user(
            username="approval-student",
            email="approval-student@student.oauife.edu.ng",
            password="Test-Only-Cloud-482!",
            role=User.Role.STUDENT,
        )

    def approve(self, accounts):
        return self.client.post(
            reverse("admin:accounts_user_changelist"),
            {
                "action": "approve_lecturers",
                "_selected_action": [
                    str(account.pk) for account in accounts
                ],
            },
        )

    def test_admin_approves_without_granting_admin_access(self):
        self.client.force_login(self.administrator)

        response = self.approve([self.lecturer])

        self.assertEqual(response.status_code, 302)

        self.lecturer.refresh_from_db()

        self.assertTrue(self.lecturer.is_active)
        self.assertFalse(self.lecturer.is_staff)
        self.assertFalse(self.lecturer.is_superuser)
        self.assertEqual(self.lecturer.role, User.Role.LECTURER)

    def test_action_does_not_activate_student_accounts(self):
        self.student.is_active = False
        self.student.save(update_fields=["is_active"])

        self.client.force_login(self.administrator)
        self.approve([self.lecturer, self.student])

        self.lecturer.refresh_from_db()
        self.student.refresh_from_db()

        self.assertTrue(self.lecturer.is_active)
        self.assertFalse(self.student.is_active)

    def test_student_cannot_use_admin_approval(self):
        self.client.force_login(self.student)

        self.approve([self.lecturer])

        self.lecturer.refresh_from_db()
        self.assertFalse(self.lecturer.is_active)

