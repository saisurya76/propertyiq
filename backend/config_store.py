import json
from typing import Any, Optional

from backend.db import get_connection

# Base prices in USD, converted at checkout time the same way construction
# estimates are (see backend/construction_studio.py fx_rates_usd_base).
DEFAULT_TIER_CONFIG = {
    "insight_addon": {
        "label": "Insight Add-on",
        "billing": "one_time",
        "price_usd": 4,
        "features": ["similar_property_suggestions"],
        "design_quota_per_month": 0,
        "saved_designs_limit": 0,
        # "paid" (default, current behavior): similar-property suggestions
        # require a purchase or an active subscription that includes the
        # feature — the panel itself stays hidden until unlocked, not
        # just its data. "free": suggestions are available to everyone
        # with no purchase at all, and the buy button disappears since
        # there's nothing to buy. A real, admin-toggleable product
        # decision, not a per-tier feature flag, since it's an either/or
        # switch for the whole product rather than something that
        # differs by subscription tier.
        "mode": "paid",
    },
    "studio_starter": {
        "label": "Studio Starter",
        "billing": "subscription",
        "price_usd": 9,
        "features": [
            "similar_property_suggestions",
            "vastu_compliance",
            "standard_suppliers",
            "property_url_import",
            "price_drop_alert",
            "area_comparison",
            "property_assessment",
        ],
        "design_quota_per_month": 3,
        "saved_designs_limit": 2,
        "max_price_watches": 2,
    },
    "studio_pro": {
        "label": "Studio Pro",
        "billing": "subscription",
        "price_usd": 29,
        "features": [
            "similar_property_suggestions",
            "vastu_compliance",
            "premium_global_suppliers",
            "property_url_import",
            "price_drop_alert",
            "area_comparison",
            "property_assessment",
        ],
        "design_quota_per_month": 15,
        "saved_designs_limit": 10,
        "max_price_watches": 10,
    },
    "studio_unlimited": {
        "label": "Studio Unlimited",
        "billing": "subscription",
        "price_usd": 79,
        "features": [
            "similar_property_suggestions",
            "vastu_compliance",
            "premium_global_suppliers",
            "priority_cad_formats",
            "team_seats",
            "property_url_import",
            "price_drop_alert",
            "area_comparison",
            "property_assessment",
        ],
        "design_quota_per_month": None,  # None = unlimited
        "saved_designs_limit": None,  # None = unlimited
        "max_price_watches": None,  # None = unlimited
    },
}

_CONFIG_KEY = "tier_config"


def initialize_config_store() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
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
        return

    # A real, one-time cleanup for every deployment already past first
    # run, not just fresh ones: "construction_studio_lite" was listed on
    # every Studio tier's pricing-page bullet list and admin toggle for
    # a real stretch of time, but nothing anywhere ever actually checked
    # it via has_feature() — an already-live database's stored config
    # still has this dead entry baked in, and DEFAULT_TIER_CONFIG above
    # only applies to a database that's never been seeded at all. Runs
    # on every startup, but is a genuine no-op once cleaned (removing an
    # already-absent string from a list changes nothing), so it's safe
    # to leave here permanently rather than needing its own one-off
    # migration script.
    changed = False
    for tier in existing.values():
        features = tier.get("features")
        if isinstance(features, list) and "construction_studio_lite" in features:
            tier["features"] = [f for f in features if f != "construction_studio_lite"]
            changed = True
    if changed:
        set_tier_config(existing)


def get_tier_config() -> dict[str, Any] | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT value FROM app_config WHERE key = %s", (_CONFIG_KEY,))
            row = cursor.fetchone()

    if row is None:
        return None

    return json.loads(row["value"])


def set_tier_config(config: dict[str, Any]) -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO app_config (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                (_CONFIG_KEY, json.dumps(config, separators=(",", ":"))),
            )
        connection.commit()


# Generic app-wide settings (not tied to tiers/pricing) reusing the same
# app_config key-value table — currently backs the admin-configurable
# Gemini API key for the property_url_import feature's LLM fallback, but
# is intentionally generic so future global settings don't each need
# their own table.
def get_app_setting(key: str) -> Optional[str]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT value FROM app_config WHERE key = %s", (key,))
            row = cursor.fetchone()
    return row["value"] if row else None


def set_app_setting(key: str, value: str) -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO app_config (key, value) VALUES (%s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
        connection.commit()


def get_tier(tier_id: str) -> dict[str, Any] | None:
    """Merges the persisted (possibly stale) tier config over the current
    code's DEFAULT_TIER_CONFIG, field by field, per tier — NOT a raw
    passthrough of whatever's in the database.

    This matters because config_store deliberately never overwrites an
    admin's existing saved config (see initialize_config_store's comment) —
    so if a NEW field gets added to DEFAULT_TIER_CONFIG after production
    already has a saved tier_config row, that field is simply missing from
    the persisted data forever, with no migration. A caller doing
    tier["new_field"] on that stale data throws a real KeyError -> 500 —
    confirmed as the actual root cause of a "Failed to fetch"/CORS-blocked
    report that was really an unhandled server exception dropping CORS
    headers on its error response, not a network or CORS problem at all.
    Merging defaults underneath the persisted values keeps admin edits to
    EXISTING fields intact while safely filling in anything newer."""

    persisted = get_tier_config()
    default_tier = DEFAULT_TIER_CONFIG.get(tier_id)

    if persisted is None:
        return default_tier

    persisted_tier = persisted.get(tier_id)
    if persisted_tier is None:
        return default_tier
    if default_tier is None:
        return persisted_tier

    return {**default_tier, **persisted_tier}


def get_all_tiers_merged() -> dict[str, Any]:
    """Same merge as get_tier(), but for every tier at once — used by the
    pricing page and admin panel so neither ever displays or relies on a
    field silently missing from stale persisted config."""
    persisted = get_tier_config() or {}
    return {
        tier_id: {**default_tier, **persisted.get(tier_id, {})}
        for tier_id, default_tier in DEFAULT_TIER_CONFIG.items()
    }


# The canonical set of every feature flag the system knows how to
# actually enforce — used by the admin panel to render a checkbox for
# EVERY feature against EVERY tier, not just whatever happens to already
# be in that tier's features list. A feature only belongs here once
# something in the code genuinely checks for it via has_feature() below;
# a feature string that exists only as pricing-page copy with nothing
# behind it doesn't belong in this list, since toggling it in the admin
# panel would do nothing.
ALL_FEATURES = [
    "similar_property_suggestions",
    "vastu_compliance",
    "standard_suppliers",
    "premium_global_suppliers",
    "priority_cad_formats",
    "team_seats",
    "property_url_import",
    "price_drop_alert",
    "area_comparison",
    "property_assessment",
]


def has_feature(tier_id: str | None, feature: str) -> bool:
    """The one place feature-gating logic lives — every endpoint that
    gates on a tier's feature list should call this, not read
    tier["features"] directly, so admin-toggled changes take effect
    everywhere consistently and immediately (no separate code path to
    keep in sync). Returns False for no tier / an unknown tier / a
    tier whose features list doesn't include it — never raises."""
    if not tier_id:
        return False
    tier = get_tier(tier_id)
    if not tier:
        return False
    return feature in tier.get("features", [])
