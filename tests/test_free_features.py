import os

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app  # noqa: E402
from backend.auth_store import create_otp  # noqa: E402
from backend.config_store import (  # noqa: E402
    FREE_ELIGIBLE_FEATURES, get_free_features, set_free_features, user_has_feature,
)
from backend.subscription_store import upsert_subscription  # noqa: E402

client = TestClient(app)


def _set(features):
    return client.post("/api/admin/settings", json={"password": "test-admin-pw", "free_features": features})


def _headers(email):
    code = create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    return {"Authorization": f"Bearer {r.json()['session_token']}"}


def teardown_function():
    set_free_features([])


def test_default_is_no_free_features():
    assert get_free_features() == []
    assert user_has_feature("nobody-free@example.com", "property_assessment") is False


def test_free_feature_is_granted_to_any_signed_in_email():
    assert _set(["property_assessment"]).status_code == 200
    assert user_has_feature("freeuser@example.com", "property_assessment") is True
    # ...and ONLY that feature
    assert user_has_feature("freeuser@example.com", "cost_of_living") is False


def test_assess_endpoint_opens_up_for_a_user_with_no_plan():
    headers = _headers("freeassess@example.com")
    from tests.test_property_assessment_paywall import _valid_payload
    body = _valid_payload()
    before = client.post("/assess", headers=headers, json=body)
    assert before.status_code == 403  # gate closed by default
    _set(["property_assessment"])
    after = client.post("/assess", headers=headers, json=body)
    assert after.status_code == 200  # a real assessment comes back
    _set([])
    again = client.post("/assess", headers=headers, json=body)
    assert again.status_code == 403  # switching it off closes it again


def test_unknown_and_ineligible_names_are_never_stored():
    saved = set_free_features(["property_assessment", "agent_intelligence", "price_drop_alert", "made_up"])
    assert saved == ["property_assessment"]
    assert "agent_intelligence" not in FREE_ELIGIBLE_FEATURES
    assert "price_drop_alert" not in FREE_ELIGIBLE_FEATURES


def test_setting_requires_the_admin_password():
    r = client.post("/api/admin/settings", json={"password": "wrong", "free_features": ["property_assessment"]})
    assert r.status_code in (401, 403)
    assert get_free_features() == []


def test_overview_reports_the_list_and_the_eligible_set():
    _set(["emi_calculator"])
    r = client.post("/api/admin/overview", json={"password": "test-admin-pw"})
    data = r.json()
    assert data["free_features"] == ["emi_calculator"]
    assert "property_assessment" in data["free_eligible_features"]


def test_a_paying_subscriber_is_unaffected_by_the_free_list():
    email = "freepaying@example.com"
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_free_pay")
    _set(["property_assessment"])
    assert user_has_feature(email, "property_assessment") is True
    assert user_has_feature(email, "agent_intelligence") is True
    _set([])
    assert user_has_feature(email, "property_assessment") is True  # their plan still grants it
