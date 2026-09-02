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
            # A request queue sitting upstream of the `refunds` table
            # above -- a customer's claim, reviewed by an admin, which
            # (once approved) becomes a real row in `refunds` via the
            # existing issue-via-Dodo or record-manual flows. Kept
            # deliberately separate rather than merged into `refunds`
            # itself: a request that gets denied, or one still awaiting
            # review, was never a real refund and shouldn't live in the
            # same table as ones that genuinely happened.
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS refund_requests (
                    id TEXT PRIMARY KEY,
                    user_email TEXT NOT NULL,
                    reason_code TEXT NOT NULL,
                    details TEXT,
                    purchase_reference TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    linked_refund_id TEXT,
                    admin_response TEXT,
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


# ---------------------------------------------------------------------
# Refund requests — the user-facing intake queue sitting upstream of
# the refund-fulfillment functions above. See refund_request_module_spec.md
# for the full design; this is the "simple way" version of it.
# ---------------------------------------------------------------------

VALID_REASON_CODES = {
    "report_never_generated",
    "duplicate_charge",
    "report_incorrect",
    "insight_addon_technical_failure",
    "first_month_guarantee",
    "charged_after_cancellation",
    "wrong_plan_charged",
    "other",
}


def create_refund_request(
    *,
    user_email: str,
    reason_code: str,
    details: Optional[str],
    purchase_reference: Optional[str],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    record_id = str(uuid.uuid4())
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO refund_requests (id, user_email, reason_code, details, purchase_reference, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s)
                """,
                (record_id, user_email.strip().lower(), reason_code, details, purchase_reference, now, now),
            )
        connection.commit()
    return get_refund_request(record_id)


def get_refund_request(record_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM refund_requests WHERE id = %s", (record_id,))
            return cursor.fetchone()


def get_refund_request_for_user(record_id: str, user_email: str) -> Optional[dict[str, Any]]:
    """The public status-check lookup — deliberately requires BOTH the
    request id and the matching email, not just the id alone, so a
    guessed/leaked request id can't be used to read someone else's
    refund request details (which purchase, what reason, any admin
    response)."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM refund_requests WHERE id = %s AND user_email = %s",
                (record_id, user_email.strip().lower()),
            )
            return cursor.fetchone()


def list_refund_requests(status: Optional[str] = None) -> list[dict[str, Any]]:
    """The admin queue view, most recent first, optionally filtered to
    one status (pending/approved/denied)."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            if status:
                cursor.execute(
                    "SELECT * FROM refund_requests WHERE status = %s ORDER BY created_at DESC",
                    (status,),
                )
            else:
                cursor.execute("SELECT * FROM refund_requests ORDER BY created_at DESC")
            return cursor.fetchall()


def approve_refund_request(record_id: str, linked_refund_id: str, admin_response: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Marks a request approved once it's actually been fulfilled — via
    either the real Dodo refund flow or a manual entry — linking back
    to the resulting row in the `refunds` table so the two stay
    traceable to each other."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE refund_requests SET status = 'approved', linked_refund_id = %s, admin_response = %s, updated_at = %s WHERE id = %s",
                (linked_refund_id, admin_response, now, record_id),
            )
        connection.commit()
    return get_refund_request(record_id)


def deny_refund_request(record_id: str, admin_response: str) -> Optional[dict[str, Any]]:
    """admin_response is required here (unlike approval's optional
    note) since it's the reason shown back to the user for why their
    request was denied -- a denial with no explanation isn't useful to
    them."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE refund_requests SET status = 'denied', admin_response = %s, updated_at = %s WHERE id = %s",
                (admin_response, now, record_id),
            )
        connection.commit()
    return get_refund_request(record_id)
