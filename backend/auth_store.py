import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from backend.db import get_connection

OTP_TTL_MINUTES = 10
SESSION_TTL_DAYS = 30


def initialize_auth_store() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    email TEXT PRIMARY KEY,
                    verified INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS country_code TEXT")
            cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS country_name TEXT")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS otp_codes (
                    id SERIAL PRIMARY KEY,
                    email TEXT NOT NULL,
                    code TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
        connection.commit()


def create_otp(email: str) -> str:
    email = email.strip().lower()
    code = f"{secrets.randbelow(1000000):06d}"
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=OTP_TTL_MINUTES)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE otp_codes SET used = 1 WHERE email = %s AND used = 0",
                (email,),
            )
            cursor.execute(
                "INSERT INTO otp_codes (email, code, expires_at, used, created_at) VALUES (%s, %s, %s, 0, %s)",
                (email, code, expires_at.isoformat(), now.isoformat()),
            )
        connection.commit()

    return code


def verify_otp(email: str, code: str, country_code: Optional[str] = None, country_name: Optional[str] = None) -> bool:
    email = email.strip().lower()
    now = datetime.now(timezone.utc)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, expires_at FROM otp_codes
                WHERE email = %s AND code = %s AND used = 0
                ORDER BY created_at DESC LIMIT 1
                """,
                (email, code),
            )
            row = cursor.fetchone()

            if row is None:
                return False

            expires_at = datetime.fromisoformat(row["expires_at"])
            if expires_at < now:
                return False

            cursor.execute("UPDATE otp_codes SET used = 1 WHERE id = %s", (row["id"],))

            # country_code/country_name come from the visitor's own
            # browser (the same real ipapi.co lookup the homepage
            # already runs for language/currency defaults — not a new
            # server-side geolocation call on this hot auth path).
            # Only overwrites a real, non-empty value -- a sign-in that
            # couldn't detect a country (blocked request, ipapi.co
            # down) never blanks out a country already on file for a
            # returning user.
            if country_code and country_name:
                cursor.execute(
                    "INSERT INTO users (email, verified, created_at, country_code, country_name) VALUES (%s, 1, %s, %s, %s) "
                    "ON CONFLICT (email) DO UPDATE SET verified = 1, country_code = EXCLUDED.country_code, country_name = EXCLUDED.country_name",
                    (email, now.isoformat(), country_code, country_name),
                )
            else:
                cursor.execute(
                    "INSERT INTO users (email, verified, created_at) VALUES (%s, 1, %s) "
                    "ON CONFLICT (email) DO UPDATE SET verified = 1",
                    (email, now.isoformat()),
                )
        connection.commit()

    return True



def get_users_by_country() -> list[dict[str, Any]]:
    """Real per-country, per-tier breakdown, joining the real
    country_code captured at sign-in (see verify_otp's own docstring
    for where this comes from) against this user's real, current
    subscription tier (if any) — genuinely empty for any user who
    signed in before location capture was added, or whose sign-in
    couldn't detect a country. Not a retroactive estimate; the admin
    map starts sparse and fills in as real, already-signed-in users
    sign in again, and new users sign up.

    A user with no active subscription (or none at all) is grouped
    under the real tier_id 'none' rather than dropped — the admin map
    should be able to show where free/unsubscribed users are too, not
    only paying ones."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT u.country_code, u.country_name,
                       COALESCE(s.tier_id, 'none') AS tier_id,
                       COUNT(*) AS user_count
                FROM users u
                LEFT JOIN subscriptions s ON s.email = u.email AND s.status = 'active'
                WHERE u.country_code IS NOT NULL
                GROUP BY u.country_code, u.country_name, COALESCE(s.tier_id, 'none')
                ORDER BY u.country_code, user_count DESC
                """
            )
            rows = cursor.fetchall()
    return [dict(row) for row in rows]


def create_session(email: str) -> str:
    email = email.strip().lower()
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=SESSION_TTL_DAYS)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO sessions (token, email, expires_at, created_at) VALUES (%s, %s, %s, %s)",
                (token, email, expires_at.isoformat(), now.isoformat()),
            )
        connection.commit()

    return token


def get_session_email(token: str) -> Optional[str]:
    if not token:
        return None

    now = datetime.now(timezone.utc)
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT email, expires_at FROM sessions WHERE token = %s",
                (token,),
            )
            row = cursor.fetchone()

    if row is None:
        return None

    if datetime.fromisoformat(row["expires_at"]) < now:
        return None

    return row["email"]
