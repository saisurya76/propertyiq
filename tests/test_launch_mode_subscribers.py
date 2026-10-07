"""The launch-mode switch stops NEW subscriptions and nothing else. These
tests pin the other half of that promise: a person who already has a plan
keeps every feature, every limit, and every renewal while it is on."""
import os
import uuid

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from unittest.mock import MagicMock, patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app  # noqa: E402
from backend.auth_store import create_otp  # noqa: E402
from backend.config_store import (  # noqa: E402
    ALL_FEATURES, DEFAULT_TIER_CONFIG, get_tier, set_free_features, set_tier_config,
    set_app_setting, user_has_feature,
)
from backend.subscription_store import get_active_tier, get_subscription, upsert_subscription  # noqa: E402
import copy  # noqa: E402

client = TestClient(app)


def _mode(enabled):
    return client.post("/api/admin/launch-mode", json={"password": "test-admin-pw", "enabled": enabled})


def _reset():
    set_tier_config(copy.deepcopy(DEFAULT_TIER_CONFIG))
    set_free_features([])
    set_app_setting("launch_mode_snapshot", "")


def setup_function():
    _reset()


def teardown_function():
    _reset()


def _headers(email):
    code = create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    return {"Authorization": f"Bearer {r.json()['session_token']}"}


def _webhook(event_type, attrs):
    data = MagicMock()
    for k, v in attrs.items():
        setattr(data, k, v)
    event = MagicMock()
    event.type = event_type
    event.data = data
    wc = MagicMock()
    wc.webhooks.unwrap.return_value = event
    with patch("backend.api.get_dodo_webhook_client", return_value=wc), patch("backend.api.send_email"), \
         patch("backend.api.get_dodo_product_price", return_value=None):
        return client.post(
            "/api/webhooks/dodo", content=b"{}",
            headers={"webhook-id": f"wh_{uuid.uuid4().hex}", "webhook-signature": "s", "webhook-timestamp": "0"},
        )


def test_every_feature_and_limit_of_an_active_subscriber_is_identical_on_and_off():
    email = "lms_features@example.com"
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_lms_f")

    def snapshot():
        return (
            {f: user_has_feature(email, f) for f in ALL_FEATURES},
            get_active_tier(email),
            {k: v for k, v in get_tier("studio_pro").items() if k != "coming_soon"},
        )

    before = snapshot()
    _mode(True)
    during = snapshot()
    _mode(False)
    after = snapshot()
    assert before == during == after


def test_subscriber_status_endpoint_keeps_their_plan_and_lists_their_features():
    email = "lms_status@example.com"
    upsert_subscription(email=email, tier_id="studio_starter", status="active", dodo_subscription_id="sub_lms_s")
    headers = _headers(email)
    _mode(True)
    st = client.get("/api/subscribe/status", headers=headers).json()
    assert st["tier_id"] == "studio_starter" and st["status"] == "active"
    assert "agent_intelligence" in st["features"] and "property_ai_advisor" in st["features"]


def test_a_non_subscriber_sees_no_studio_features_in_status_but_the_free_assessment():
    headers = _headers("lms_visitor@example.com")
    _mode(True)
    st = client.get("/api/subscribe/status", headers=headers).json()
    assert st["tier_id"] is None
    assert "property_assessment" in st["features"]
    assert "agent_intelligence" not in st["features"] and "property_ai_advisor" not in st["features"]


def test_renewal_and_updates_still_flow_while_the_tier_is_coming_soon():
    email = "lms_renew@example.com"
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_lms_r")
    _mode(True)

    renewed = _webhook("subscription.renewed", {
        "subscription_id": "sub_lms_r", "payment_id": "pay_lms_r",
        "metadata": {"tier_id": "studio_pro", "user_email": email}, "amount": None, "currency": None, "customer": None,
        "status": "active",
    })
    assert renewed.status_code == 200
    assert get_subscription(email)["status"] == "active"
    assert get_subscription(email)["tier_id"] == "studio_pro"

    updated = _webhook("subscription.updated", {
        "subscription_id": "sub_lms_r", "payment_id": None,
        "metadata": {"tier_id": "studio_pro", "user_email": email}, "amount": None, "currency": None, "customer": None,
        "status": "active",
    })
    assert updated.status_code == 200 and get_subscription(email)["status"] == "active"


def test_cancellation_and_payment_failure_still_apply_while_on():
    email = "lms_cancel@example.com"
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_lms_c")
    _mode(True)
    r = _webhook("subscription.cancelled", {
        "subscription_id": "sub_lms_c", "payment_id": None, "metadata": {}, "amount": None, "currency": None, "customer": None,
    })
    assert r.status_code == 200
    assert get_subscription(email)["status"] == "cancelled"


def test_a_checkout_already_in_flight_still_activates_when_it_is_paid():
    """Someone who started paying just before the switch went on and
    completes the payment must still get what they paid for."""
    email = "lms_inflight@example.com"
    _mode(True)
    r = _webhook("subscription.active", {
        "subscription_id": "sub_lms_if", "payment_id": "pay_lms_if",
        "metadata": {"tier_id": "studio_starter", "user_email": email}, "amount": None, "currency": None, "customer": None,
    })
    assert r.status_code == 200
    assert get_subscription(email)["status"] == "active"


def test_a_subscribers_own_data_rows_are_untouched_by_on_and_off():
    email = "lms_data@example.com"
    upsert_subscription(email=email, tier_id="studio_unlimited", status="active", dodo_subscription_id="sub_lms_d")
    before = get_subscription(email)
    _mode(True)
    _mode(False)
    assert get_subscription(email) == before
