from django.core.exceptions import ValidationError
from rest_framework.test import APIClient, APITestCase

from .models import User


class AccountTests(APITestCase):
    password = "Tide-Cloud-482-Quartz!"

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="demo-student",
            email="demo@student.oauife.edu.ng",
            password=cls.password,
            first_name="Demo",
            last_name="Student",
            role=User.Role.STUDENT,
        )

    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)

    def csrf_post(self, path, data):
        token = self.client.get("/api/auth/csrf/").data["csrfToken"]

        return self.client.post(
            path,
            data,
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )

    def sign_in(self, **changes):
        data = {
            "email": self.user.email,
            "password": self.password,
        }
        data.update(changes)

        return self.csrf_post("/api/auth/login/", data)

    def registration_data(self, **changes):
        data = {
            "name": "New Student",
            "email": "new@student.oauife.edu.ng",
            "password": self.password,
            "confirmPassword": self.password,
            "department": "Computer Science",
            "role": "student",
            "matricNumber": "CSC/2026/010",
        }
        data.update(changes)
        return data

    def test_login_and_current_user(self):
        response = self.sign_in(
            email="DEMO@STUDENT.OAUIFE.EDU.NG",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["role"], "student")
        self.assertNotIn("password", response.data["user"])

        current = self.client.get("/api/auth/me/")

        self.assertEqual(current.status_code, 200)
        self.assertEqual(
            current.data["user"]["id"],
            str(self.user.pk),
        )

    def test_wrong_password_is_rejected(self):
        response = self.sign_in(password="incorrect")

        self.assertEqual(response.status_code, 401)

    def test_current_user_requires_authentication(self):
        response = self.client.get("/api/auth/me/")

        self.assertEqual(response.status_code, 403)

    def test_client_cannot_select_admin_role(self):
        response = self.sign_in(role="admin")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["role"], "student")

    def test_login_and_registration_require_csrf(self):
        cases = [
            (
                "/api/auth/login/",
                {
                    "email": self.user.email,
                    "password": self.password,
                },
            ),
            (
                "/api/auth/register/",
                self.registration_data(),
            ),
        ]

        for path, data in cases:
            with self.subTest(path=path):
                response = self.client.post(
                    path,
                    data,
                    format="json",
                )
                self.assertEqual(response.status_code, 403)

    def test_logout_ends_session(self):
        self.assertEqual(self.sign_in().status_code, 200)

        without_token = self.client.post(
            "/api/auth/logout/",
            {},
            format="json",
        )
        self.assertEqual(without_token.status_code, 403)

        response = self.csrf_post("/api/auth/logout/", {})
        self.assertEqual(response.status_code, 200)

        current = self.client.get("/api/auth/me/")
        self.assertEqual(current.status_code, 403)

    def test_invalid_email_is_rejected_during_creation(self):
        cases = [
            ("student", "invalid@gmail.com"),
            ("student", "invalid@oauife.edu.ng"),
            ("lecturer", "invalid@student.oauife.edu.ng"),
            ("lecturer", "invalid@oauife.edu.ng.example.com"),
        ]

        for role, email in cases:
            with self.subTest(role=role, email=email):
                with self.assertRaises(ValidationError):
                    User.objects.create_user(
                        username="invalid-account",
                        email=email,
                        password=self.password,
                        role=role,
                    )

    def test_invalid_email_update_is_rejected(self):
        original_email = self.user.email
        self.user.email = "invalid@gmail.com"

        with self.assertRaises(ValidationError):
            self.user.save()

        self.user.refresh_from_db()
        self.assertEqual(self.user.email, original_email)

    def test_role_change_requires_matching_email(self):
        self.user.role = User.Role.LECTURER

        with self.assertRaises(ValidationError):
            self.user.save()

        self.user.email = "demo@oauife.edu.ng"
        self.user.save()

        response = self.sign_in()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["role"], "lecturer")

    def test_student_registration(self):
        response = self.csrf_post(
            "/api/auth/register/",
            self.registration_data(),
        )

        self.assertEqual(response.status_code, 201)

        user = User.objects.get(email="new@student.oauife.edu.ng")

        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.institutional_id, "CSC/2026/010")
        self.assertTrue(user.check_password(self.password))

        # A newly registered student must be able to sign in immediately.
        response = self.sign_in(email=user.email)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["role"], "student")
        current = self.client.get("/api/auth/me/")
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.data["user"]["id"], str(user.pk))

    def test_registration_rejects_wrong_domains(self):
        cases = [
            self.registration_data(email="new@gmail.com"),
            self.registration_data(email="new@oauife.edu.ng"),
            self.registration_data(
                role="lecturer",
                email="new@student.oauife.edu.ng",
                matricNumber="",
                staffId="STF/CSC/010",
            ),
        ]

        for data in cases:
            with self.subTest(email=data["email"], role=data["role"]):
                response = self.csrf_post("/api/auth/register/", data)

                self.assertEqual(response.status_code, 400)
                self.assertIn("email", response.data)

    def test_public_registration_cannot_create_admin(self):
        response = self.csrf_post(
            "/api/auth/register/",
            self.registration_data(role="admin"),
        )

        self.assertEqual(response.status_code, 400)

    def test_duplicate_email_is_rejected(self):
        response = self.csrf_post(
            "/api/auth/register/",
            self.registration_data(
                email="DEMO@STUDENT.OAUIFE.EDU.NG",
            ),
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.data)

    def test_lecturer_registration_requires_activation(self):
        response = self.csrf_post(
            "/api/auth/register/",
            self.registration_data(
                role="lecturer",
                email="new@oauife.edu.ng",
                matricNumber="",
                staffId="STF/CSC/010",
            ),
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["requiresApproval"])

        user = User.objects.get(email="new@oauife.edu.ng")
        self.assertFalse(user.is_active)

        before = self.sign_in(email=user.email)
        self.assertEqual(before.status_code, 403)
        self.assertIn("administrator to approve", before.data["detail"])
        self.assertNotIn("_auth_user_id", self.client.session)

        incorrect = self.sign_in(email=user.email, password="incorrect")
        self.assertEqual(incorrect.status_code, 401)
        self.assertEqual(incorrect.data["detail"], "Invalid email or password.")

        user.is_active = True
        user.save()

        after = self.sign_in(email=user.email)
        self.assertEqual(after.status_code, 200)
        self.assertEqual(after.data["user"]["role"], "lecturer")

    def test_registration_requires_matching_confirmation_for_both_roles(self):
        for role in ("student", "lecturer"):
            for confirmation in (None, "", "mismatched-password"):
                data = self.registration_data(role=role)
                if confirmation is None:
                    del data["confirmPassword"]
                else:
                    data["confirmPassword"] = confirmation
                with self.subTest(role=role, confirmation=confirmation):
                    before = User.objects.count()
                    response = self.csrf_post("/api/auth/register/", data)
                    self.assertEqual(response.status_code, 400)
                    self.assertIn("confirmPassword", response.data)
                    self.assertEqual(User.objects.count(), before)

    def test_confirmation_is_not_returned_or_stored(self):
        response = self.csrf_post("/api/auth/register/", self.registration_data())
        self.assertEqual(response.status_code, 201)
        self.assertNotIn("confirmPassword", str(response.data))
        self.assertNotIn(self.password, str(response.data))
        self.assertFalse(hasattr(User.objects.get(email="new@student.oauife.edu.ng"), "confirmPassword"))

    def test_inactive_student_gets_inactive_message_and_no_session(self):
        self.user.is_active = False
        self.user.save()
        response = self.sign_in()
        self.assertEqual(response.status_code, 403)
        self.assertIn("inactive", response.data["detail"])
        self.assertNotIn("approve", response.data["detail"])
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_unknown_email_keeps_generic_error(self):
        response = self.sign_in(email="not-registered@oauife.edu.ng")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["detail"], "Invalid email or password.")

