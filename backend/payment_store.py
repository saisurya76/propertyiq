import json
from datetime import datetime, timezone
from typing import Any, Optional

from backend.db import get_connection


def initialize_payment_store() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS report_orders (
                    order_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    country TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    terms_version TEXT NOT NULL,
                    terms_accepted_at TEXT NOT NULL,
                    property_payload TEXT NOT NULL,
                    dodo_checkout_session_id TEXT,
                    dodo_payment_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        connection.commit()


def create_order(
    *,
    order_id: str,
    property_payload: dict[str, Any],
    terms_version: str,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO report_orders (
                    order_id, status, country, currency, terms_version,
                    terms_accepted_at, property_payload, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    order_id,
                    "pending_payment",
                    property_payload.get("country", ""),
                    "INR",
                    terms_version,
                    now,
                    json.dumps(property_payload, separators=(",", ":")),
                    now,
                    now,
                ),
            )
        connection.commit()


def attach_checkout_session(order_id: str, session_id: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE report_orders
                SET dodo_checkout_session_id = %s, updated_at = %s
                WHERE order_id = %s
                """,
                (session_id, now, order_id),
            )
        connection.commit()


def get_order(order_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM report_orders WHERE order_id = %s",
                (order_id,),
            )
            row = cursor.fetchone()

    if row is None:
        return None

    result = dict(row)
    result["property_payload"] = json.loads(result["property_payload"])
    return result
