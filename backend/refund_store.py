"""Tracks PropertyIQ's own record of every refund — both real ones
issued through Dodo's API (or Dodo's own dashboard, reflected here via
webhook) and manual ones an admin records for a case Dodo didn't
handle (a duplicate charge fixed by a direct bank transfer, a
goodwill refund done another way, etc).

Dodo itself remains the actual source of truth for whether money moved
— this table exists so PropertyIQ has its own audit trail of refund
activity in one place, including the cases Dodo never sees at all.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from backend.db import get_connection


def initialize_refund_store() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS refunds (
                    id TEXT PRIMARY KEY,
                    dodo_refund_id TEXT,
                    dodo_payment_id TEXT,
                    user_email TEXT NOT NULL,
                    amount_usd REAL,
                    currency TEXT,
                    reason TEXT,
                    status TEXT NOT NULL,
                    is_manual BOOLEAN NOT NULL DEFAULT FALSE,
                    admin_note TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        connection.commit()


def record_dodo_refund(
    *,
    dodo_refund_id: str,
    dodo_payment_id: str,
    user_email: str,
    amount_usd: Optional[float],
    currency: Optional[str],
    reason: Optional[str],
    status: str,
) -> dict[str, Any]:
    """Records a refund actually issued through Dodo's real API (or
    reflected back via its webhook, if issued directly from Dodo's own
    dashboard instead of PropertyIQ's admin panel — see
    upsert_refund_status_by_dodo_id for that second path)."""
    now = datetime.now(timezone.utc).isoformat()
    record_id = str(uuid.uuid4())
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO refunds (id, dodo_refund_id, dodo_payment_id, user_email, amount_usd, currency, reason, status, is_manual, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, FALSE, %s, %s)
                """,
                (record_id, dodo_refund_id, dodo_payment_id, user_email.strip().lower(), amount_usd, currency, reason, status, now, now),
            )
        connection.commit()
    return get_refund(record_id)


def record_manual_refund(
    *,
    user_email: str,
    amount_usd: float,
    currency: str,
    reason: str,
    admin_note: str,
) -> dict[str, Any]:
    """Records a refund PropertyIQ handled OUTSIDE Dodo entirely — the
    real, explicit case this whole feature was requested for: something
    Dodo missed or couldn't process (an expired card with no way to
    re-charge for a partial correction, a goodwill gesture done by
    direct transfer, etc). Always status='manual', distinct from any
    real Dodo refund status, so it's never confused with a payment
    processor's own confirmation that money actually moved back."""
    now = datetime.now(timezone.utc).isoformat()
    record_id = str(uuid.uuid4())
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO refunds (id, dodo_refund_id, dodo_payment_id, user_email, amount_usd, currency, reason, status, is_manual, admin_note, created_at, updated_at)
                VALUES (%s, NULL, NULL, %s, %s, %s, %s, 'manual', TRUE, %s, %s, %s)
                """,
                (record_id, user_email.strip().lower(), amount_usd, currency, reason, admin_note, now, now),
            )
        connection.commit()
    return get_refund(record_id)


def upsert_refund_status_by_dodo_id(
    *,
    dodo_refund_id: str,
    status: str,
    dodo_payment_id: Optional[str] = None,
    user_email: Optional[str] = None,
    amount_usd: Optional[float] = None,
    currency: Optional[str] = None,
    reason: Optional[str] = None,
) -> None:
    """Called from the refund.succeeded/refund.failed webhook — keeps a
    refund record's status current even when the refund was issued
    directly from Dodo's own dashboard rather than through PropertyIQ's
    admin panel at all, since Dodo's webhook fires either way.

    Tries an UPDATE by dodo_refund_id first (the common case: a refund
    this app itself issued via /api/admin/refunds, now getting its
    real, confirmed status). If no row matched — genuinely the "issued
    directly in Dodo's own dashboard, PropertyIQ never saw it happen"
    case — inserts a brand-new record instead, using the real refund
    details the webhook payload itself carries, so it still shows up
    here for monitoring rather than only ever existing in Dodo's UI.
    This two-path behavior is the actual fix for a real gap an earlier
    draft of this function had: its own docstring claimed it would
    create a missing record, but the code only ever attempted the
    UPDATE half."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE refunds SET status = %s, updated_at = %s WHERE dodo_refund_id = %s",
                (status, now, dodo_refund_id),
            )
            if cursor.rowcount > 0:
                connection.commit()
                return

            record_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO refunds (id, dodo_refund_id, dodo_payment_id, user_email, amount_usd, currency, reason, status, is_manual, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, FALSE, %s, %s)
                """,
                (record_id, dodo_refund_id, dodo_payment_id, (user_email or "unknown").strip().lower(), amount_usd, currency, reason, status, now, now),
            )
        connection.commit()


def get_refund(record_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM refunds WHERE id = %s", (record_id,))
            return cursor.fetchone()


def list_all_refunds() -> list[dict[str, Any]]:
    """Every refund record, most recent first — the admin panel's own
    monitoring view, covering both Dodo-processed and manual entries in
    one place."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM refunds ORDER BY created_at DESC")
            return cursor.fetchall()
