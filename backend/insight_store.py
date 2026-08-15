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
        connection.commit()


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
