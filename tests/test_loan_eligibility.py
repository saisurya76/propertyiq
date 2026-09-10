import os

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

import pytest  # noqa: E402
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


def _eligibility_payload(**overrides):
    payload = {
        "monthly_income": 100000, "existing_monthly_obligations": 0, "property_price": 9000000,
        "down_payment_available": 2000000, "age": 35, "credit_rating": "good",
        "annual_rate_percent": 8.5, "tenure_years": 20,
    }
    payload.update(overrides)
    return payload


def test_loan_eligibility_requires_authentication():
    r = client.post("/api/neighborhood-insights/loan-eligibility", json=_eligibility_payload())
    assert r.status_code == 401


def test_loan_eligibility_requires_subscription():
    headers = _authed_headers("loannosub@example.com")
    r = client.post("/api/neighborhood-insights/loan-eligibility", json=_eligibility_payload(), headers=headers)
    assert r.status_code == 403


def test_loan_eligibility_fails_when_foir_exceeds_max():
    """Direct proof of the real math: a loan whose EMI would exceed the
    configured FOIR threshold must be marked ineligible, with the real
    percentage shown, not just a bare fail."""
    headers = _entitled_headers("loanfoirfail@example.com")
    r = client.post("/api/neighborhood-insights/loan-eligibility", json=_eligibility_payload(), headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["is_eligible"] is False
    foir_check = next(c for c in data["checks"] if "FOIR" in c["name"])
    assert foir_check["pass"] is False
    assert "60.7%" in foir_check["detail"]


def test_loan_eligibility_passes_with_a_realistic_affordable_scenario():
    headers = _entitled_headers("loaneligible@example.com")
    payload = _eligibility_payload(monthly_income=300000, property_price=9000000, down_payment_available=2000000)
    r = client.post("/api/neighborhood-insights/loan-eligibility", json=payload, headers=headers)
    data = r.json()
    assert data["is_eligible"] is True
    assert all(c["pass"] for c in data["checks"])


def test_loan_eligibility_max_eligible_loan_amount_is_mathematically_real():
    """The reported max eligible loan, run back through the real EMI
    formula, must produce an EMI at exactly the FOIR ceiling -- proof
    this is a real inverse calculation, not an estimate."""
    from backend.loan_calculator import calculate_emi
    headers = _entitled_headers("loanmaxcheck@example.com")
    r = client.post("/api/neighborhood-insights/loan-eligibility", json=_eligibility_payload(), headers=headers)
    data = r.json()
    max_loan = data["max_eligible_loan_amount"]
    recomputed_emi = calculate_emi(max_loan, 8.5, 20)
    assert abs(recomputed_emi - 50000) < 1  # 50% FOIR of 100,000 income


def test_loan_eligibility_fails_on_ltv_when_down_payment_too_low():
    headers = _entitled_headers("loanltvfail@example.com")
    payload = _eligibility_payload(monthly_income=1000000, down_payment_available=500000)  # only ~5.5% down on a 9M property
    r = client.post("/api/neighborhood-insights/loan-eligibility", json=payload, headers=headers)
    data = r.json()
    ltv_check = next(c for c in data["checks"] if "LTV" in c["name"])
    assert ltv_check["pass"] is False


def test_loan_eligibility_fails_on_age_at_maturity():
    headers = _entitled_headers("loanagefail@example.com")
    payload = _eligibility_payload(monthly_income=1000000, age=55, tenure_years=20)  # 75 at payoff, exceeds default 65
    r = client.post("/api/neighborhood-insights/loan-eligibility", json=payload, headers=headers)
    data = r.json()
    age_check = next(c for c in data["checks"] if "Age" in c["name"])
    assert age_check["pass"] is False


def test_loan_eligibility_fails_on_credit_rating_below_minimum():
    headers = _entitled_headers("loancreditfail@example.com")
    payload = _eligibility_payload(monthly_income=1000000, credit_rating="poor")
    r = client.post("/api/neighborhood-insights/loan-eligibility", json=payload, headers=headers)
    data = r.json()
    credit_check = next(c for c in data["checks"] if "Credit" in c["name"])
    assert credit_check["pass"] is False


def test_loan_eligibility_rejects_an_invalid_credit_rating():
    headers = _entitled_headers("loaninvalidcredit@example.com")
    payload = _eligibility_payload(credit_rating="amazing")
    r = client.post("/api/neighborhood-insights/loan-eligibility", json=payload, headers=headers)
    assert r.status_code == 400


def test_public_loan_eligibility_settings_returns_real_defaults():
    r = client.get("/api/loan-eligibility/settings")
    assert r.status_code == 200
    data = r.json()
    assert data["max_foir_percent"] == 50.0
    assert data["max_ltv_percent"] == 80.0


def test_admin_can_update_loan_eligibility_settings():
    r = client.post("/api/admin/loan-eligibility-settings", json={"password": "test-admin-pw", "max_foir_percent": 45})
    assert r.status_code == 200
    assert r.json()["max_foir_percent"] == 45.0

    r2 = client.get("/api/loan-eligibility/settings")
    assert r2.json()["max_foir_percent"] == 45.0

    # restore default so this test doesn't leak into others
    client.post("/api/admin/loan-eligibility-settings", json={"password": "test-admin-pw", "max_foir_percent": 50})


def test_admin_settings_update_requires_real_password():
    r = client.post("/api/admin/loan-eligibility-settings", json={"password": "wrong", "max_foir_percent": 45})
    assert r.status_code == 403


def test_admin_settings_rejects_an_unrealistic_foir():
    r = client.post("/api/admin/loan-eligibility-settings", json={"password": "test-admin-pw", "max_foir_percent": 150})
    assert r.status_code == 400


def test_admin_settings_partial_update_does_not_reset_other_thresholds():
    client.post("/api/admin/loan-eligibility-settings", json={"password": "test-admin-pw", "max_ltv_percent": 75})
    r = client.post("/api/admin/loan-eligibility-settings", json={"password": "test-admin-pw", "max_age_at_maturity": 70})
    assert r.json()["max_ltv_percent"] == 75.0
    assert r.json()["max_age_at_maturity"] == 70

    # restore defaults
    client.post("/api/admin/loan-eligibility-settings", json={
        "password": "test-admin-pw", "max_ltv_percent": 80, "max_age_at_maturity": 65,
    })


def test_feature_is_gated_correctly_for_a_tier_without_it(monkeypatch):
    import backend.api as api_module
    monkeypatch.setattr(api_module, "user_has_feature", lambda user_email, feature: False)
    headers = _entitled_headers("loangatedoff@example.com")
    r = client.post("/api/neighborhood-insights/loan-eligibility", json=_eligibility_payload(), headers=headers)
    assert r.status_code == 403
