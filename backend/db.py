import os

import psycopg2
import psycopg2.extras


def get_connection():
    """Returns a new psycopg2 connection to the shared Postgres database
    (Neon in production). DATABASE_URL is required — there is no SQLite
    fallback, since the whole point of this module is to stop losing data
    on every redeploy. Raises a clear error at call time if it's missing,
    rather than silently falling back to something ephemeral again."""

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. PropertyIQ requires a persistent Postgres database "
            "(e.g. a Neon connection string) — set DATABASE_URL to avoid losing sessions, "
            "subscriptions, and other data on every redeploy."
        )

    return psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)
