import os

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

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


def _entitled_headers(email: str, tier_id: str = "studio_pro") -> dict:
    upsert_subscription(email=email, tier_id=tier_id, status="active", dodo_subscription_id=f"sub_{email}")
    return _authed_headers(email)


def test_property_ai_advisor_requires_authentication():
    r = client.get("/api/property-ai-advisor/access")
    assert r.status_code == 401


def test_property_ai_advisor_requires_an_entitled_subscription():
    headers = _authed_headers("aiadvisornosub@example.com")
    r = client.get("/api/property-ai-advisor/access", headers=headers)
    assert r.status_code == 403
    assert "url" not in r.json()  # the real destination is never leaked to a non-entitled caller


def test_property_ai_advisor_returns_the_real_url_when_entitled():
    headers = _entitled_headers("aiadvisorentitled@example.com")
    r = client.get("/api/property-ai-advisor/access", headers=headers)
    assert r.status_code == 200
    assert r.json()["url"] == "https://chatgpt.com/g/g-6a3d764cd690819180e776b79d816594-propertyiq-ai-advisor"


def test_property_ai_advisor_works_via_a_one_time_grant_too():
    """Confirms this new feature genuinely participates in the
    one-time-tier-grant system built earlier -- an admin checking this
    box under a one-time-purchase tier actually works, the whole point
    of that mechanism existing."""
    from backend.config_store import get_all_tiers_merged, set_tier_config
    from backend.insight_store import grant_one_time_tier

    email = "aiadvisoronetime@example.com"
    headers = _authed_headers(email)

    tiers = get_all_tiers_merged()
    if "property_ai_advisor" not in tiers["insight_addon"]["features"]:
        tiers["insight_addon"]["features"] = tiers["insight_addon"]["features"] + ["property_ai_advisor"]
        set_tier_config(tiers)

    r_before = client.get("/api/property-ai-advisor/access", headers=headers)
    assert r_before.status_code == 403

    grant_one_time_tier(email, "insight_addon")
    r_after = client.get("/api/property-ai-advisor/access", headers=headers)
    assert r_after.status_code == 200


def test_property_ai_advisor_is_in_homepage_panels_and_all_features():
    from backend.api import HOMEPAGE_PANELS
    from backend.config_store import ALL_FEATURES
    assert "property_ai_advisor" in HOMEPAGE_PANELS
    assert "property_ai_advisor" in ALL_FEATURES
