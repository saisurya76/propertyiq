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
from backend.insight_store import grant_insight_access  # noqa: E402
from backend.similar_properties import get_similar_properties  # noqa: E402

client = TestClient(app)


def _authed_headers(email: str) -> dict:
    code = create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    return {"Authorization": f"Bearer {r.json()['session_token']}"}


def test_get_similar_properties_supported_region_ranks_by_closeness():
    result = get_similar_properties(city="Hyderabad", property_type="Apartment", subject_price_per_sqft=10000)
    assert result["coverage"] == "supported"
    assert len(result["suggestions"]) > 0
    # closest by absolute price/sqft distance should come first
    diffs = [abs(s["price_diff_percent"]) for s in result["suggestions"]]
    assert diffs == sorted(diffs)


def test_get_similar_properties_unsupported_region_is_honest_not_empty_fake():
    result = get_similar_properties(city="Austin", property_type="Apartment", subject_price_per_sqft=10000)
    assert result["coverage"] == "unsupported"
    assert result["suggestions"] == []


def test_similar_properties_endpoint_requires_access():
    headers = _authed_headers("noaccess@example.com")
    r = client.get("/api/similar-properties/rep_noaccess", headers=headers,
                    params={"city": "Hyderabad", "property_type": "Apartment"})
    assert r.status_code == 403


def test_insight_purchase_grants_access_to_that_report_only(monkeypatch):
    import backend.api as api_module
    monkeypatch.setattr(api_module, "PROPERTYIQ_BETA_BYPASS_PAYMENTS", True)

    email = "insightbuyer@example.com"
    headers = _authed_headers(email)

    r = client.post("/api/insight/checkout", headers=headers, json={"report_id": "rep_A"})
    assert r.status_code == 200
    assert r.json()["beta_bypass"] is True

    r = client.get("/api/similar-properties/rep_A", headers=headers,
                    params={"city": "Hyderabad", "property_type": "Apartment", "subject_price_per_sqft": 10000})
    assert r.status_code == 200

    # a DIFFERENT report was never purchased by this user — must still be blocked
    r = client.get("/api/similar-properties/rep_B", headers=headers,
                    params={"city": "Hyderabad", "property_type": "Apartment"})
    assert r.status_code == 403


def test_active_subscription_grants_access_without_insight_purchase():
    email = "subscriber@example.com"
    headers = _authed_headers(email)
    upsert_subscription(email=email, tier_id="studio_starter", status="active", dodo_subscription_id="sub_sp1")

    r = client.get("/api/similar-properties/any_report_never_purchased", headers=headers,
                    params={"city": "Hyderabad", "property_type": "Apartment", "subject_price_per_sqft": 9500})
    assert r.status_code == 200


def test_insight_grant_is_per_user_not_global():
    buyer_headers = _authed_headers("realbuyer@example.com")
    other_headers = _authed_headers("freeloader@example.com")

    grant_insight_access("rep_shared", "realbuyer@example.com")

    r = client.get("/api/similar-properties/rep_shared", headers=buyer_headers,
                    params={"city": "Hyderabad", "property_type": "Apartment"})
    assert r.status_code == 200

    r = client.get("/api/similar-properties/rep_shared", headers=other_headers,
                    params={"city": "Hyderabad", "property_type": "Apartment"})
    assert r.status_code == 403
