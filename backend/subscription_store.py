from datetime import datetime, timezone
from typing import Any, Optional

from backend.db import get_connection


def initialize_subscription_store() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS subscriptions (
                    email TEXT PRIMARY KEY,
                    tier_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    dodo_subscription_id TEXT,
                    dodo_checkout_session_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        connection.commit()


def upsert_subscription(
    *,
    email: str,
    tier_id: str,
    status: str,
    dodo_subscription_id: Optional[str] = None,
    dodo_checkout_session_id: Optional[str] = None,
) -> None:
    email = email.strip().lower()
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO subscriptions (
                    email, tier_id, status, dodo_subscription_id, dodo_checkout_session_id, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET
                    tier_id = excluded.tier_id,
                    status = excluded.status,
                    dodo_subscription_id = COALESCE(excluded.dodo_subscription_id, subscriptions.dodo_subscription_id),
                    dodo_checkout_session_id = COALESCE(excluded.dodo_checkout_session_id, subscriptions.dodo_checkout_session_id),
                    updated_at = excluded.updated_at
                """,
                (email, tier_id, status, dodo_subscription_id, dodo_checkout_session_id, now, now),
            )
        connection.commit()


def get_subscription(email: str) -> Optional[dict[str, Any]]:
    email = email.strip().lower()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM subscriptions WHERE email = %s", (email,))
            row = cursor.fetchone()

    return dict(row) if row else None


def get_subscription_by_dodo_id(dodo_subscription_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM subscriptions WHERE dodo_subscription_id = %s", (dodo_subscription_id,)
            )
            row = cursor.fetchone()

    return dict(row) if row else None


def set_status_by_dodo_id(dodo_subscription_id: str, status: str) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE subscriptions SET status = %s, updated_at = %s WHERE dodo_subscription_id = %s",
                (status, now, dodo_subscription_id),
            )
            updated = cursor.rowcount > 0
        connection.commit()
        return updated


def get_active_tier(email: str) -> Optional[str]:
    """Returns the tier_id if the user has an active subscription, else None."""
    sub = get_subscription(email)
    if sub and sub["status"] == "active":
        return sub["tier_id"]
    return None


def list_all_subscriptions() -> list[dict[str, Any]]:
    """For the admin overview panel — all subscriptions regardless of status,
    most recently updated first."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM subscriptions ORDER BY updated_at DESC")
            rows = cursor.fetchall()
    return [dict(row) for row in rows]
