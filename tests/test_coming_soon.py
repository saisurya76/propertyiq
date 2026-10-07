import copy
import os

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from unittest.mock import MagicMock, patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app  # noqa: E402
from backend.auth_store import create_otp  # noqa: E402
from backend.config_store import DEFAULT_TIER_CONFIG, get_all_tiers_merged, set_tier_config, get_tier_config  # noqa: E402
from backend.subscription_store import upsert_subscription, get_subscription  # noqa: E402

client = TestClient(app)


def _headers(email):
    code = create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    return {"Authorization": f"Bearer {r.json()['session_token']}"}


def _save(config):
    return client.post("/api/admin/tiers", json={"password": "test-admin-pw", "tier_config": config})


def _restore():
    set_tier_config(copy.deepcopy(DEFAULT_TIER_CONFIG))


def test_every_default_tier_is_purchasable():
    for tier_id, tier in DEFAULT_TIER_CONFIG.items():
        assert tier["coming_soon"] is False, tier_id


def test_stale_persisted_config_without_the_field_reads_as_not_coming_soon():
    stale = copy.deepcopy(DEFAULT_TIER_CONFIG)
    for tier in stale.values():
        tier.pop("coming_soon", None)
    set_tier_config(stale)
    try:
        merged = get_all_tiers_merged()
        assert all(t["coming_soon"] is False for t in merged.values())
    finally:
        _restore()


def test_subscription_checkout_rejected_when_coming_soon():
    cfg = copy.deepcopy(DEFAULT_TIER_CONFIG)
    cfg["studio_pro"]["coming_soon"] = True
    assert _save(cfg).status_code == 200
    try:
        headers = _headers("comingsoon_sub@example.com")
        with patch("backend.api.PROPERTYIQ_BETA_BYPASS_PAYMENTS", False), \
             patch("backend.api.TIER_DODO_PRODUCT_IDS", {"studio_pro": "prod_x"}), \
             patch("backend.api.get_dodo_client") as dodo:
            r = client.post("/api/subscribe/checkout", headers=headers, json={"tier_id": "studio_pro"})
        assert r.status_code == 403
        assert "coming soon" in r.json()["detail"].lower()
        dodo.return_value.checkout_sessions.create.assert_not_called()
        assert get_subscription("comingsoon_sub@example.com") is None
    finally:
        _restore()


def test_coming_soon_also_blocks_the_beta_bypass():
    cfg = copy.deepcopy(DEFAULT_TIER_CONFIG)
    cfg["studio_starter"]["coming_soon"] = True
    assert _save(cfg).status_code == 200
    try:
        headers = _headers("comingsoon_bypass@example.com")
        with patch("backend.api.PROPERTYIQ_BETA_BYPASS_PAYMENTS", True):
            r = client.post("/api/subscribe/checkout", headers=headers, json={"tier_id": "studio_starter"})
        assert r.status_code == 403
        assert get_subscription("comingsoon_bypass@example.com") is None
    finally:
        _restore()


def test_other_tiers_still_purchasable_when_one_is_coming_soon():
    cfg = copy.deepcopy(DEFAULT_TIER_CONFIG)
    cfg["studio_pro"]["coming_soon"] = True
    assert _save(cfg).status_code == 200
    try:
        headers = _headers("comingsoon_other@example.com")
        fake = MagicMock()
        fake.checkout_url = "https://checkout.dodopayments.com/fake"
        fake.id = "cs_other"
        with patch("backend.api.PROPERTYIQ_BETA_BYPASS_PAYMENTS", False), \
             patch("backend.api.TIER_DODO_PRODUCT_IDS", {"studio_starter": "prod_s"}), \
             patch("backend.api.get_dodo_client") as dodo:
            dodo.return_value.checkout_sessions.create.return_value = fake
            r = client.post("/api/subscribe/checkout", headers=headers, json={"tier_id": "studio_starter"})
        assert r.status_code == 200
    finally:
        _restore()


def test_insight_checkout_rejected_when_coming_soon():
    cfg = copy.deepcopy(DEFAULT_TIER_CONFIG)
    cfg["insight_addon"]["coming_soon"] = True
    assert _save(cfg).status_code == 200
    try:
        headers = _headers("comingsoon_insight@example.com")
        with patch("backend.api.PROPERTYIQ_BETA_BYPASS_PAYMENTS", True):
            r = client.post("/api/insight/checkout", headers=headers, json={"report_id": "rep_cs_1"})
        assert r.status_code == 403
        assert "coming soon" in r.json()["detail"].lower()
    finally:
        _restore()


def test_existing_active_subscriber_keeps_access_when_tier_goes_coming_soon():
    email = "comingsoon_keeps@example.com"
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_cs_keep")
    cfg = copy.deepcopy(DEFAULT_TIER_CONFIG)
    cfg["studio_pro"]["coming_soon"] = True
    assert _save(cfg).status_code == 200
    try:
        assert get_subscription(email)["status"] == "active"
        from backend.config_store import user_has_feature
        assert user_has_feature(email, "agent_intelligence") is True
    finally:
        _restore()


def test_public_tiers_endpoint_exposes_the_flag():
    cfg = copy.deepcopy(DEFAULT_TIER_CONFIG)
    cfg["studio_unlimited"]["coming_soon"] = True
    assert _save(cfg).status_code == 200
    try:
        tiers = client.get("/api/tiers").json()
        assert tiers["studio_unlimited"]["coming_soon"] is True
        assert tiers["studio_starter"]["coming_soon"] is False
    finally:
        _restore()


def test_admin_save_coerces_coming_soon_to_a_real_boolean():
    cfg = copy.deepcopy(DEFAULT_TIER_CONFIG)
    cfg["studio_pro"]["coming_soon"] = "false"  # a truthy string must NOT lock the tier
    cfg["studio_starter"]["coming_soon"] = True
    assert _save(cfg).status_code == 200
    try:
        saved = get_tier_config()
        assert saved["studio_pro"]["coming_soon"] is False
        assert saved["studio_starter"]["coming_soon"] is True
    finally:
        _restore()
