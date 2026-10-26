"""Environment settings for local development and HTTPS deployments."""

import re
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured


def _boolean(env, name, default):
    value = env.get(name, str(default)).strip().lower()
    if value in {"true", "1", "yes"}:
        return True
    if value in {"false", "0", "no"}:
        return False
    raise ImproperlyConfigured(f"{name} must be true or false.")


def _list(env, name):
    return [value.strip() for value in env.get(name, "").split(",") if value.strip()]


def _valid_host(host):
    if host == "[::1]":
        return True
    return len(host) <= 253 and all(
        re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
        for label in host.split(".")
    )


def runtime_from_environment(env):
    debug = _boolean(env, "DJANGO_DEBUG", True)
    secret = env.get("DJANGO_SECRET_KEY", "")
    # Render generates 256-bit base64 values (44 characters). A stable prefix
    # preserves their entropy and meets Django's 50-character deployment check.
    if re.fullmatch(r"[A-Za-z0-9+/]{43}=", secret):
        secret = f"optispace:{secret}"
    if not debug and (
        len(secret) < 50 or len(set(secret)) < 5 or secret.startswith("django-insecure-")
    ):
        raise ImproperlyConfigured(
            "Set DJANGO_SECRET_KEY to a generated secret of at least 50 characters "
            "when DJANGO_DEBUG is false."
        )

    hosts = _list(env, "DJANGO_ALLOWED_HOSTS")
    render_host = env.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
    if render_host and render_host not in hosts:
        hosts.append(render_host)
    if not hosts and debug:
        hosts = ["localhost", "127.0.0.1", "[::1]"]
    if not hosts or any(not _valid_host(host) for host in hosts):
        raise ImproperlyConfigured(
            "DJANGO_ALLOWED_HOSTS must contain hostnames without schemes, ports "
            "or wildcards. Render supplies RENDER_EXTERNAL_HOSTNAME automatically."
        )

    origins = _list(env, "DJANGO_CSRF_TRUSTED_ORIGINS")
    if debug and not origins:
        origins = ["http://127.0.0.1:5173", "http://localhost:5173"]
    if render_host:
        origins.append(f"https://{render_host}")
    for origin in origins:
        try:
            parsed = urlsplit(origin)
            valid = (
                parsed.scheme in ({"http", "https"} if debug else {"https"})
                and parsed.hostname and _valid_host(parsed.hostname)
                and parsed.path == "" and not parsed.query and not parsed.fragment
                and parsed.username is None and parsed.password is None
            )
            parsed.port  # Reject malformed ports without exposing environment values.
        except ValueError:
            valid = False
        if not valid:
            raise ImproperlyConfigured(
                "DJANGO_CSRF_TRUSTED_ORIGINS must contain valid origins; "
                "production origins must use HTTPS."
            )

    return {
        "DEBUG": debug,
        "SECRET_KEY": secret or "django-insecure-local-optispace-development-only-key",
        "ALLOWED_HOSTS": hosts,
        "CSRF_TRUSTED_ORIGINS": list(dict.fromkeys(origins)),
        "SESSION_COOKIE_SECURE": not debug,
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "CSRF_COOKIE_SECURE": not debug,
        "SECURE_SSL_REDIRECT": not debug,
        # Render accepts redirects as healthy; this probe must actually check PG.
        "SECURE_REDIRECT_EXEMPT": [r"^api/health/$"],
        "SECURE_PROXY_SSL_HEADER": (
            ("HTTP_X_FORWARDED_PROTO", "https")
            if _boolean(env, "DJANGO_TRUST_PROXY", False) else None
        ),
        "SECURE_HSTS_SECONDS": 31536000 if not debug else 0,
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": False,
        "SECURE_HSTS_PRELOAD": False,
        "SECURE_CONTENT_TYPE_NOSNIFF": True,
        "SECURE_REFERRER_POLICY": "same-origin",
    }
