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


def test_webhook_falls_back_to_subscription_retrieval_when_metadata_missing():
    """A real, confirmed root cause: checkout-session metadata (tier_id/
    user_email) is not guaranteed to land directly on the subscription
    webhook's data object — confirmed via a real, working Dodo
    integration example that retrieves the full subscription via the
    API inside the webhook handler rather than trusting the webhook
    payload alone. This was the actual cause of a real reported failure:
    a test subscription payment succeeded on Dodo's side, but the tier
    never activated in PropertyIQ, because tier_id/user_email came back
    empty from the webhook payload's own metadata."""
    from unittest.mock import patch, MagicMock
    from fastapi.testclient import TestClient
    from backend.api import app
    from backend.subscription_store import get_subscription

    client = TestClient(app)

    # A webhook event with NO metadata on the data object at all --
    # exactly the real failure mode -- only a bare subscription_id.
    fake_event = MagicMock()
    fake_event.type = "subscription.active"
    fake_event.data = MagicMock()
    fake_event.data.metadata = {}
    fake_event.data.subscription_id = "sub_fallback_test_123"
    fake_event.data.payment_id = None

    # What retrieving the full subscription object returns -- customer
    # email and product_id ARE reliably present here even when metadata
    # wasn't on the webhook payload itself.
    fake_subscription = MagicMock()
    fake_subscription.metadata = {}
    fake_subscription.product_id = "test_studio_starter_product_id"
    fake_subscription.customer = MagicMock()
    fake_subscription.customer.email = "webhook_fallback_test@example.com"

    fake_webhook_client = MagicMock()
    fake_webhook_client.webhooks.unwrap.return_value = fake_event
    fake_webhook_client.subscriptions.retrieve.return_value = fake_subscription

    with patch("backend.api.get_dodo_webhook_client", return_value=fake_webhook_client), \
         patch("backend.api.TIER_DODO_PRODUCT_IDS", {"studio_starter": "test_studio_starter_product_id"}):
        response = client.post(
            "/api/webhooks/dodo",
            content=b"{}",
            headers={"webhook-id": "wh_test_fallback_lookup", "webhook-signature": "sig_test", "webhook-timestamp": "0"},
        )

    assert response.status_code == 200
    sub = get_subscription("webhook_fallback_test@example.com")
    assert sub is not None
    assert sub["tier_id"] == "studio_starter"
    assert sub["status"] == "active"


def test_webhook_handles_subscription_updated_event_with_active_status():
    """A real, confirmed third root cause for a real reported failure,
    found from an actual live webhook payload the user pasted directly
    (not a hypothetical): Dodo sent subscription.updated (not
    subscription.active/renewed) for a genuinely active subscription,
    with tier_id/user_email correctly present in metadata the whole
    time. subscription.updated fires on ANY field change (per Dodo's
    own docs, which recommend tracking it specifically for this
    reason), so it can't be treated as an automatic "activate" signal
    the way subscription.active can — must be interpreted using the
    payload's own status field. This test uses the exact real payload
    shape reported, not a simplified approximation."""
    from unittest.mock import patch, MagicMock
    from fastapi.testclient import TestClient
    from backend.api import app
    from backend.subscription_store import get_subscription

    client = TestClient(app)

    # The exact real payload shape Dodo actually sent, condensed to the
    # fields the handler reads (full real payload had many more fields
    # this handler correctly ignores, like billing/addons/tax_id/etc).
    fake_event = MagicMock()
    fake_event.type = "subscription.updated"
    fake_event.data = MagicMock()
    fake_event.data.metadata = {"tier_id": "studio_starter", "user_email": "real_payload_test@example.com"}
    fake_event.data.subscription_id = "sub_0Nm2NGOUoDXb3B11jgYuf"
    fake_event.data.status = "active"
    fake_event.data.payment_id = None

    fake_webhook_client = MagicMock()
    fake_webhook_client.webhooks.unwrap.return_value = fake_event

    with patch("backend.api.get_dodo_webhook_client", return_value=fake_webhook_client):
        response = client.post(
            "/api/webhooks/dodo",
            content=b"{}",
            headers={"webhook-id": "wh_test_sub_updated_active", "webhook-signature": "sig_test", "webhook-timestamp": "0"},
        )

    assert response.status_code == 200
    sub = get_subscription("real_payload_test@example.com")
    assert sub is not None
    assert sub["tier_id"] == "studio_starter"
    assert sub["status"] == "active"


def test_webhook_subscription_updated_with_non_active_status_does_not_activate():
    """subscription.updated firing does NOT mean the subscription is
    active — must check the payload's actual status, not assume."""
    from unittest.mock import patch, MagicMock
    from fastapi.testclient import TestClient
    from backend.api import app
    from backend.subscription_store import get_subscription

    client = TestClient(app)

    fake_event = MagicMock()
    fake_event.type = "subscription.updated"
    fake_event.data = MagicMock()
    fake_event.data.metadata = {"tier_id": "studio_starter", "user_email": "on_hold_test@example.com"}
    fake_event.data.subscription_id = "sub_on_hold_test"
    fake_event.data.status = "on_hold"
    fake_event.data.payment_id = None

    fake_webhook_client = MagicMock()
    fake_webhook_client.webhooks.unwrap.return_value = fake_event

    with patch("backend.api.get_dodo_webhook_client", return_value=fake_webhook_client):
        response = client.post(
            "/api/webhooks/dodo",
            content=b"{}",
            headers={"webhook-id": "wh_test_sub_updated_inactive", "webhook-signature": "sig_test", "webhook-timestamp": "0"},
        )

    assert response.status_code == 200
    sub = get_subscription("on_hold_test@example.com")
    # Never having had a subscription record at all is the correct
    # outcome here (nothing to mark on_hold for a subscription that was
    # never created via a real checkout in this test) -- the key
    # assertion is that it was NOT marked "active".
    assert sub is None or sub["status"] != "active"


def test_standardwebhooks_dependency_is_actually_installed():
    """A real, confirmed production bug this guards against: every one
    of the webhook-handling tests above mocks get_dodo_webhook_client
    entirely, so the REAL unwrap() call (and its internal
    `from standardwebhooks import Webhook` import) never actually ran
    in this test suite — completely invisible to it. requirements.txt
    only listed `dodopayments`, not the `dodopayments[webhooks]` extra
    that actually installs the standardwebhooks package unwrap()
    depends on, so every real webhook in production failed at import
    time with a 401, regardless of how correct the webhook secret was.
    This test doesn't mock anything — it exercises the real,
    unmocked import path directly, matching what actually broke."""
    from dodopayments import DodoPayments

    client = DodoPayments(bearer_token="fake", environment="test_mode", webhook_key="whsec_ZmFrZV9zZWNyZXRfZm9yX3Rlc3Rpbmc=")
    try:
        client.webhooks.unwrap(
            "{}",
            headers={"webhook-id": "wh_test", "webhook-signature": "v1,fake", "webhook-timestamp": "0"},
        )
    except Exception as exc:
        # ANY exception other than the specific "you need to install
        # dodopayments[webhooks]" import error is fine here — a stale
        # timestamp or bad signature (which is exactly what this fake
        # test data should produce) proves the real verification logic
        # ran at all, which is the only thing this test needs to prove.
        assert "install" not in str(exc).lower() and "webhooks]" not in str(exc), (
            f"standardwebhooks dependency appears to be missing again: {type(exc).__name__}: {exc}"
        )


def test_admin_can_already_cap_the_unlimited_tier_with_a_real_finite_quota():
    """Directly answers a real question: does setting a specific number
    for Studio Unlimited's design_quota_per_month (instead of leaving it
    None/blank) actually get enforced, the same as it would for any
    other tier? Confirms this is already fully supported mechanically —
    nothing in the backend hardcodes "unlimited tier always has no
    limit" — the enforcement check only ever looks at whatever value is
    actually stored, for every tier including this one."""
    from backend.config_store import get_all_tiers_merged, set_tier_config

    original = get_all_tiers_merged()
    capped_config = {**original, "studio_unlimited": {**original["studio_unlimited"], "design_quota_per_month": 2}}
    set_tier_config(capped_config)

    try:
        email = "capped_unlimited@example.com"
        headers = _authed_headers(email)
        upsert_subscription(email=email, tier_id="studio_unlimited", status="active", dodo_subscription_id="sub_capped")

        payload = {
            "plot_size_sqft": 1000, "plot_length_ft": 40, "plot_width_ft": 25,
            "selections": {}, "entrance_direction": "north", "road_facing_side": "north",
        }

        r1 = client.post("/api/construction-studio/design", headers=headers, json=payload)
        assert r1.status_code == 200
        r2 = client.post("/api/construction-studio/design", headers=headers, json=payload)
        assert r2.status_code == 200
        # The 3rd generate this month must now be blocked, exactly like
        # it would be for Starter/Pro hitting their own real quota.
        r3 = client.post("/api/construction-studio/design", headers=headers, json=payload)
        assert r3.status_code == 403
        assert "2/2" in r3.json()["detail"]
    finally:
        set_tier_config(original)


def test_deleting_a_saved_property_does_not_free_up_the_generate_quota():
    """Directly answers a real, important question: does deleting a
    design free up the monthly GENERATE quota (design_quota_per_month)?
    No -- confirmed here directly. design_quota_per_month counts rows
    in construction_designs (an append-only generate-history log with
    no delete path at all, based on created_at within the current
    calendar month) -- a completely separate table/concept from the
    properties table saved_designs_limit counts, and a completely
    separate ACTION from saving/deleting a property at all: only
    /api/construction-studio/design (the cost-estimate generation step)
    consumes this quota; /api/properties (saving a multi-floor property
    directly) does not touch it at all, confirmed directly rather than
    assumed."""
    from backend.config_store import get_all_tiers_merged, set_tier_config

    original = get_all_tiers_merged()
    tight_config = {**original, "studio_starter": {**original["studio_starter"], "design_quota_per_month": 1}}
    set_tier_config(tight_config)

    try:
        email = "quota_after_delete@example.com"
        headers = _authed_headers(email)
        upsert_subscription(email=email, tier_id="studio_starter", status="active", dodo_subscription_id="sub_qd")

        plot_spec = {
            "plot_size_sqft": 1000, "plot_length_ft": 40, "plot_width_ft": 25,
            "entrance_direction": "north", "road_facing_side": "north",
        }

        # Uses up the entire monthly generate quota (1).
        r_generate = client.post(
            "/api/construction-studio/design", headers=headers,
            json={**plot_spec, "selections": {}},
        )
        assert r_generate.status_code == 200

        # Separately, save a property (a different action, unrelated to
        # the generate quota) and then delete it.
        floors = [{"floor_number": 1, "floor_label": "Ground Floor", "rooms": []}]
        r_create = client.post("/api/properties", headers=headers, json={"name": "Test House", "plot_spec": plot_spec, "floors": floors})
        assert r_create.status_code == 200
        property_id = r_create.json()["property_id"]
        r_delete = client.delete(f"/api/properties/{property_id}", headers=headers)
        assert r_delete.status_code == 200

        # The generate quota must still be exhausted -- deleting the
        # saved property (an entirely separate action/table) did NOT
        # free it up.
        r_generate_again = client.post(
            "/api/construction-studio/design", headers=headers,
            json={**plot_spec, "selections": {}},
        )
        assert r_generate_again.status_code == 403
        assert "Monthly design quota reached" in r_generate_again.json()["detail"]
    finally:
        set_tier_config(original)


def test_deleting_a_saved_property_does_free_up_the_save_limit():
    """The other half of the same question, for the OTHER limit type:
    saved_designs_limit counts live rows in `properties` directly, so
    deleting one genuinely does free up a slot -- confirmed here
    directly, not assumed from reading the code."""
    from backend.config_store import get_all_tiers_merged, set_tier_config

    original = get_all_tiers_merged()
    tight_config = {**original, "studio_starter": {**original["studio_starter"], "saved_designs_limit": 1, "design_quota_per_month": None}}
    set_tier_config(tight_config)

    try:
        email = "savelimit_after_delete@example.com"
        headers = _authed_headers(email)
        upsert_subscription(email=email, tier_id="studio_starter", status="active", dodo_subscription_id="sub_sl")

        plot_spec = {
            "plot_size_sqft": 1000, "plot_length_ft": 40, "plot_width_ft": 25,
            "entrance_direction": "north", "road_facing_side": "north",
        }

        floors = [{"floor_number": 1, "floor_label": "Ground Floor", "rooms": []}]
        r_create1 = client.post("/api/properties", headers=headers, json={"name": "House 1", "plot_spec": plot_spec, "floors": floors})
        assert r_create1.status_code == 200
        property_id = r_create1.json()["property_id"]

        # A 2nd save must be blocked -- the save limit (1) is now full.
        r_create2_blocked = client.post("/api/properties", headers=headers, json={"name": "House 2", "plot_spec": plot_spec, "floors": floors})
        assert r_create2_blocked.status_code == 403
        assert "Saved design limit reached" in r_create2_blocked.json()["detail"]

        # Delete the first one.
        r_delete = client.delete(f"/api/properties/{property_id}", headers=headers)
        assert r_delete.status_code == 200

        # Now a new save must genuinely succeed -- the slot was freed.
        r_create2_now_ok = client.post("/api/properties", headers=headers, json={"name": "House 2", "plot_spec": plot_spec, "floors": floors})
        assert r_create2_now_ok.status_code == 200
    finally:
        set_tier_config(original)
