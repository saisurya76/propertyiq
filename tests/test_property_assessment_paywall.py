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


def _valid_payload():
    return {
        "country": "India", "stateProvince": "Telangana", "city": "Hyderabad", "location": "Tellapur",
        "propertyType": "Apartment", "propertyName": "Aparna Sarovar Zenith", "developerName": "Aparna",
        "quotedPrice": 18000000, "governmentGuidance": 6500, "marketAverage": 10125, "unitArea": 1800,
        "monthlyRent": 45000, "areaUnit": "sqft",
    }


def test_assess_requires_authentication():
    """The real, direct proof this is now a paid, tier-gated feature:
    no session at all is rejected, not silently treated as public --
    confirmed this endpoint was completely open before this change."""
    r = client.post("/assess", json=_valid_payload())
    assert r.status_code == 401


def test_assess_rejects_a_signed_in_visitor_with_no_subscription():
    headers = _authed_headers("noassesssub@example.com")
    r = client.post("/assess", json=_valid_payload(), headers=headers)
    assert r.status_code == 403
    assert "property assessment" in r.json()["detail"]


def test_assess_rejects_a_tier_without_the_feature_enabled(monkeypatch):
    """A real, subscribed customer whose specific tier has had this
    feature disabled by an admin must still be rejected."""
    import backend.config_store as config_module
    email = "assessdisabled@example.com"
    headers = _entitled_headers(email, tier_id="studio_starter")

    tiers = config_module.get_all_tiers_merged()
    tiers["studio_starter"]["features"] = [f for f in tiers["studio_starter"]["features"] if f != "property_assessment"]
    monkeypatch.setattr(config_module, "get_tier_config", lambda: tiers)

    r = client.post("/assess", json=_valid_payload(), headers=headers)
    assert r.status_code == 403


def test_assess_succeeds_for_a_genuinely_entitled_subscriber():
    """The real, direct proof the gate is scoped correctly -- an
    entitled subscriber gets the actual, full assessment result, not
    just a bare 200."""
    headers = _entitled_headers("assessworks@example.com")
    r = client.post("/assess", json=_valid_payload(), headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "score" in data
    assert "rating" in data


def test_emi_calculator_requires_authentication():
    r = client.post("/api/neighborhood-insights/emi-calculator", json={"principal": 1000000, "annual_rate_percent": 10, "tenure_years": 10})
    assert r.status_code == 401


def test_emi_calculator_rejects_a_signed_in_visitor_with_no_subscription():
    headers = _authed_headers("noemisub@example.com")
    r = client.post("/api/neighborhood-insights/emi-calculator", json={"principal": 1000000, "annual_rate_percent": 10, "tenure_years": 10}, headers=headers)
    assert r.status_code == 403
    assert "EMI calculator" in r.json()["detail"]


def test_emi_calculator_succeeds_for_an_entitled_subscriber_with_the_real_reference_value():
    headers = _entitled_headers("emiworks@example.com")
    r = client.post("/api/neighborhood-insights/emi-calculator", json={"principal": 1000000, "annual_rate_percent": 10, "tenure_years": 10}, headers=headers)
    assert r.status_code == 200
    assert r.json()["emi"] == 13215.07


def test_amortization_schedule_gated_independently_from_emi_calculator():
    """Direct proof the two panels are genuinely gated separately, per
    the explicit business decision -- an entitled EMI-calculator user
    without amortization_projector must still be rejected here."""
    email = "emionly@example.com"
    headers = _entitled_headers(email, tier_id="studio_starter")

    import backend.config_store as config_module
    tiers = config_module.get_all_tiers_merged()
    tiers["studio_starter"]["features"] = [f for f in tiers["studio_starter"]["features"] if f != "amortization_projector"]
    import unittest.mock as mock
    with mock.patch.object(config_module, "get_tier_config", lambda: tiers):
        r = client.post("/api/neighborhood-insights/amortization-schedule", json={"principal": 1000000, "annual_rate_percent": 10, "tenure_years": 10}, headers=headers)
    assert r.status_code == 403

    r2 = client.post("/api/neighborhood-insights/emi-calculator", json={"principal": 1000000, "annual_rate_percent": 10, "tenure_years": 10}, headers=headers)
    assert r2.status_code == 200


def test_amortization_schedule_returns_the_full_real_schedule():
    headers = _entitled_headers("amortworks@example.com")
    r = client.post("/api/neighborhood-insights/amortization-schedule", json={"principal": 1000000, "annual_rate_percent": 10, "tenure_years": 10}, headers=headers)
    assert r.status_code == 200
    schedule = r.json()["schedule"]
    assert len(schedule) == 120
    assert schedule[-1]["remaining_balance"] == 0.0


def test_amortization_export_returns_a_real_csv():
    headers = _entitled_headers("csvexport@example.com")
    r = client.get(
        "/api/neighborhood-insights/amortization-schedule/export",
        params={"principal": 1000000, "annual_rate_percent": 10, "tenure_years": 10},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    lines = r.text.strip().split("\r\n")
    assert lines[0] == "month,payment,principal_component,interest_component,remaining_balance"
    assert len(lines) == 121  # header + 120 months


def test_amortization_export_requires_authentication():
    r = client.get(
        "/api/neighborhood-insights/amortization-schedule/export",
        params={"principal": 1000000, "annual_rate_percent": 10, "tenure_years": 10},
    )
    assert r.status_code == 401


def test_emi_calculator_rejects_invalid_input_with_a_400_not_a_500():
    headers = _entitled_headers("invalidinput@example.com")
    r = client.post("/api/neighborhood-insights/emi-calculator", json={"principal": -5, "annual_rate_percent": 10, "tenure_years": 10}, headers=headers)
    assert r.status_code == 400
