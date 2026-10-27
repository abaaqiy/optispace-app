"""Production configuration, SPA routing, and HTTPS session integration."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import OperationalError
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from .runtime import runtime_from_environment


PRODUCTION_ENV = {
    "DJANGO_DEBUG": "false",
    "DJANGO_SECRET_KEY": "Deployment-Tests-Only:9qLm!" * 3,
    "DJANGO_ALLOWED_HOSTS": "optispace.onrender.com",
    "DJANGO_TRUST_PROXY": "true",
}


class DeploymentConfigurationTests(SimpleTestCase):
    def production(self, **changes):
        return runtime_from_environment({**PRODUCTION_ENV, **changes})

    def test_local_defaults_preserve_http_development(self):
        config = runtime_from_environment({})

        self.assertTrue(config["DEBUG"])
        self.assertTrue(config["SECRET_KEY"])
        self.assertFalse(config["SESSION_COOKIE_SECURE"])
        self.assertFalse(config["CSRF_COOKIE_SECURE"])
        self.assertFalse(config["SECURE_SSL_REDIRECT"])
        self.assertFalse(config.get("SECURE_PROXY_SSL_HEADER"))

    def test_production_enables_https_and_secure_cookies(self):
        config = self.production()

        self.assertFalse(config["DEBUG"])
        self.assertEqual(config["SECRET_KEY"], PRODUCTION_ENV["DJANGO_SECRET_KEY"])
        self.assertEqual(config["ALLOWED_HOSTS"], ["optispace.onrender.com"])
        self.assertTrue(config["SESSION_COOKIE_SECURE"])
        self.assertTrue(config["CSRF_COOKIE_SECURE"])
        self.assertTrue(config["SECURE_SSL_REDIRECT"])
        self.assertGreater(config["SECURE_HSTS_SECONDS"], 0)
        self.assertEqual(config["SECURE_PROXY_SSL_HEADER"], ("HTTP_X_FORWARDED_PROTO", "https"))

    def test_proxy_headers_are_trusted_only_when_enabled(self):
        config = self.production(DJANGO_TRUST_PROXY="false")

        self.assertFalse(config.get("SECURE_PROXY_SSL_HEADER"))

    def test_production_rejects_missing_short_and_insecure_secrets(self):
        for secret in ("", "short-secret", "django-insecure-" + "a" * 60):
            with self.subTest(secret_type=secret[:16]):
                with self.assertRaises(ImproperlyConfigured):
                    self.production(DJANGO_SECRET_KEY=secret)

    def test_development_accepts_an_explicit_secret(self):
        config = runtime_from_environment({"DJANGO_SECRET_KEY": "local-test-secret"})

        self.assertEqual(config["SECRET_KEY"], "local-test-secret")

    def test_render_generated_secret_remains_stable_and_passes_length_check(self):
        # Render generateValue provides 32 random bytes encoded as base64.
        generated = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG="
        self.assertEqual(len(generated), 44)

        first = self.production(DJANGO_SECRET_KEY=generated)
        second = self.production(DJANGO_SECRET_KEY=generated)

        self.assertEqual(first["SECRET_KEY"], "optispace:" + generated)
        self.assertEqual(first["SECRET_KEY"], second["SECRET_KEY"])
        self.assertGreaterEqual(len(first["SECRET_KEY"]), 50)

    def test_known_boolean_values_are_parsed(self):
        for value in ("false", "0", "no"):
            with self.subTest(value=value):
                self.assertFalse(self.production(DJANGO_DEBUG=value)["DEBUG"])
        for value in ("true", "1", "yes"):
            with self.subTest(value=value):
                self.assertTrue(runtime_from_environment({"DJANGO_DEBUG": value})["DEBUG"])

    def test_unknown_boolean_does_not_silently_enable_debug(self):
        with self.assertRaises(ImproperlyConfigured):
            self.production(DJANGO_DEBUG="fales")

    def test_production_requires_a_host(self):
        with self.assertRaises(ImproperlyConfigured):
            self.production(DJANGO_ALLOWED_HOSTS="")

    def test_production_rejects_wildcards_and_urls_as_hosts(self):
        for host in (
            "*", "https://optispace.onrender.com", "example.com/path",
            "user@example.com", "a..b", "a.-b", "a" * 64 + ".example",
        ):
            with self.subTest(host=host):
                with self.assertRaises(ImproperlyConfigured):
                    self.production(DJANGO_ALLOWED_HOSTS=host)

    def test_host_lists_ignore_separator_whitespace(self):
        config = self.production(DJANGO_ALLOWED_HOSTS="optispace.onrender.com, example.org ")

        self.assertEqual(config["ALLOWED_HOSTS"], ["optispace.onrender.com", "example.org"])

    def test_render_hostname_supplies_host_and_https_csrf_origin(self):
        config = self.production(
            DJANGO_ALLOWED_HOSTS="",
            RENDER_EXTERNAL_HOSTNAME="optispace-demo.onrender.com",
        )

        self.assertIn("optispace-demo.onrender.com", config["ALLOWED_HOSTS"])
        self.assertIn("https://optispace-demo.onrender.com", config["CSRF_TRUSTED_ORIGINS"])

    def test_render_hostname_is_validated(self):
        with self.assertRaises(ImproperlyConfigured):
            self.production(RENDER_EXTERNAL_HOSTNAME="https://optispace.onrender.com/path")

    def test_explicit_production_csrf_origins_require_https_origins(self):
        for origin in (
            "http://example.org",
            "example.org",
            "https://example.org/path",
            "https://user:password@example.org",
            "https://example.org?query=1",
        ):
            with self.subTest(origin=origin):
                with self.assertRaises(ImproperlyConfigured):
                    self.production(DJANGO_CSRF_TRUSTED_ORIGINS=origin)

    def test_explicit_https_origins_are_supported(self):
        config = self.production(DJANGO_CSRF_TRUSTED_ORIGINS="https://example.org, https://example.net")

        self.assertIn("https://example.org", config["CSRF_TRUSTED_ORIGINS"])
        self.assertIn("https://example.net", config["CSRF_TRUSTED_ORIGINS"])


@override_settings(DEBUG=False, ALLOWED_HOSTS=["testserver"], SECURE_SSL_REDIRECT=False)
class FrontendRoutingTests(SimpleTestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.frontend_root = Path(self.directory.name)
        self.index = b'<!doctype html><html><body><div id="root">SPA test</div></body></html>'
        (self.frontend_root / "index.html").write_bytes(self.index)
        (self.frontend_root / "assets").mkdir()
        (self.frontend_root / "assets" / "index-abcdefgh.js").write_text("console.log('SPA test');")
        (self.frontend_root / "app-icon.jpg").write_bytes(b"test-icon")
        self.static_root = self.frontend_root / "staticfiles"
        (self.static_root / "admin" / "css").mkdir(parents=True)
        (self.static_root / "admin" / "css" / "base.css").write_text("body { color: black; }")
        self.settings_override = override_settings(
            FRONTEND_ROOT=self.frontend_root,
            WHITENOISE_ROOT=self.frontend_root,
            STATIC_ROOT=self.static_root,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def body(self, response):
        if response.streaming:
            return b"".join(response.streaming_content)
        return response.content

    def test_public_and_direct_admin_entry_points_serve_built_spa(self):
        for path in ("/", "/staff-login", "/staff-login/"):
            with self.subTest(path=path):
                response = self.client.get(path)

                self.assertEqual(response.status_code, 200)
                self.assertIn("text/html", response["Content-Type"])
                self.assertEqual(response["Cache-Control"], "no-store")
                self.assertEqual(self.body(response), self.index)

    def test_unknown_api_and_page_paths_do_not_receive_spa_html(self):
        for path in ("/api/not-a-real-route/", "/not-a-real-page/", "/assets/missing.js"):
            with self.subTest(path=path):
                response = self.client.get(path)

                self.assertEqual(response.status_code, 404)
                self.assertNotEqual(self.body(response), self.index)

    def test_admin_keeps_django_login_and_permissions(self):
        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])
        self.assertNotEqual(self.body(response), self.index)

    def test_missing_frontend_build_returns_404(self):
        (self.frontend_root / "index.html").unlink()

        response = self.client.get("/")

        self.assertEqual(response.status_code, 404)

    def test_frontend_assets_and_admin_styles_share_the_host(self):
        for path, expected in (
            ("/assets/index-abcdefgh.js", b"console.log('SPA test');"),
            ("/app-icon.jpg", b"test-icon"),
            ("/static/admin/css/base.css", b"body { color: black; }"),
        ):
            with self.subTest(path=path):
                response = self.client.get(path)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.body(response), expected)

    def test_hashed_assets_are_immutable_and_html_is_not_cached(self):
        asset = self.client.get("/assets/index-abcdefgh.js")
        self.assertEqual(asset.status_code, 200)
        self.assertIn("immutable", asset["Cache-Control"])
        self.body(asset)

        html = self.client.get("/index.html")
        self.assertEqual(html.status_code, 200)
        self.assertEqual(html["Cache-Control"], "no-store")
        self.assertEqual(self.body(html), self.index)

    def test_host_validation_also_covers_static_assets(self):
        response = self.client.get("/assets/index-abcdefgh.js", HTTP_HOST="attacker.example")

        self.assertEqual(response.status_code, 400)


@override_settings(**runtime_from_environment(PRODUCTION_ENV))
class ProductionHealthProbeTests(TestCase):
    @patch("config.views.connection.cursor")
    def test_internal_http_probe_checks_database_instead_of_redirecting(self, cursor):
        response = self.client.get("/api/health/", HTTP_HOST="optispace.onrender.com")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Location", response)
        self.assertEqual(response.json()["database"], "ok")
        cursor.return_value.__enter__.return_value.execute.assert_called_once_with("SELECT 1")

    @patch("config.views.connection.cursor")
    def test_internal_http_database_outage_is_unhealthy_instead_of_redirecting(self, cursor):
        cursor.side_effect = OperationalError("private connection details")

        response = self.client.get("/api/health/", HTTP_HOST="optispace.onrender.com")

        self.assertEqual(response.status_code, 503)
        self.assertNotIn("Location", response)
        self.assertEqual(response.json()["database"], "unavailable")
        self.assertNotContains(response, "private connection details", status_code=503)


class ProductionSessionTests(TestCase):
    password = "Production-Login-Tests-934!"
    host = "optispace.onrender.com"
    origin = "https://optispace.onrender.com"

    @classmethod
    def setUpTestData(cls):
        cls.administrator = get_user_model().objects.create_superuser(
            username="deployment-admin",
            email="deployment-admin@oauife.edu.ng",
            password=cls.password,
        )

    def setUp(self):
        self.settings_override = override_settings(**runtime_from_environment(PRODUCTION_ENV))
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.client = APIClient(enforce_csrf_checks=True)
        self.proxy_headers = {
            "HTTP_HOST": self.host,
            "HTTP_X_FORWARDED_PROTO": "https",
            "HTTP_ORIGIN": self.origin,
        }

    def csrf_token(self):
        response = self.client.get("/api/auth/csrf/", **self.proxy_headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.cookies["csrftoken"]["secure"])
        return response.data["csrfToken"]

    def sign_in(self):
        return self.client.post(
            "/api/auth/login/",
            {"email": self.administrator.email, "password": self.password},
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf_token(),
            **self.proxy_headers,
        )

    def test_http_requests_redirect_to_https(self):
        response = self.client.get("/api/auth/csrf/", HTTP_HOST=self.host)

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], self.origin + "/api/auth/csrf/")

    def test_https_proxy_login_session_also_opens_django_admin(self):
        response = self.sign_in()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user"]["role"], "admin")
        self.assertTrue(response.cookies["sessionid"]["secure"])
        self.assertTrue(response.cookies["sessionid"]["httponly"])
        self.assertEqual(response.cookies["sessionid"]["samesite"], "Lax")
        current = self.client.get("/api/auth/me/", **self.proxy_headers)
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.data["user"]["id"], str(self.administrator.pk))
        self.assertEqual(self.client.get("/admin/", **self.proxy_headers).status_code, 200)

    def test_foreign_origin_cannot_submit_login_even_with_csrf_token(self):
        headers = {**self.proxy_headers, "HTTP_ORIGIN": "https://attacker.example"}
        response = self.client.post(
            "/api/auth/login/",
            {"email": self.administrator.email, "password": self.password},
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf_token(),
            **headers,
        )

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_remains_csrf_protected_in_production(self):
        response = self.client.post(
            "/api/auth/login/",
            {"email": self.administrator.email, "password": self.password},
            format="json",
            **self.proxy_headers,
        )

        self.assertEqual(response.status_code, 403)

    def test_authenticated_and_failed_api_responses_disable_shared_caching(self):
        anonymous = self.client.get("/api/auth/me/", **self.proxy_headers)
        self.assertEqual(anonymous.status_code, 403)
        self.assertEqual(anonymous["Cache-Control"], "private, no-store")

        self.assertEqual(self.sign_in().status_code, 200)
        current = self.client.get("/api/auth/me/", **self.proxy_headers)
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current["Cache-Control"], "private, no-store")

    def test_forwarded_https_does_not_skip_host_validation(self):
        response = self.client.get(
            "/api/auth/csrf/",
            HTTP_HOST="attacker.example",
            HTTP_X_FORWARDED_PROTO="https",
        )

        self.assertEqual(response.status_code, 400)

    def test_https_logout_ends_api_and_admin_session(self):
        self.assertEqual(self.sign_in().status_code, 200)
        response = self.client.post(
            "/api/auth/logout/",
            {},
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf_token(),
            **self.proxy_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me/", **self.proxy_headers).status_code, 403)
        self.assertEqual(self.client.get("/admin/", **self.proxy_headers).status_code, 302)
