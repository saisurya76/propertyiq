"""What happens when someone who cancelled subscribes again, straight away or
after the period ends. The rules: never bill them twice for the same time,
never move them off a plan they paid for, never promise something launch mode
does not allow."""
import copy
import os
import uuid

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from unittest.mock import MagicMock, patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app  # noqa: E402
from backend.auth_store import create_otp  # noqa: E402
from backend.config_store import DEFAULT_TIER_CONFIG, set_app_setting, set_free_features, set_tier_config  # noqa: E402
from backend.subscription_store import get_subscription, set_cancellation, upsert_subscription  # noqa: E402

client = TestClient(app)


def _reset():
    set_tier_config(copy.deepcopy(DEFAULT_TIER_CONFIG))
    set_free_features([])
    set_app_setting("launch_mode_snapshot", "")
    set_app_setting("wind_down_state", "")


setup_function = teardown_function = _reset


def _headers(email):
    code = create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    return {"Authorization": f"Bearer {r.json()['session_token']}"}


def _webhook(event_type, attrs, live=None):
    """live: what Dodo says about the event's own subscription when we look it up."""
    data = MagicMock()
    for k, v in attrs.items():
        setattr(data, k, v)
    event = MagicMock(); event.type = event_type; event.data = data
    wc = MagicMock()
    wc.webhooks.unwrap.return_value = event
    if live is not None:
        wc.subscriptions.retrieve.return_value = live
    with patch("backend.api.get_dodo_webhook_client", return_value=wc), patch("backend.api.send_email"), \
         patch("backend.api.get_dodo_product_price", return_value=None), \
         patch("backend.api.DODO_API_KEY", "fake_key"), patch("backend.api.DodoPayments") as dodo:
        r = client.post("/api/webhooks/dodo", content=b"{}", headers={
            "webhook-id": f"wh_{uuid.uuid4().hex}", "webhook-signature": "s", "webhook-timestamp": "0"})
    return r, dodo


def _sub_attrs(email, tier, sub_id, status="active"):
    return {"subscription_id": sub_id, "status": status,
            "metadata": {"tier_id": tier, "user_email": email}, "customer": MagicMock(email=email)}


# ---- straight away: still active, renewal switched off ---------------------

def test_cannot_buy_the_plan_you_still_hold_while_it_is_set_to_end():
    email = "rs_now@example.com"
    h = _headers(email)
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_rs_now")
    set_cancellation(email, True, "12 November 2026")
    with patch("backend.api.get_dodo_client") as dodo:
        r = client.post("/api/subscribe/checkout", headers=h, json={"tier_id": "studio_pro"})
    assert r.status_code == 409
    assert "12 November 2026" in r.json()["detail"] and "Keep my plan" in r.json()["detail"]
    dodo.return_value.checkout_sessions.create.assert_not_called()  # no second charge possible
    assert get_subscription(email)["status"] == "active"


def test_cannot_buy_the_plan_you_are_already_renewing():
    email = "rs_same@example.com"
    h = _headers(email)
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_rs_same")
    with patch("backend.api.get_dodo_client") as dodo:
        r = client.post("/api/subscribe/checkout", headers=h, json={"tier_id": "studio_pro"})
    assert r.status_code == 409
    dodo.return_value.checkout_sessions.create.assert_not_called()


def test_keep_my_plan_undoes_the_cancellation_without_a_new_charge():
    email = "rs_keep@example.com"
    h = _headers(email)
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_rs_keep")
    set_cancellation(email, True, "12 November 2026")
    sent = []
    with patch("backend.api.DODO_API_KEY", "fake_key"), patch("backend.api.DodoPayments") as dodo, \
         patch("backend.api.send_email", side_effect=lambda **kw: sent.append(kw)):
        r = client.post("/api/profile/resume-subscription", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "resumed"
    dodo.return_value.subscriptions.update.assert_called_once_with("sub_rs_keep", cancel_at_next_billing_date=False)
    dodo.return_value.checkout_sessions.create.assert_not_called()
    assert get_subscription(email)["cancel_scheduled"] is False
    assert len(sent) == 1 and "continue" in sent[0]["subject"].lower()


def test_keep_my_plan_is_refused_during_a_service_wind_down():
    email = "rs_wind@example.com"
    h = _headers(email)
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_rs_wind")
    set_cancellation(email, True, "12 November 2026")
    set_app_setting("wind_down_state", '{"mode": "period_end"}')
    with patch("backend.api.DODO_API_KEY", "fake_key"), patch("backend.api.DodoPayments") as dodo:
        r = client.post("/api/profile/resume-subscription", headers=h)
    assert r.status_code == 409
    dodo.return_value.subscriptions.update.assert_not_called()
    assert get_subscription(email)["cancel_scheduled"] is True


def test_keep_my_plan_needs_a_cancellation_to_undo():
    email = "rs_none@example.com"
    h = _headers(email)
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_rs_none")
    with patch("backend.api.DODO_API_KEY", "fake_key"), patch("backend.api.DodoPayments") as dodo:
        r = client.post("/api/profile/resume-subscription", headers=h)
    assert r.json()["status"] == "already_renewing"
    dodo.return_value.subscriptions.update.assert_not_called()
    assert client.post("/api/profile/resume-subscription", headers=_headers("rs_nobody@example.com")).status_code == 400


# ---- changing plan (or paying again anyway): the older subscription must stop ----

def test_a_new_subscription_stops_the_one_it_replaces():
    email = "rs_change@example.com"
    upsert_subscription(email=email, tier_id="studio_starter", status="active", dodo_subscription_id="sub_old_1")
    r, dodo = _webhook("subscription.active", _sub_attrs(email, "studio_pro", "sub_new_1"))
    assert r.status_code == 200
    dodo.return_value.subscriptions.update.assert_called_once()
    assert dodo.return_value.subscriptions.update.call_args.args[0] == "sub_old_1"
    assert dodo.return_value.subscriptions.update.call_args.kwargs["cancel_at_next_billing_date"] is True
    sub = get_subscription(email)
    assert sub["dodo_subscription_id"] == "sub_new_1" and sub["tier_id"] == "studio_pro" and sub["status"] == "active"
    assert sub["cancel_scheduled"] is False


def test_the_old_plans_late_update_cannot_pull_the_row_back():
    email = "rs_late@example.com"
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_new_2")
    old_live = MagicMock(cancel_at_next_billing_date=True)
    r, _ = _webhook("subscription.updated", _sub_attrs(email, "studio_starter", "sub_old_2"), live=old_live)
    assert r.status_code == 200
    sub = get_subscription(email)
    assert sub["dodo_subscription_id"] == "sub_new_2" and sub["tier_id"] == "studio_pro"


def test_an_update_from_a_different_live_subscription_is_still_honoured():
    """If the new plan's own 'active' event was missed, its update must still work."""
    email = "rs_missed@example.com"
    upsert_subscription(email=email, tier_id="studio_starter", status="active", dodo_subscription_id="sub_old_3")
    new_live = MagicMock(cancel_at_next_billing_date=False)
    r, dodo = _webhook("subscription.updated", _sub_attrs(email, "studio_pro", "sub_new_3"), live=new_live)
    assert r.status_code == 200
    assert get_subscription(email)["dodo_subscription_id"] == "sub_new_3"


def test_ending_the_old_subscription_later_does_not_touch_the_new_plan():
    email = "rs_end@example.com"
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_new_4")
    r, _ = _webhook("subscription.cancelled", {"subscription_id": "sub_old_4", "metadata": {}, "customer": MagicMock(email=email)})
    assert r.status_code == 200
    assert get_subscription(email)["status"] == "active"


# ---- after the period ends ----------------------------------------------------

def test_subscribing_again_after_the_period_ended_works_and_clears_the_old_flag():
    email = "rs_after@example.com"
    h = _headers(email)
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_old_5")
    set_cancellation(email, True, "12 November 2026")
    # Dodo ends it
    r, _ = _webhook("subscription.cancelled", {"subscription_id": "sub_old_5", "metadata": {}, "customer": MagicMock(email=email)})
    assert get_subscription(email)["status"] == "cancelled"
    # checkout is now allowed (plans open): it records a pending row but keeps nothing active
    with patch("backend.api.get_dodo_client") as dodo, \
         patch.dict("backend.api.TIER_DODO_PRODUCT_IDS", {"studio_pro": "prod_pro_test"}):
        dodo.return_value.checkout_sessions.create.return_value = MagicMock(id="cks_5", checkout_url="https://pay.test/5")
        co = client.post("/api/subscribe/checkout", headers=h, json={"tier_id": "studio_pro"})
    assert co.status_code == 200 and co.json()["checkout_url"] == "https://pay.test/5"
    assert get_subscription(email)["status"] == "pending_payment"
    # payment lands
    r, dodo = _webhook("subscription.active", _sub_attrs(email, "studio_pro", "sub_new_5"))
    sub = get_subscription(email)
    assert sub["status"] == "active" and sub["dodo_subscription_id"] == "sub_new_5"
    assert sub["cancel_scheduled"] is False and sub["access_until"] is None
    dodo.return_value.subscriptions.update.assert_not_called()  # nothing old left to stop
    prof = client.get("/api/profile", headers=h).json()["tier"]
    assert prof["status"] == "active" and prof["cancel_scheduled"] is False


def test_after_the_period_ends_launch_mode_still_keeps_studio_closed():
    email = "rs_launch@example.com"
    h = _headers(email)
    upsert_subscription(email=email, tier_id="studio_pro", status="cancelled", dodo_subscription_id="sub_old_6")
    assert client.post("/api/admin/launch-mode", json={"password": "test-admin-pw", "enabled": True}).status_code == 200
    with patch("backend.api.get_dodo_client") as dodo:
        r = client.post("/api/subscribe/checkout", headers=h, json={"tier_id": "studio_pro"})
    assert r.status_code == 403
    dodo.return_value.checkout_sessions.create.assert_not_called()
