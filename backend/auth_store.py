import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

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


def verify_otp(email: str, code: str) -> bool:
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

            cursor.execute(
                "INSERT INTO users (email, verified, created_at) VALUES (%s, 1, %s) "
                "ON CONFLICT (email) DO UPDATE SET verified = 1",
                (email, now.isoformat()),
            )
        connection.commit()

    return True


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
