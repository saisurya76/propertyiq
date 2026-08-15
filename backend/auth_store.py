import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

DEFAULT_DB_PATH = Path(os.getenv("PROPERTYIQ_AUTH_DB_PATH", "data/propertyiq_auth.db"))

OTP_TTL_MINUTES = 10
SESSION_TTL_DAYS = 30


def _connect() -> sqlite3.Connection:
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DEFAULT_DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_auth_store() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                verified INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS otp_codes (
                email TEXT NOT NULL,
                code TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
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

    with _connect() as connection:
        # Invalidate any prior unused codes for this email first
        connection.execute(
            "UPDATE otp_codes SET used = 1 WHERE email = ? AND used = 0",
            (email,),
        )
        connection.execute(
            "INSERT INTO otp_codes (email, code, expires_at, used, created_at) VALUES (?, ?, ?, 0, ?)",
            (email, code, expires_at.isoformat(), now.isoformat()),
        )
        connection.commit()

    return code


def verify_otp(email: str, code: str) -> bool:
    email = email.strip().lower()
    now = datetime.now(timezone.utc)

    with _connect() as connection:
        row = connection.execute(
            """
            SELECT rowid, expires_at FROM otp_codes
            WHERE email = ? AND code = ? AND used = 0
            ORDER BY created_at DESC LIMIT 1
            """,
            (email, code),
        ).fetchone()

        if row is None:
            return False

        expires_at = datetime.fromisoformat(row["expires_at"])
        if expires_at < now:
            return False

        connection.execute("UPDATE otp_codes SET used = 1 WHERE rowid = ?", (row["rowid"],))

        connection.execute(
            "INSERT INTO users (email, verified, created_at) VALUES (?, 1, ?) "
            "ON CONFLICT(email) DO UPDATE SET verified = 1",
            (email, now.isoformat()),
        )
        connection.commit()

    return True


def create_session(email: str) -> str:
    email = email.strip().lower()
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=SESSION_TTL_DAYS)

    with _connect() as connection:
        connection.execute(
            "INSERT INTO sessions (token, email, expires_at, created_at) VALUES (?, ?, ?, ?)",
            (token, email, expires_at.isoformat(), now.isoformat()),
        )
        connection.commit()

    return token


def get_session_email(token: str) -> Optional[str]:
    if not token:
        return None

    now = datetime.now(timezone.utc)
    with _connect() as connection:
        row = connection.execute(
            "SELECT email, expires_at FROM sessions WHERE token = ?",
            (token,),
        ).fetchone()

    if row is None:
        return None

    if datetime.fromisoformat(row["expires_at"]) < now:
        return None

    return row["email"]
