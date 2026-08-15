import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = Path(os.getenv("PROPERTYIQ_INSIGHT_DB_PATH", "data/propertyiq_insight.db"))


def _connect() -> sqlite3.Connection:
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DEFAULT_DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_insight_store() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS insight_grants (
                report_id TEXT NOT NULL,
                user_email TEXT NOT NULL,
                granted_at TEXT NOT NULL,
                PRIMARY KEY (report_id, user_email)
            )
            """
        )
        connection.commit()


def grant_insight_access(report_id: str, user_email: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        connection.execute(
            "INSERT INTO insight_grants (report_id, user_email, granted_at) VALUES (?, ?, ?) "
            "ON CONFLICT(report_id, user_email) DO NOTHING",
            (report_id, user_email.strip().lower(), now),
        )
        connection.commit()


def has_insight_access(report_id: str, user_email: str) -> bool:
    with _connect() as connection:
        row = connection.execute(
            "SELECT 1 FROM insight_grants WHERE report_id = ? AND user_email = ?",
            (report_id, user_email.strip().lower()),
        ).fetchone()
    return row is not None


def list_all_grants() -> list[dict]:
    """For the admin overview panel — all Insight Add-on grants, most
    recent first."""
    with _connect() as connection:
        rows = connection.execute(
            "SELECT * FROM insight_grants ORDER BY granted_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]
