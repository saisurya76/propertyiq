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
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS user_profiles (
                    email TEXT PRIMARY KEY,
                    display_name TEXT
                )
                """
            )
            cursor.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS photo_url TEXT")
            cursor.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS contact_phone TEXT")
            cursor.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS contact_email TEXT")
            cursor.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS brokerage_name TEXT")
            cursor.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS custom_footer_text TEXT")
            cursor.execute("ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS share_slug TEXT")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_user_profiles_share_slug ON user_profiles (share_slug) WHERE share_slug IS NOT NULL")
        connection.commit()


_BRANDING_FIELDS = ["photo_url", "contact_phone", "contact_email", "brokerage_name", "custom_footer_text", "share_slug"]


def get_agent_branding(email: str) -> dict[str, Optional[str]]:
    """Real branding an agent has set for themselves, shown on their
    own Agent Intelligence reports and workspace UI — every field
    starts as None for every existing account, since none of this
    existed before. Callers render each field's own honest fallback
    (e.g. the agent's display name/email) rather than treating a
    missing value as an error."""
    email = email.strip().lower()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT {', '.join(_BRANDING_FIELDS)} FROM user_profiles WHERE email = %s", (email,))
            row = cursor.fetchone()
    if not row:
        return {field: None for field in _BRANDING_FIELDS}
    return {field: row[field] for field in _BRANDING_FIELDS}


def set_agent_branding(email: str, **fields: Optional[str]) -> dict[str, Optional[str]]:
    """Only updates the fields actually passed in -- a caller sending
    just `brokerage_name` doesn't accidentally blank out the agent's
    already-set photo_url or contact_phone. Each passed value is
    trimmed, with an empty string treated as a deliberate "clear this
    field" (same reasoning as set_display_name), not left as literal
    empty-string noise in the database."""
    email = email.strip().lower()
    unknown = set(fields) - set(_BRANDING_FIELDS)
    if unknown:
        raise ValueError(f"Unknown branding field(s): {', '.join(sorted(unknown))}")
    cleaned = {k: (v.strip() if v and v.strip() else None) for k, v in fields.items()}
    if not cleaned:
        return get_agent_branding(email)

    set_clause = ", ".join(f"{k} = %s" for k in cleaned)
    insert_cols = ", ".join(["email"] + list(cleaned.keys()))
    insert_placeholders = ", ".join(["%s"] * (1 + len(cleaned)))
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO user_profiles ({insert_cols}) VALUES ({insert_placeholders})
                ON CONFLICT (email) DO UPDATE SET {set_clause}
                """,
                [email] + list(cleaned.values()) + list(cleaned.values()),
            )
        connection.commit()
    return get_agent_branding(email)


def get_email_for_share_slug(slug: str) -> Optional[str]:
    """Real, case-insensitive lookup for a branded share link
    (app.propertyiqweb.com/a/{slug}) -- used to resolve a public link
    back to the agent who owns it, without ever exposing their email
    in the URL itself."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT email FROM user_profiles WHERE LOWER(share_slug) = LOWER(%s)", (slug.strip(),))
            row = cursor.fetchone()
    return row["email"] if row else None


def get_display_name(email: str) -> Optional[str]:
    """The real, human name a customer set for themselves (e.g. for
    use on an Agent Intelligence advisory report) — or None if they
    never set one, which every existing account starts as, since this
    app has only ever collected an email via OTP sign-in until now.
    Callers should fall back to the email itself when this is None,
    not treat it as an error."""
    email = email.strip().lower()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT display_name FROM user_profiles WHERE email = %s", (email,))
            row = cursor.fetchone()
    return row["display_name"] if row and row["display_name"] else None


def set_display_name(email: str, display_name: Optional[str]) -> None:
    """A blank/None display_name is a real, valid choice (clearing a
    previously-set name back to "just use my email"), not an error."""
    email = email.strip().lower()
    cleaned = display_name.strip() if display_name and display_name.strip() else None
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO user_profiles (email, display_name) VALUES (%s, %s)
                ON CONFLICT (email) DO UPDATE SET display_name = EXCLUDED.display_name
                """,
                (email, cleaned),
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
