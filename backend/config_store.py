import json
import os
import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(os.getenv("PROPERTYIQ_CONFIG_DB_PATH", "data/propertyiq_config.db"))

# Base prices in USD, converted at checkout time the same way construction
# estimates are (see backend/construction_studio.py fx_rates_usd_base).
DEFAULT_TIER_CONFIG = {
    "insight_addon": {
        "label": "Insight Add-on",
        "billing": "one_time",
        "price_usd": 4,
        "features": ["similar_property_suggestions"],
        "design_quota_per_month": 0,
    },
    "studio_starter": {
        "label": "Studio Starter",
        "billing": "subscription",
        "price_usd": 9,
        "features": [
            "similar_property_suggestions",
            "construction_studio_lite",
            "vastu_compliance",
            "standard_suppliers",
        ],
        "design_quota_per_month": 3,
    },
    "studio_pro": {
        "label": "Studio Pro",
        "billing": "subscription",
        "price_usd": 29,
        "features": [
            "similar_property_suggestions",
            "construction_studio_lite",
            "vastu_compliance",
            "premium_global_suppliers",
        ],
        "design_quota_per_month": 15,
    },
    "studio_unlimited": {
        "label": "Studio Unlimited",
        "billing": "subscription",
        "price_usd": 79,
        "features": [
            "similar_property_suggestions",
            "construction_studio_lite",
            "vastu_compliance",
            "premium_global_suppliers",
            "priority_cad_formats",
            "team_seats",
        ],
        "design_quota_per_month": None,  # None = unlimited
    },
}

_CONFIG_KEY = "tier_config"


def _connect() -> sqlite3.Connection:
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DEFAULT_DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_config_store() -> None:
    with _connect() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.commit()

    # Seed defaults on first run only — never overwrite an admin's existing config
    existing = get_tier_config()
    if existing is None:
        set_tier_config(DEFAULT_TIER_CONFIG)


def get_tier_config() -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT value FROM app_config WHERE key = ?", (_CONFIG_KEY,)
        ).fetchone()

    if row is None:
        return None

    return json.loads(row["value"])


def set_tier_config(config: dict[str, Any]) -> None:
    with _connect() as connection:
        connection.execute(
            "INSERT INTO app_config (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (_CONFIG_KEY, json.dumps(config, separators=(",", ":"))),
        )
        connection.commit()


def get_tier(tier_id: str) -> dict[str, Any] | None:
    config = get_tier_config() or DEFAULT_TIER_CONFIG
    return config.get(tier_id)