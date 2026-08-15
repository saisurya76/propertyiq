import os
import uuid

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("PROPERTYIQ_ADMIN_PASSWORD", "test-admin-pw")

# Use isolated per-test-run DB files so this suite never collides with dev data
_run_id = uuid.uuid4().hex[:8]
os.environ["PROPERTYIQ_AUTH_DB_PATH"] = f"data/test_auth_{_run_id}.db"
os.environ["PROPERTYIQ_CONFIG_DB_PATH"] = f"data/test_config_{_run_id}.db"
os.environ["PROPERTYIQ_SUBSCRIPTION_DB_PATH"] = f"data/test_subscription_{_run_id}.db"
os.environ["PROPERTYIQ_CONSTRUCTION_DB_PATH"] = f"data/test_construction_{_run_id}.db"
os.environ["PROPERTYIQ_PAYMENT_DB_PATH"] = f"data/test_payment_{_run_id}.db"

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
    new_config = {"studio_starter": {
        "label": "Studio Starter", "billing": "subscription", "price_usd": 99,
        "features": [], "design_quota_per_month": 1,
    }}
    r = client.post("/api/admin/tiers", json={"password": "test-admin-pw", "tier_config": new_config})
    assert r.status_code == 200

    r = client.get("/api/tiers")
    assert r.json()["studio_starter"]["price_usd"] == 99


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
