from datetime import datetime, timezone

from backend.db import get_connection


def initialize_insight_store() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS insight_grants (
                    report_id TEXT NOT NULL,
                    user_email TEXT NOT NULL,
                    granted_at TEXT NOT NULL,
                    PRIMARY KEY (report_id, user_email)
                )
                """
            )
            # A real, deliberate, SEPARATE mechanism from the
            # `subscriptions` table above -- not a variant of it. A
            # one-time purchase (e.g. Insight Add-on) grants permanent,
            # account-wide access to whatever features that tier's own
            # config lists, WITHOUT ever writing to `subscriptions`.
            # This is the actual safety property: there is no code
            # path by which buying a one-time tier can touch, overwrite,
            # or downgrade an existing paying subscriber's real active
            # subscription row, because this table is never read by
            # anything that writes to `subscriptions`, and nothing that
            # reads `subscriptions` writes here.
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS one_time_tier_grants (
                    user_email TEXT NOT NULL,
                    tier_id TEXT NOT NULL,
                    granted_at TEXT NOT NULL,
                    PRIMARY KEY (user_email, tier_id)
                )
                """
            )
        connection.commit()


def grant_one_time_tier(user_email: str, tier_id: str) -> None:
    """Permanent — there is no expiry, revocation, or renewal concept
    for a one-time purchase; once granted, it stays granted. Real,
    deliberate idempotency (ON CONFLICT DO NOTHING): re-granting the
    same tier to the same email (e.g. a duplicate webhook delivery,
    which Dodo's own docs say can genuinely happen) is a safe no-op,
    not a second grant or an error."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO one_time_tier_grants (user_email, tier_id, granted_at) VALUES (%s, %s, %s) "
                "ON CONFLICT (user_email, tier_id) DO NOTHING",
                (user_email.strip().lower(), tier_id, now),
            )
        connection.commit()


def get_one_time_tier_grants(user_email: str) -> list[str]:
    """Every tier_id this email has ever permanently unlocked via a
    one-time purchase — real, current, directly queried, not cached or
    inferred."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tier_id FROM one_time_tier_grants WHERE user_email = %s",
                (user_email.strip().lower(),),
            )
            rows = cursor.fetchall()
    return [row["tier_id"] for row in rows]


def grant_insight_access(report_id: str, user_email: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO insight_grants (report_id, user_email, granted_at) VALUES (%s, %s, %s) "
                "ON CONFLICT (report_id, user_email) DO NOTHING",
                (report_id, user_email.strip().lower(), now),
            )
        connection.commit()


def has_insight_access(report_id: str, user_email: str) -> bool:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM insight_grants WHERE report_id = %s AND user_email = %s",
                (report_id, user_email.strip().lower()),
            )
            row = cursor.fetchone()
    return row is not None


def list_all_grants() -> list[dict]:
    """For the admin overview panel — all Insight Add-on grants, most
    recent first."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM insight_grants ORDER BY granted_at DESC")
            rows = cursor.fetchall()
    return [dict(row) for row in rows]
