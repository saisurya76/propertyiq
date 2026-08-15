import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DEFAULT_DB_PATH = Path(os.getenv("PROPERTYIQ_CONSTRUCTION_DB_PATH", "data/propertyiq_construction.db"))


def _connect() -> sqlite3.Connection:
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DEFAULT_DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_construction_store() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS construction_designs (
                design_id TEXT PRIMARY KEY,
                user_email TEXT NOT NULL,
                region TEXT NOT NULL,
                currency TEXT NOT NULL,
                plot_spec TEXT NOT NULL,
                selections TEXT NOT NULL,
                cost_estimate TEXT NOT NULL,
                vastu_result TEXT,
                risks TEXT,
                dxf_path TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.commit()


def save_design(
    *,
    design_id: str,
    user_email: str,
    region: str,
    currency: str,
    plot_spec: dict[str, Any],
    selections: dict[str, str],
    cost_estimate: dict[str, Any],
    vastu_result: Optional[dict[str, Any]] = None,
    risks: Optional[list[str]] = None,
    dxf_path: Optional[str] = None,
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO construction_designs (
                design_id, user_email, region, currency, plot_spec, selections,
                cost_estimate, vastu_result, risks, dxf_path, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                design_id,
                user_email,
                region,
                currency,
                json.dumps(plot_spec, separators=(",", ":")),
                json.dumps(selections, separators=(",", ":")),
                json.dumps(cost_estimate, separators=(",", ":")),
                json.dumps(vastu_result, separators=(",", ":")) if vastu_result else None,
                json.dumps(risks, separators=(",", ":")) if risks else None,
                dxf_path,
                now,
                now,
            ),
        )
        connection.commit()


def get_design(design_id: str) -> Optional[dict[str, Any]]:
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM construction_designs WHERE design_id = ?",
            (design_id,),
        ).fetchone()

    if row is None:
        return None

    result = dict(row)
    result["plot_spec"] = json.loads(result["plot_spec"])
    result["selections"] = json.loads(result["selections"])
    result["cost_estimate"] = json.loads(result["cost_estimate"])
    result["vastu_result"] = json.loads(result["vastu_result"]) if result["vastu_result"] else None
    result["risks"] = json.loads(result["risks"]) if result["risks"] else None
    return result


def count_designs_this_month(user_email: str) -> int:
    """Used later by tier-quota enforcement (Phase: tier/subscription infra).
    Counts designs created in the current calendar month for a user."""
    now = datetime.now(timezone.utc)
    month_prefix = now.strftime("%Y-%m")
    with _connect() as connection:
        row = connection.execute(
            "SELECT COUNT(*) as cnt FROM construction_designs WHERE user_email = ? AND created_at LIKE ?",
            (user_email, f"{month_prefix}%"),
        ).fetchone()
    return row["cnt"] if row else 0
