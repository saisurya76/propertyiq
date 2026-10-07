import copy
import json
import os

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from unittest.mock import patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app, get_homepage_panel_visibility, HOMEPAGE_VISIBILITY_SETTING_KEY  # noqa: E402
from backend.config_store import (  # noqa: E402
    DEFAULT_TIER_CONFIG, get_all_tiers_merged, get_free_features, set_free_features,
    set_tier_config, set_app_setting, get_app_setting, get_tier_config,
)

client = TestClient(app)
STRIPS = ["construction_studio", "agent_intelligence", "property_ai_advisor"]
STUDIO = ["studio_starter", "studio_pro", "studio_unlimited"]


def _mode(enabled, pw="test-admin-pw"):
    return client.post("/api/admin/launch-mode", json={"password": pw, "enabled": enabled})


def _reset():
    set_tier_config(copy.deepcopy(DEFAULT_TIER_CONFIG))
    set_free_features([])
    set_app_setting(HOMEPAGE_VISIBILITY_SETTING_KEY, json.dumps({}))
    set_app_setting("launch_mode_snapshot", "")


def setup_function():
    _reset()


def teardown_function():
    _reset()


def test_requires_admin_password():
    assert _mode(True, pw="wrong").status_code in (401, 403)
    assert get_free_features() == []


def test_on_applies_everything():
    r = _mode(True)
    assert r.status_code == 200 and r.json()["active"] is True
    tiers = get_all_tiers_merged()
    assert all(tiers[t]["coming_soon"] is True for t in STUDIO)
    assert tiers["insight_addon"]["coming_soon"] is False  # the one thing for sale
    assert "property_assessment" in get_free_features()
    # the admin's own show/hide settings are never touched by the mode
    panels = get_homepage_panel_visibility()
    assert all(panels[k] is True for k in STRIPS)
    assert client.get("/api/launch-mode").json() == {"active": True}


def test_off_undoes_exactly_what_on_did():
    # a deliberately mixed starting state
    cfg = copy.deepcopy(DEFAULT_TIER_CONFIG)
    cfg["studio_pro"]["coming_soon"] = True          # already coming soon before
    set_tier_config(cfg)
    set_free_features(["emi_calculator"])             # already free before
    set_app_setting(HOMEPAGE_VISIBILITY_SETTING_KEY, json.dumps({"agent_intelligence": False}))  # already hidden

    _mode(True)
    assert "emi_calculator" in get_free_features() and "property_assessment" in get_free_features()

    r = _mode(False)
    assert r.json()["active"] is False
    tiers = get_all_tiers_merged()
    assert tiers["studio_starter"]["coming_soon"] is False
    assert tiers["studio_pro"]["coming_soon"] is True     # stays as it was
    assert tiers["studio_unlimited"]["coming_soon"] is False
    assert get_free_features() == ["emi_calculator"]       # assessment gone, emi kept
    panels = get_homepage_panel_visibility()
    assert panels["agent_intelligence"] is False            # the admin's own hide is untouched
    assert panels["construction_studio"] is True
    assert client.get("/api/launch-mode").json() == {"active": False}


def test_a_feature_that_was_already_free_stays_free_after_off():
    set_free_features(["property_assessment"])
    _mode(True)
    _mode(False)
    assert get_free_features() == ["property_assessment"]


def test_turning_on_twice_keeps_the_original_snapshot():
    _mode(True)
    _mode(True)  # must NOT snapshot the already-modified state
    _mode(False)
    assert all(get_all_tiers_merged()[t]["coming_soon"] is False for t in STUDIO)
    assert get_free_features() == []


def test_turning_off_when_off_changes_nothing():
    set_free_features(["emi_calculator"])
    r = _mode(False)
    assert r.json()["active"] is False
    assert get_free_features() == ["emi_calculator"]


def test_other_changes_made_while_on_survive_the_undo():
    _mode(True)
    # while the mode is on the admin hides a panel, edits a label and frees another feature
    panels = get_homepage_panel_visibility()
    panels["hidden_deal"] = False
    set_app_setting(HOMEPAGE_VISIBILITY_SETTING_KEY, json.dumps(panels))
    cfg = get_tier_config()
    cfg["studio_pro"]["label"] = "Pro Plus"
    set_tier_config(cfg)
    set_free_features(get_free_features() + ["cost_of_living"])

    _mode(False)
    assert get_homepage_panel_visibility()["hidden_deal"] is False
    assert get_all_tiers_merged()["studio_pro"]["label"] == "Pro Plus"
    assert get_free_features() == ["cost_of_living"]  # only the mode's own addition was removed


def test_overview_reports_status_and_warns_when_quick_analysis_cannot_sell():
    with patch("backend.api.TIER_DODO_PRODUCT_IDS", {"insight_addon": ""}):
        data = client.post("/api/admin/overview", json={"password": "test-admin-pw"}).json()
    assert data["launch_mode"]["active"] is False
    assert any("DODO_PRODUCT_ID_INSIGHT_ADDON" in w for w in data["launch_mode"]["warnings"])

    cfg = get_tier_config()
    cfg["insight_addon"]["coming_soon"] = True
    set_tier_config(cfg)
    with patch("backend.api.TIER_DODO_PRODUCT_IDS", {"insight_addon": "pdt_x"}):
        data = client.post("/api/admin/overview", json={"password": "test-admin-pw"}).json()
    assert any("Coming soon" in w for w in data["launch_mode"]["warnings"])


def test_active_subscribers_keep_access_while_on():
    from backend.subscription_store import upsert_subscription
    from backend.config_store import user_has_feature
    upsert_subscription(email="lm_sub@example.com", tier_id="studio_pro", status="active", dodo_subscription_id="sub_lm")
    _mode(True)
    assert user_has_feature("lm_sub@example.com", "agent_intelligence") is True
    assert user_has_feature("anyone@example.com", "property_assessment") is True
    assert user_has_feature("anyone@example.com", "agent_intelligence") is False


def test_public_endpoints_reflect_the_mode_both_ways():
    _mode(True)
    assert client.get("/api/launch-mode").json() == {"active": True}
    tiers = client.get("/api/tiers").json()
    assert all(tiers[t]["coming_soon"] is True for t in STUDIO)
    assert tiers["insight_addon"]["coming_soon"] is False
    _mode(False)
    assert client.get("/api/launch-mode").json() == {"active": False}
    tiers = client.get("/api/tiers").json()
    assert all(tiers[t]["coming_soon"] is False for t in STUDIO)
