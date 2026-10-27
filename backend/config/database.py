"""PostgreSQL connection settings shared by all Django entry points."""

import dj_database_url
from django.core.exceptions import ImproperlyConfigured


def database_from_url(url):
    if not url:
        raise ImproperlyConfigured(
            "DATABASE_URL is required. Copy backend/.env.example to "
            "backend/.env and configure your PostgreSQL connection."
        )

    try:
        database = dj_database_url.parse(
            url,
            # runserver creates a thread per request. Keeping each thread's
            # connection open can exhaust a small hosted PostgreSQL service.
            conn_max_age=0,
        )
    except (ValueError, TypeError):
        # Do not expose a URL containing credentials in an error message.
        raise ImproperlyConfigured(
            "DATABASE_URL must be a valid PostgreSQL connection URL."
        ) from None

    if database["ENGINE"] != "django.db.backends.postgresql":
        raise ImproperlyConfigured(
            "DATABASE_URL must use PostgreSQL (postgres:// or postgresql://)."
        )

    options = database.setdefault("OPTIONS", {})
    options.setdefault("sslmode", "require")
    options.setdefault("connect_timeout", 10)

    return database
