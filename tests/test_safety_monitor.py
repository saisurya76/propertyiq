"""The safety monitor: while launch mode is ON, admin actions that would open
new subscriptions or take anything from a subscriber are refused, drift is
repaired, and switching OFF is never blocked."""
import copy
import os

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app, run_safety_check, get_safety_events  # noqa: E402
from backend.config_store import (  # noqa: E402
    DEFAULT_TIER_CONFIG, get_all_tiers_merged, get_free_features, get_tier_config,
    set_app_setting, set_free_features, set_tier_config,
)
from backend.subscription_store import upsert_subscription  # noqa: E402

client = TestClient(app)
PW = "test-admin-pw"


def _reset():
    from backend.db import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM subscriptions")
        conn.commit()
    set_tier_config(copy.deepcopy(DEFAULT_TIER_CONFIG))
    set_free_features([])
    set_app_setting("launch_mode_snapshot", "")
    set_app_setting("safety_monitor_log", "")
    set_app_setting("homepage_panel_visibility", "")
    set_app_setting("ni_section_visibility", "")


setup_function = teardown_function = _reset


def _on():
    assert client.post("/api/admin/launch-mode", json={"password": PW, "enabled": True}).status_code == 200


def _save_tiers(cfg):
    return client.post("/api/admin/tiers", json={"password": PW, "tier_config": cfg})


def _settings(**kw):
    return client.post("/api/admin/settings", json={"password": PW, **kw})


def _merged_copy():
    return copy.deepcopy(get_all_tiers_merged())


def test_nothing_is_guarded_while_off():
    cfg = _merged_copy()
    cfg["studio_pro"]["features"] = ["vastu_compliance"]
    assert _save_tiers(cfg).status_code == 200
    assert _settings(free_features=[]).status_code == 200


def test_reopening_a_studio_tier_is_refused_and_nothing_saved():
    _on()
    cfg = _merged_copy()
    cfg["studio_starter"]["coming_soon"] = False
    r = _save_tiers(cfg)
    assert r.status_code == 409 and "safety monitor" in r.json()["detail"]
    assert get_all_tiers_merged()["studio_starter"]["coming_soon"] is True


def test_stale_admin_screen_save_is_refused():
    """A tab loaded before the switch still holds coming_soon=False."""
    stale = _merged_copy()
    _on()
    assert _save_tiers(stale).status_code == 409


def test_unrelated_edit_while_on_is_allowed():
    _on()
    cfg = _merged_copy()
    cfg["studio_pro"]["price_usd"] = 31
    cfg["insight_addon"]["price_usd"] = 5
    assert _save_tiers(cfg).status_code == 200


def test_quick_analysis_cannot_be_made_unsellable():
    _on()
    for change in ({"coming_soon": True}, {"mode": "free"}):
        cfg = _merged_copy()
        cfg["insight_addon"].update(change)
        assert _save_tiers(cfg).status_code == 409


def test_subscribers_features_and_quotas_cannot_be_reduced():
    upsert_subscription(email="sm1@example.com", tier_id="studio_pro", status="active", dodo_subscription_id="sub_sm1")
    _on()
    cfg = _merged_copy()
    cfg["studio_pro"]["features"] = [f for f in cfg["studio_pro"]["features"] if f != "price_trends"]
    assert _save_tiers(cfg).status_code == 409
    cfg = _merged_copy()
    cfg["studio_pro"]["design_quota_per_month"] = 1
    assert _save_tiers(cfg).status_code == 409
    cfg = _merged_copy()
    cfg["studio_pro"]["max_price_watches"] = 99  # an increase is fine
    assert _save_tiers(cfg).status_code == 200


def test_unlimited_to_a_number_counts_as_a_reduction():
    upsert_subscription(email="sm2@example.com", tier_id="studio_unlimited", status="active", dodo_subscription_id="sub_sm2")
    _on()
    cfg = _merged_copy()
    cfg["studio_unlimited"]["max_agent_clients"] = 50
    assert _save_tiers(cfg).status_code == 409


def test_tier_without_subscribers_may_be_edited_while_on():
    upsert_subscription(email="sm3@example.com", tier_id="studio_pro", status="active", dodo_subscription_id="sub_sm3")
    _on()
    cfg = _merged_copy()
    cfg["studio_starter"]["features"] = ["vastu_compliance"]
    assert _save_tiers(cfg).status_code == 200


def test_free_assessment_cannot_be_turned_off_while_on():
    _on()
    assert _settings(free_features=[]).status_code == 409
    assert "property_assessment" in get_free_features()
    assert _settings(free_features=["property_assessment", "vastu_compliance"]).status_code == 200


def test_hiding_a_panel_subscribers_use_is_refused_only_when_someone_holds_it():
    _on()
    # nobody subscribed yet: hiding is harmless
    assert _settings(homepage_panel_visibility={"price_drop_alert": False}).status_code == 200
    _reset()
    upsert_subscription(email="sm4@example.com", tier_id="studio_starter", status="active", dodo_subscription_id="sub_sm4")
    _on()
    assert _settings(homepage_panel_visibility={"price_drop_alert": False}).status_code == 409
    assert _settings(ni_section_visibility={"emi_calculator": False}).status_code == 409
    assert _settings(ni_section_visibility={"map": False}).status_code == 200
    assert _settings(homepage_panel_visibility={"hidden_deal": False}).status_code == 200


def test_switching_off_is_never_blocked_and_restores_previous_state():
    cfg = copy.deepcopy(DEFAULT_TIER_CONFIG)
    cfg["studio_pro"]["coming_soon"] = True  # admin had paused this one already
    set_tier_config(cfg)
    set_free_features(["vastu_compliance"])
    _on()
    assert client.post("/api/admin/launch-mode", json={"password": PW, "enabled": False}).status_code == 200
    tiers = get_all_tiers_merged()
    assert tiers["studio_pro"]["coming_soon"] is True
    assert tiers["studio_starter"]["coming_soon"] is False
    assert get_free_features() == ["vastu_compliance"]


def test_cannot_switch_on_when_nothing_would_be_for_sale():
    cfg = copy.deepcopy(DEFAULT_TIER_CONFIG)
    cfg["insight_addon"]["coming_soon"] = True
    set_tier_config(cfg)
    r = client.post("/api/admin/launch-mode", json={"password": PW, "enabled": True})
    assert r.status_code == 409
    assert client.get("/api/launch-mode").json() == {"active": False}


def test_drift_check_relocks_and_reopens_and_logs():
    _on()
    persisted = get_tier_config()
    persisted["studio_pro"]["coming_soon"] = False  # simulate a direct DB edit
    set_tier_config(persisted)
    set_free_features([])
    assert run_safety_check() == []
    assert get_all_tiers_merged()["studio_pro"]["coming_soon"] is True
    assert "property_assessment" in get_free_features()
    kinds = [e["kind"] for e in get_safety_events()]
    assert kinds.count("repaired") == 2


def test_drift_check_does_nothing_when_off():
    persisted = copy.deepcopy(DEFAULT_TIER_CONFIG)
    set_tier_config(persisted)
    assert run_safety_check() == []
    assert get_all_tiers_merged()["studio_pro"]["coming_soon"] is False


def test_refusals_are_logged_and_visible_to_admin():
    _on()
    cfg = _merged_copy()
    cfg["studio_pro"]["coming_soon"] = False
    _save_tiers(cfg)
    ov = client.post("/api/admin/overview", json={"password": PW}).json()
    assert any(e["kind"] == "blocked" for e in ov["launch_mode"]["safety_events"])


def test_no_checkout_path_opens_a_studio_tier_while_on(monkeypatch):
    import backend.api as api
    monkeypatch.setattr(api, "PROPERTYIQ_BETA_BYPASS_PAYMENTS", True)
    _on()
    from backend.auth_store import create_otp
    code = create_otp("sm5@example.com")
    tok = client.post("/api/auth/verify-otp", json={"email": "sm5@example.com", "code": code}).json()["session_token"]
    for tier in ("studio_starter", "studio_pro", "studio_unlimited"):
        r = client.post("/api/subscribe/checkout", json={"tier_id": tier}, headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 403
