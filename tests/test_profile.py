import os

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from unittest.mock import patch, MagicMock  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app  # noqa: E402
from backend.auth_store import create_otp  # noqa: E402
from backend.subscription_store import upsert_subscription  # noqa: E402
from backend.profile_store import is_email_in_cooling_off, get_deletion_record, COOLING_OFF_DAYS  # noqa: E402
from backend.refund_store import create_refund_request, deny_refund_request  # noqa: E402
from backend.construction_store import reset_quota_for_user  # noqa: E402
from backend.property_store import create_property  # noqa: E402

client = TestClient(app)


def _authed_headers(email: str) -> dict:
    code = create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    token = r.json()["session_token"]
    return {"Authorization": f"Bearer {token}"}


def test_get_profile_requires_auth():
    r = client.get("/api/profile")
    assert r.status_code == 401


def test_get_profile_shows_real_tier_and_quota():
    email = "profiletest@example.com"
    headers = _authed_headers(email)
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_profile_test")

    r = client.get("/api/profile", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == email
    assert data["tier"]["tier_id"] == "studio_pro"
    assert data["quota"]["design_quota_per_month"] == 15
    assert data["quota"]["designs_used_this_month"] == 0


def test_get_profile_handles_no_subscription_gracefully():
    email = "nosubprofile@example.com"
    headers = _authed_headers(email)

    r = client.get("/api/profile", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["tier"]["tier_id"] is None
    assert "No subscription payments" in data["payments_note"]


def test_get_profile_includes_real_payment_history_from_dodo():
    email = "paymenthistory@example.com"
    headers = _authed_headers(email)
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_payment_history")

    fake_payment = MagicMock()
    fake_payment.payment_id = "pay_history_1"
    fake_payment.total_amount = 2900
    fake_payment.currency = "usd"
    fake_payment.status = "succeeded"
    fake_payment.created_at.isoformat.return_value = "2026-08-01T00:00:00+00:00"
    fake_page = MagicMock()
    fake_page.items = [fake_payment]

    with patch("backend.api.DODO_API_KEY", "fake_key"), \
         patch("backend.api.DodoPayments") as mock_client_cls:
        mock_client_cls.return_value.payments.list.return_value = fake_page
        r = client.get("/api/profile", headers=headers)

    assert r.status_code == 200
    payments = r.json()["payments"]
    assert len(payments) == 1
    assert payments[0]["payment_id"] == "pay_history_1"
    assert payments[0]["amount_usd"] == 29.0


def test_get_profile_degrades_gracefully_on_dodo_failure():
    email = "dodofailsprofile@example.com"
    headers = _authed_headers(email)
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_dodo_fails")

    with patch("backend.api.DODO_API_KEY", "fake_key"), \
         patch("backend.api.DodoPayments") as mock_client_cls:
        mock_client_cls.return_value.payments.list.side_effect = Exception("simulated outage")
        r = client.get("/api/profile", headers=headers)

    assert r.status_code == 200  # the whole profile must not fail over this
    assert r.json()["payments"] == []
    assert "Couldn't load payment history" in r.json()["payments_note"]


def test_get_profile_aggregates_real_notifications():
    email = "notiftest@example.com"
    headers = _authed_headers(email)

    req = create_refund_request(user_email=email, reason_code="duplicate_charge", details=None, purchase_reference=None)
    deny_refund_request(req["id"], "Not eligible per policy")
    reset_quota_for_user(email, "Goodwill reset")

    r = client.get("/api/profile", headers=headers)
    assert r.status_code == 200
    notifications = r.json()["notifications"]
    types = [n["type"] for n in notifications]
    assert "refund_request" in types
    assert "quota_reset" in types


def test_cancel_subscription_requires_an_active_subscription():
    email = "nocancel@example.com"
    headers = _authed_headers(email)
    r = client.post("/api/profile/cancel-subscription", headers=headers, json={})
    assert r.status_code == 400


def test_cancel_subscription_calls_the_real_dodo_api_correctly():
    email = "cancelme@example.com"
    headers = _authed_headers(email)
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_cancel_test")

    with patch("backend.api.DODO_API_KEY", "fake_key"), \
         patch("backend.api.DodoPayments") as mock_client_cls, \
         patch("backend.api.send_email"):
        r = client.post("/api/profile/cancel-subscription", headers=headers, json={"reason": "too expensive"})

    assert r.status_code == 200
    mock_client_cls.return_value.subscriptions.update.assert_called_once_with(
        "sub_cancel_test",
        cancel_at_next_billing_date=True,
        cancel_reason="cancelled_by_customer",
        cancellation_comment="too expensive",
    )


def test_delete_account_requires_matching_confirmation_email():
    email = "deleteme@example.com"
    headers = _authed_headers(email)
    r = client.post("/api/profile/delete-account", headers=headers, json={"confirm_email": "wrong@example.com"})
    assert r.status_code == 400


def test_delete_account_genuinely_removes_data_and_enforces_cooling_off():
    email = "fulldelete@example.com"
    headers = _authed_headers(email)
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_full_delete")
    create_property(
        user_email=email, name="Test", plot_spec={}, selections={},
        labor_selections={}, site_elements=[], floors=[{"floor_number": 1, "floor_label": "Ground Floor", "rooms": []}],
    )

    with patch("backend.api.send_email"):
        r = client.post("/api/profile/delete-account", headers=headers, json={"confirm_email": email, "reason": "no longer needed"})
    assert r.status_code == 200

    # The account is genuinely gone -- the same session token no longer works.
    r_after = client.get("/api/profile", headers=headers)
    assert r_after.status_code == 401

    # Cooling-off is real and enforced at the actual entry point (OTP request).
    assert is_email_in_cooling_off(email) is True
    r_otp = client.post("/api/auth/request-otp", json={"email": email})
    assert r_otp.status_code == 403
    assert f"{COOLING_OFF_DAYS} days" in r_otp.json()["detail"]

    record = get_deletion_record(email)
    assert record["reason"] == "no longer needed"


def test_delete_account_does_not_permanently_ban_only_time_limits():
    """Directly verifies the actual, considered design: this is a
    time-limited cooling-off, not a permanent, indefinite ban -- a
    deletion record from far enough in the past must NOT still block
    re-registration."""
    from datetime import datetime, timedelta, timezone
    from backend.db import get_connection

    email = "oldeletion@example.com"
    long_ago = (datetime.now(timezone.utc) - timedelta(days=COOLING_OFF_DAYS + 1)).isoformat()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO deleted_accounts (email, deleted_at, reason) VALUES (%s, %s, %s) "
                "ON CONFLICT (email) DO UPDATE SET deleted_at = EXCLUDED.deleted_at",
                (email, long_ago, "old test deletion"),
            )
        connection.commit()

    assert is_email_in_cooling_off(email) is False
    with patch("backend.api.send_otp_email"):
        r = client.post("/api/auth/request-otp", json={"email": email})
    assert r.status_code == 200


def test_delete_account_still_deletes_data_even_if_dodo_cancellation_fails():
    """A real resilience requirement: a Dodo hiccup during cancellation
    must not block the actual account/data deletion the user asked
    for -- the more important, irreversible action the user explicitly
    requested."""
    email = "dodofailsondelete@example.com"
    headers = _authed_headers(email)
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_dodo_fails_delete")

    with patch("backend.api.DODO_API_KEY", "fake_key"), \
         patch("backend.api.DodoPayments") as mock_client_cls, \
         patch("backend.api.send_email"):
        mock_client_cls.return_value.subscriptions.update.side_effect = Exception("simulated Dodo outage")
        r = client.post("/api/profile/delete-account", headers=headers, json={"confirm_email": email})

    assert r.status_code == 200
    assert is_email_in_cooling_off(email) is True
