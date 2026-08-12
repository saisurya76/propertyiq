import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DEFAULT_DB_PATH = Path(os.getenv("PROPERTYIQ_PAYMENT_DB_PATH", "data/propertyiq_payments.db"))


def _connect() -> sqlite3.Connection:
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DEFAULT_DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_payment_store() -> None:
    with _connect() as connection:
        connection.execute(
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
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO report_orders (
                order_id, status, country, currency, terms_version,
                terms_accepted_at, property_payload, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    with _connect() as connection:
        connection.execute(
            """
            UPDATE report_orders
            SET dodo_checkout_session_id = ?, updated_at = ?
            WHERE order_id = ?
            """,
            (session_id, now, order_id),
        )
        connection.commit()


def get_order(order_id: str) -> Optional[dict[str, Any]]:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM report_orders WHERE order_id = ?",
            (order_id,),
        ).fetchone()

    if row is None:
        return None

    result = dict(row)
    result["property_payload"] = json.loads(result["property_payload"])
    return result
