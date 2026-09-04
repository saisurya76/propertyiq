import os

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from backend.config_store import (  # noqa: E402
    DEFAULT_TIER_CONFIG,
    ALL_FEATURES,
    initialize_config_store,
    get_tier_config,
    set_tier_config,
)


def test_construction_studio_lite_is_genuinely_gone_from_every_default_tier():
    """The real bug this fixes: this feature string was listed on every
    Studio tier's pricing-page bullet list and admin toggle, but nothing
    anywhere ever actually checked it via has_feature() -- a dead label
    presented to paying customers as if it were a real benefit."""
    for tier_id, tier in DEFAULT_TIER_CONFIG.items():
        assert "construction_studio_lite" not in tier.get("features", []), (
            f"{tier_id} still lists the dead construction_studio_lite feature"
        )


def test_construction_studio_lite_is_gone_from_the_admin_toggle_list():
    assert "construction_studio_lite" not in ALL_FEATURES


def test_every_remaining_feature_in_all_features_is_a_real_one_confirmed_by_hand():
    """A direct, explicit confirmation of the exact set verified by
    reading the real gating code for each: similar_property_suggestions
    (report-access checks), vastu_compliance (compliance-check gate),
    standard_suppliers/premium_global_suppliers (materials catalog
    region), priority_cad_formats (DXF dimension annotations),
    team_seats (property-sharing endpoint), property_url_import and
    price_drop_alert (their own respective feature gates), area_comparison
    (Neighborhood Insights compare/refresh/monitor-on endpoints),
    property_assessment (the main /assess endpoint)."""
    assert set(ALL_FEATURES) == {
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
    }


def test_migration_strips_the_dead_feature_from_an_already_seeded_database():
    """The real, practical concern this covers: DEFAULT_TIER_CONFIG only
    seeds a database that has NEVER had a tier config at all --
    initialize_config_store's own existing "seed on first run only"
    rule means fixing the code default alone does nothing for a
    database that was already seeded with the old, dead feature
    included. Confirms the separate cleanup step actually strips it
    from an existing, already-stored config on the next startup."""
    stale_config = {
        "insight_addon": {"label": "Insight Add-on", "billing": "one_time", "price_usd": 4, "features": ["similar_property_suggestions"]},
        "studio_starter": {"label": "Studio Starter", "billing": "subscription", "price_usd": 9, "features": ["similar_property_suggestions", "construction_studio_lite", "vastu_compliance"]},
        "studio_pro": {"label": "Studio Pro", "billing": "subscription", "price_usd": 29, "features": ["construction_studio_lite", "premium_global_suppliers"]},
    }
    set_tier_config(stale_config)

    initialize_config_store()

    cleaned = get_tier_config()
    for tier_id, tier in cleaned.items():
        assert "construction_studio_lite" not in tier.get("features", []), (
            f"{tier_id} still has the dead feature after migration"
        )
    # Confirms the migration only removed the dead entry -- every real
    # feature already on the stale config survives untouched.
    assert "similar_property_suggestions" in cleaned["studio_starter"]["features"]
    assert "vastu_compliance" in cleaned["studio_starter"]["features"]
    assert "premium_global_suppliers" in cleaned["studio_pro"]["features"]


def test_migration_is_a_genuine_no_op_when_theres_nothing_to_clean():
    """Confirms the migration doesn't corrupt or needlessly rewrite a
    config that's already clean -- it must be safe to run on every
    single startup indefinitely, not just once."""
    clean_config = {
        "studio_starter": {"label": "Studio Starter", "billing": "subscription", "price_usd": 9, "features": ["vastu_compliance", "standard_suppliers"]},
    }
    set_tier_config(clean_config)

    initialize_config_store()

    assert get_tier_config() == clean_config
