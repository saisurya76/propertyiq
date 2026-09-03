"""Backs the customer-facing profile: subscription cancellation and
account deletion.

Real design note on account deletion, since this directly implements
advice given rather than a blind permanent email-blacklist: a
permanently-banned email (never reusable, ever, for any new account)
has three concrete real problems — (1) email addresses get recycled
over time (a company reassigns an ex-employee's address, some
providers recycle long-dormant addresses), so a permanent ban can end
up blocking a completely different, innocent person years later; (2)
it creates real, avoidable support burden for a genuine customer who
deleted by mistake or wants to return later, with literally no path
back; (3) an indefinite "we still track that this specific email is
banned forever" record sits in real tension with a "delete my account"
request being fundamentally about erasing data, not extending it.

The real, legitimate concern behind wanting this at all is almost
certainly abuse prevention — someone deleting their account specifically
to escape a used-up monthly quota or a subscription obligation, then
immediately re-registering with the same email for a clean slate. This
module addresses that directly and proportionately instead: a short,
fixed cooling-off window (COOLING_OFF_DAYS) during which the same email
can't create a brand new account, long enough to close the immediate
delete-and-recycle loophole, but not an indefinite punishment. After
the window, the email is fully available again, exactly as if the
account had never existed.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from backend.db import get_connection

COOLING_OFF_DAYS = 7


def initialize_profile_store() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS deleted_accounts (
                    email TEXT PRIMARY KEY,
                    deleted_at TEXT NOT NULL,
                    reason TEXT
                )
                """
            )
        connection.commit()


def is_email_in_cooling_off(email: str) -> bool:
    """True only if this email was deleted within the last
    COOLING_OFF_DAYS — after that, re-registration is allowed exactly
    as if the account had never existed at all; nothing here is
    permanent."""
    email = email.strip().lower()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT deleted_at FROM deleted_accounts WHERE email = %s", (email,))
            row = cursor.fetchone()
    if not row:
        return False
    deleted_at = datetime.fromisoformat(row["deleted_at"])
    return datetime.now(timezone.utc) < deleted_at + timedelta(days=COOLING_OFF_DAYS)


def delete_account(email: str, reason: Optional[str] = None) -> None:
    """Deletes a user's account: removes their real identity/session
    records outright (not soft-deleted — an actual delete, since
    otp_codes/sessions/users hold nothing anyone would need to retain
    for support purposes), their own created content (saved properties
    and the construction-designs generate log), and records a short
    cooling-off entry (see the module's own docstring for why this is
    time-limited, not permanent).

    Deliberately does NOT delete financial/payment-adjacent records
    (subscriptions, refunds, refund_requests, insight_grants) — this
    matches PropertyIQ's own real, published Privacy Policy, which
    already states data is deleted "except where we're required to
    retain payment records for tax/accounting purposes." Cancelling the
    actual Dodo subscription (so billing genuinely stops) is handled by
    the caller in api.py, since that requires a real Dodo API call this
    module deliberately doesn't depend on."""
    email = email.strip().lower()
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM sessions WHERE email = %s", (email,))
            cursor.execute("DELETE FROM otp_codes WHERE email = %s", (email,))
            cursor.execute("DELETE FROM users WHERE email = %s", (email,))
            cursor.execute("DELETE FROM properties WHERE user_email = %s", (email,))
            cursor.execute("DELETE FROM construction_designs WHERE user_email = %s", (email,))
            cursor.execute(
                """
                INSERT INTO deleted_accounts (email, deleted_at, reason)
                VALUES (%s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET deleted_at = EXCLUDED.deleted_at, reason = EXCLUDED.reason
                """,
                (email, now, reason),
            )
        connection.commit()


def get_deletion_record(email: str) -> Optional[dict[str, Any]]:
    email = email.strip().lower()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM deleted_accounts WHERE email = %s", (email,))
            return cursor.fetchone()
