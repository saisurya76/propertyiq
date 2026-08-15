import os

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")
# Test isolation now comes from tests/conftest.py truncating the shared
# Postgres database at session start (DATABASE_URL) — no more per-run
# SQLite file paths.

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app  # noqa: E402
from backend.auth_store import create_otp  # noqa: E402
from backend.subscription_store import upsert_subscription  # noqa: E402

client = TestClient(app)


def _authed_headers(email: str) -> dict:
    code = create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    token = r.json()["session_token"]
    return {"Authorization": f"Bearer {token}"}


def test_otp_wrong_code_rejected():
    email = "wrongcode@example.com"
    create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": "000000"})
    assert r.status_code == 401


def test_otp_correct_code_returns_session_token():
    email = "correctcode@example.com"
    code = create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    assert r.status_code == 200
    assert "session_token" in r.json()


def test_design_endpoint_requires_auth():
    r = client.post("/api/construction-studio/design", json={
        "plot_size_sqft": 1000, "plot_length_ft": 40, "plot_width_ft": 25,
        "selections": {}, "entrance_direction": "north", "road_facing_side": "north",
    })
    assert r.status_code == 401


def test_design_endpoint_requires_active_subscription():
    headers = _authed_headers("nosub@example.com")
    r = client.post("/api/construction-studio/design", headers=headers, json={
        "plot_size_sqft": 1000, "plot_length_ft": 40, "plot_width_ft": 25,
        "selections": {}, "entrance_direction": "north", "road_facing_side": "north",
    })
    assert r.status_code == 403


def test_quota_enforced_at_exact_boundary():
    email = "quotatest@example.com"
    headers = _authed_headers(email)
    upsert_subscription(email=email, tier_id="studio_starter", status="active", dodo_subscription_id="sub_x")

    payload = {
        "plot_size_sqft": 1000, "plot_length_ft": 40, "plot_width_ft": 25,
        "selections": {}, "entrance_direction": "north", "road_facing_side": "north",
    }

    for _ in range(3):  # studio_starter default quota
        r = client.post("/api/construction-studio/design", headers=headers, json=payload)
        assert r.status_code == 200

    r = client.post("/api/construction-studio/design", headers=headers, json=payload)
    assert r.status_code == 403


def test_unlimited_tier_has_no_quota_block():
    email = "unlimited@example.com"
    headers = _authed_headers(email)
    upsert_subscription(email=email, tier_id="studio_unlimited", status="active", dodo_subscription_id="sub_y")

    payload = {
        "plot_size_sqft": 1000, "plot_length_ft": 40, "plot_width_ft": 25,
        "selections": {}, "entrance_direction": "north", "road_facing_side": "north",
    }

    for _ in range(6):  # well beyond studio_starter's quota, should never block
        r = client.post("/api/construction-studio/design", headers=headers, json=payload)
        assert r.status_code == 200


def test_admin_tier_update_wrong_password_rejected():
    r = client.post("/api/admin/tiers", json={"password": "wrong", "tier_config": {}})
    assert r.status_code == 403


def test_admin_tier_update_correct_password_persists():
    from backend.config_store import DEFAULT_TIER_CONFIG

    new_config = {"studio_starter": {
        "label": "Studio Starter", "billing": "subscription", "price_usd": 99,
        "features": [], "design_quota_per_month": 1,
    }}
    r = client.post("/api/admin/tiers", json={"password": "test-admin-pw", "tier_config": new_config})
    assert r.status_code == 200

    r = client.get("/api/tiers")
    assert r.json()["studio_starter"]["price_usd"] == 99

    # Restore full defaults so later tests in this module (and any that
    # reference other tiers, e.g. studio_pro) aren't left with a config
    # this test intentionally truncated to a single tier.
    r = client.post("/api/admin/tiers", json={"password": "test-admin-pw", "tier_config": DEFAULT_TIER_CONFIG})
    assert r.status_code == 200


def test_webhook_rejects_unsigned_payload():
    r = client.post("/api/webhooks/dodo", json={
        "type": "subscription.active",
        "data": {"metadata": {"tier_id": "studio_pro", "user_email": "attacker@example.com"}},
    })
    assert r.status_code == 401


def test_subscribe_status_requires_auth():
    r = client.get("/api/subscribe/status")
    assert r.status_code == 401


def test_subscribe_status_reflects_active_tier():
    email = "statuscheck@example.com"
    headers = _authed_headers(email)
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_z")

    r = client.get("/api/subscribe/status", headers=headers)
    assert r.status_code == 200
    assert r.json()["tier_id"] == "studio_pro"


def test_beta_bypass_off_by_default():
    """Regression guard: without PROPERTYIQ_BETA_BYPASS_PAYMENTS=true, real
    Dodo checkout path must still run (fails cleanly with 503 here since no
    product ID is configured in tests — the point is it does NOT silently
    grant access)."""
    headers = _authed_headers("nobypass@example.com")
    r = client.post("/api/subscribe/checkout", headers=headers, json={"tier_id": "studio_starter"})
    assert r.status_code == 503
    r = client.get("/api/subscribe/status", headers=headers)
    assert r.json()["tier_id"] is None


def test_beta_bypass_when_enabled(monkeypatch):
    import backend.api as api_module
    monkeypatch.setattr(api_module, "PROPERTYIQ_BETA_BYPASS_PAYMENTS", True)

    headers = _authed_headers("bypassuser@example.com")
    r = client.post("/api/subscribe/checkout", headers=headers, json={"tier_id": "studio_pro"})
    assert r.status_code == 200
    assert r.json()["beta_bypass"] is True
    assert r.json()["status"] == "active"

    r = client.get("/api/subscribe/status", headers=headers)
    assert r.json()["tier_id"] == "studio_pro"

    # feature actually usable end-to-end
    r = client.post("/api/construction-studio/design", headers=headers, json={
        "plot_size_sqft": 1000, "plot_length_ft": 40, "plot_width_ft": 25,
        "selections": {}, "entrance_direction": "north", "road_facing_side": "north",
    })
    assert r.status_code == 200


def test_beta_bypass_insight_addon(monkeypatch):
    import backend.api as api_module
    monkeypatch.setattr(api_module, "PROPERTYIQ_BETA_BYPASS_PAYMENTS", True)

    headers = _authed_headers("bypassinsight@example.com")
    r = client.post("/api/insight/checkout", headers=headers, json={"report_id": "rep_test"})
    assert r.status_code == 200
    assert r.json()["beta_bypass"] is True


def test_admin_overview_requires_correct_password():
    r = client.post("/api/admin/overview", json={"password": "wrong"})
    assert r.status_code == 403


def test_admin_overview_returns_subscriptions_and_grants(monkeypatch):
    import backend.api as api_module
    monkeypatch.setattr(api_module, "PROPERTYIQ_BETA_BYPASS_PAYMENTS", True)

    headers = _authed_headers("adminoverviewsub@example.com")
    client.post("/api/subscribe/checkout", headers=headers, json={"tier_id": "studio_starter"})

    r = client.post("/api/admin/overview", json={"password": "test-admin-pw"})
    assert r.status_code == 200
    data = r.json()
    assert "tier_config" in data
    assert any(s["email"] == "adminoverviewsub@example.com" for s in data["subscriptions"])
