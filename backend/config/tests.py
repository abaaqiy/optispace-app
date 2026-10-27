from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.signals import request_finished
from django.db import OperationalError, connection
from django.test import SimpleTestCase, TestCase, TransactionTestCase

from .database import database_from_url


class DatabaseConfigurationTests(SimpleTestCase):
    def test_postgresql_url_decodes_credentials_and_requires_tls_by_default(self):
        database = database_from_url(
            "postgresql://avnadmin:p%40ss%3Aword@db.example.com:16541/defaultdb"
        )

        self.assertEqual(database["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(database["NAME"], "defaultdb")
        self.assertEqual(database["USER"], "avnadmin")
        self.assertEqual(database["PASSWORD"], "p@ss:word")
        self.assertEqual(database["HOST"], "db.example.com")
        self.assertEqual(database["PORT"], 16541)
        self.assertEqual(database["OPTIONS"]["sslmode"], "require")
        self.assertEqual(database["OPTIONS"]["connect_timeout"], 10)
        self.assertEqual(database["CONN_MAX_AGE"], 0)

    def test_explicit_certificate_verification_is_preserved(self):
        database = database_from_url(
            "postgres://user:password@db.example.com/app"
            "?sslmode=verify-full&sslrootcert=%2Fcerts%2Fca.pem"
            "&connect_timeout=5"
        )

        self.assertEqual(database["OPTIONS"]["sslmode"], "verify-full")
        self.assertEqual(database["OPTIONS"]["sslrootcert"], "/certs/ca.pem")
        self.assertEqual(database["OPTIONS"]["connect_timeout"], 5)

    def test_missing_url_does_not_fall_back_to_sqlite(self):
        for url in (None, ""):
            with self.subTest(url=url):
                with self.assertRaisesMessage(
                    ImproperlyConfigured, "DATABASE_URL is required"
                ):
                    database_from_url(url)

    def test_non_postgresql_databases_are_rejected(self):
        with self.assertRaisesMessage(ImproperlyConfigured, "must use PostgreSQL"):
            database_from_url("sqlite:///db.sqlite3")

    def test_malformed_url_does_not_expose_credentials(self):
        with self.assertRaises(ImproperlyConfigured) as error:
            database_from_url("postgres://user:secret@db.example.com:bad/app")

        self.assertNotIn("secret", str(error.exception))


class HealthCheckTests(TestCase):
    def test_health_checks_the_database_without_authentication(self):
        with self.assertNumQueries(1):
            response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "status": "ok",
            "service": "Optispace API",
            "database": "ok",
        })

    @patch("config.views.connection.cursor")
    def test_database_outage_returns_503_without_connection_details(self, cursor):
        cursor.side_effect = OperationalError("secret connection details")
        self.client.cookies[settings.SESSION_COOKIE_NAME] = "existing-session"

        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {
            "status": "error",
            "service": "Optispace API",
            "database": "unavailable",
        })
        self.assertNotContains(response, "secret", status_code=503)


class DatabaseConnectionLifecycleTests(TransactionTestCase):
    def test_request_completion_releases_database_connection(self):
        # TestCase's wrapping transaction would prevent normal connection closing.
        connection.ensure_connection()
        self.assertIsNotNone(connection.connection)

        request_finished.send(sender=self.__class__)

        self.assertIsNone(connection.connection)
