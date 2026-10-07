"""One row per subscriber in a service wind-down: what we did on Dodo, what
we told them, and whether it still needs doing. Rows are kept after a
wind-down ends so there is always a record of who was cancelled and why.
Nothing here ever deletes a user, a subscription row or any user data."""

from datetime import datetime, timezone
from typing import Any, Optional

from backend.db import get_connection

_FIELDS = {"status", "access_until", "refund_status", "refund_amount", "refund_currency", "error", "notified"}


def initialize_wind_down_store() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS wind_down_items (
                    email TEXT PRIMARY KEY,
                    tier_id TEXT,
                    dodo_subscription_id TEXT,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    access_until TEXT,
                    refund_status TEXT NOT NULL DEFAULT 'none',
                    refund_amount REAL,
                    refund_currency TEXT,
                    error TEXT,
                    notified BOOLEAN NOT NULL DEFAULT FALSE,
                    updated_at TEXT NOT NULL
                )
                """
            )
        connection.commit()


def add_item(email: str, tier_id: str, dodo_subscription_id: Optional[str], mode: str) -> bool:
    """Adds a pending row. Returns False (and changes nothing) if one exists,
    so starting twice never resets progress."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO wind_down_items (email, tier_id, dodo_subscription_id, mode, status, updated_at) "
                "VALUES (%s, %s, %s, %s, 'pending', %s) ON CONFLICT (email) DO NOTHING",
                (email, tier_id, dodo_subscription_id, mode, now),
            )
            added = cursor.rowcount == 1
        connection.commit()
    return added


def update_item(email: str, **fields: Any) -> None:
    fields = {k: v for k, v in fields.items() if k in _FIELDS}
    fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    sets = ", ".join(f"{k} = %s" for k in fields)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"UPDATE wind_down_items SET {sets} WHERE email = %s", (*fields.values(), email))
        connection.commit()


def get_item(email: str) -> Optional[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM wind_down_items WHERE email = %s", (email,))
            row = cursor.fetchone()
    return dict(row) if row else None


def list_items() -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM wind_down_items ORDER BY updated_at DESC")
            return [dict(r) for r in cursor.fetchall()]


def todo_items(limit: int) -> list[dict[str, Any]]:
    """Rows still to do: never tried, or failed last time."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM wind_down_items WHERE status IN ('pending', 'failed') ORDER BY email LIMIT %s",
                (limit,),
            )
            return [dict(r) for r in cursor.fetchall()]


def counts() -> dict[str, int]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT status, COUNT(*) AS n FROM wind_down_items GROUP BY status")
            return {r["status"]: int(r["n"]) for r in cursor.fetchall()}
