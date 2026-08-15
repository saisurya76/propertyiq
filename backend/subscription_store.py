import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DEFAULT_DB_PATH = Path(os.getenv("PROPERTYIQ_SUBSCRIPTION_DB_PATH", "data/propertyiq_subscriptions.db"))


def _connect() -> sqlite3.Connection:
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DEFAULT_DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_subscription_store() -> None:
    with _connect() as connection:
        connection.execute(
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

    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO subscriptions (
                email, tier_id, status, dodo_subscription_id, dodo_checkout_session_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET
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
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM subscriptions WHERE email = ?", (email,)
        ).fetchone()

    return dict(row) if row else None


def get_subscription_by_dodo_id(dodo_subscription_id: str) -> Optional[dict[str, Any]]:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM subscriptions WHERE dodo_subscription_id = ?", (dodo_subscription_id,)
        ).fetchone()

    return dict(row) if row else None


def set_status_by_dodo_id(dodo_subscription_id: str, status: str) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        cursor = connection.execute(
            "UPDATE subscriptions SET status = ?, updated_at = ? WHERE dodo_subscription_id = ?",
            (status, now, dodo_subscription_id),
        )
        connection.commit()
        return cursor.rowcount > 0


def get_active_tier(email: str) -> Optional[str]:
    """Returns the tier_id if the user has an active subscription, else None."""
    sub = get_subscription(email)
    if sub and sub["status"] == "active":
        return sub["tier_id"]
    return None
