import os

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from unittest.mock import patch, MagicMock  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app  # noqa: E402
from backend.refund_store import (  # noqa: E402
    record_dodo_refund,
    record_manual_refund,
    upsert_refund_status_by_dodo_id,
    list_all_refunds,
    get_refund,
)
from backend.subscription_store import upsert_subscription  # noqa: E402

client = TestClient(app)


def test_record_dodo_refund_creates_a_real_record():
    record = record_dodo_refund(
        dodo_refund_id="refund_test_1",
        dodo_payment_id="pay_test_1",
        user_email="Test@Example.com",
        amount_usd=29.0,
        currency="usd",
        reason="requested by customer",
        status="succeeded",
    )
    assert record["dodo_refund_id"] == "refund_test_1"
    assert record["user_email"] == "test@example.com"  # normalized lowercase
    assert record["is_manual"] is False
    assert record["status"] == "succeeded"


def test_record_manual_refund_is_clearly_distinguished_from_a_dodo_one():
    """The real, explicit point of this feature: a refund PropertyIQ
    handled outside Dodo entirely must never be confused with a real,
    Dodo-confirmed refund -- always status='manual', is_manual=True,
    and no dodo_refund_id/dodo_payment_id at all."""
    record = record_manual_refund(
        user_email="manual@example.com",
        amount_usd=9.0,
        currency="USD",
        reason="Dodo failed to process a duplicate charge refund",
        admin_note="Refunded via direct bank transfer on 2026-08-31",
    )
    assert record["is_manual"] is True
    assert record["status"] == "manual"
    assert record["dodo_refund_id"] is None
    assert record["dodo_payment_id"] is None
    assert record["admin_note"] == "Refunded via direct bank transfer on 2026-08-31"


def test_upsert_refund_status_updates_an_existing_record():
    record = record_dodo_refund(
        dodo_refund_id="refund_test_update",
        dodo_payment_id="pay_test_update",
        user_email="update@example.com",
        amount_usd=29.0,
        currency="usd",
        reason=None,
        status="pending",
    )
    upsert_refund_status_by_dodo_id(dodo_refund_id="refund_test_update", status="succeeded")

    updated = get_refund(record["id"])
    assert updated["status"] == "succeeded"


def test_upsert_refund_status_creates_a_new_record_when_none_exists():
    """The real gap this fixes: a refund issued directly from Dodo's
    own dashboard (never through PropertyIQ's admin panel at all) still
    needs to show up here for monitoring, not silently vanish just
    because PropertyIQ never initiated it."""
    upsert_refund_status_by_dodo_id(
        dodo_refund_id="refund_from_dodo_dashboard",
        status="succeeded",
        dodo_payment_id="pay_from_dashboard",
        user_email="dashboard@example.com",
        amount_usd=15.0,
        currency="usd",
        reason="issued directly in Dodo",
    )

    all_refunds = list_all_refunds()
    matching = [r for r in all_refunds if r["dodo_refund_id"] == "refund_from_dodo_dashboard"]
    assert len(matching) == 1
    assert matching[0]["status"] == "succeeded"
    assert matching[0]["user_email"] == "dashboard@example.com"


def test_admin_payments_lookup_requires_correct_password():
    r = client.post("/api/admin/payments", json={"password": "wrong", "email": "test@example.com"})
    assert r.status_code == 403


def test_admin_payments_lookup_returns_a_helpful_note_when_no_subscription_exists():
    r = client.post("/api/admin/payments", json={"password": "test-admin-pw", "email": "no_subscription_at_all@example.com"})
    assert r.status_code == 200
    data = r.json()
    assert data["payments"] == []
    assert "paste the payment_id directly" in data["note"]


def test_admin_payments_lookup_returns_real_dodo_payment_data():
    upsert_subscription(email="haspayments@example.com", tier_id="studio_pro", status="active", dodo_subscription_id="sub_haspayments")

    fake_payment = MagicMock()
    fake_payment.payment_id = "pay_abc123"
    fake_payment.total_amount = 2900
    fake_payment.currency = "usd"
    fake_payment.status = "succeeded"
    fake_payment.refund_status = None
    fake_payment.created_at.isoformat.return_value = "2026-08-01T00:00:00+00:00"

    fake_page = MagicMock()
    fake_page.items = [fake_payment]

    with patch("backend.api.DODO_API_KEY", "fake_key"), \
         patch("backend.api.DodoPayments") as mock_client_cls:
        mock_client_cls.return_value.payments.list.return_value = fake_page
        r = client.post("/api/admin/payments", json={"password": "test-admin-pw", "email": "haspayments@example.com"})

    assert r.status_code == 200
    data = r.json()
    assert len(data["payments"]) == 1
    assert data["payments"][0]["payment_id"] == "pay_abc123"
    assert data["payments"][0]["amount_usd"] == 29.0


def test_admin_payments_lookup_degrades_gracefully_on_dodo_failure():
    upsert_subscription(email="dodofails@example.com", tier_id="studio_pro", status="active", dodo_subscription_id="sub_dodofails")

    with patch("backend.api.DODO_API_KEY", "fake_key"), \
         patch("backend.api.DodoPayments") as mock_client_cls:
        mock_client_cls.return_value.payments.list.side_effect = Exception("simulated Dodo outage")
        r = client.post("/api/admin/payments", json={"password": "test-admin-pw", "email": "dodofails@example.com"})

    assert r.status_code == 502


def test_admin_issue_refund_calls_the_real_dodo_api_and_records_it():
    fake_refund = MagicMock()
    fake_refund.refund_id = "refund_issued_1"
    fake_refund.amount = 2900
    fake_refund.currency = "usd"
    fake_refund.status = "pending"

    with patch("backend.api.DODO_API_KEY", "fake_key"), \
         patch("backend.api.DodoPayments") as mock_client_cls:
        mock_client_cls.return_value.refunds.create.return_value = fake_refund
        r = client.post("/api/admin/refunds", json={
            "password": "test-admin-pw", "payment_id": "pay_to_refund", "user_email": "refundme@example.com", "reason": "customer requested",
        })

    assert r.status_code == 200
    mock_client_cls.return_value.refunds.create.assert_called_once_with(payment_id="pay_to_refund", reason="customer requested")
    assert r.json()["refund"]["status"] == "pending"
    assert r.json()["refund"]["amount_usd"] == 29.0


def test_admin_issue_refund_requires_correct_password():
    r = client.post("/api/admin/refunds", json={"password": "wrong", "payment_id": "pay_1", "user_email": "x@example.com"})
    assert r.status_code == 403


def test_admin_issue_refund_surfaces_a_real_dodo_rejection_not_a_generic_error():
    with patch("backend.api.DODO_API_KEY", "fake_key"), \
         patch("backend.api.DodoPayments") as mock_client_cls:
        mock_client_cls.return_value.refunds.create.side_effect = Exception("payment already fully refunded")
        r = client.post("/api/admin/refunds", json={
            "password": "test-admin-pw", "payment_id": "pay_already_refunded", "user_email": "x@example.com",
        })

    assert r.status_code == 502
    assert "payment already fully refunded" in r.json()["detail"]


def test_admin_manual_refund_makes_no_real_api_call():
    with patch("backend.api.DodoPayments") as mock_client_cls:
        r = client.post("/api/admin/refunds/manual", json={
            "password": "test-admin-pw", "user_email": "manualtest@example.com", "amount_usd": 9.0,
            "reason": "Dodo missed this one", "admin_note": "Refunded by hand via UPI",
        })
        mock_client_cls.assert_not_called()

    assert r.status_code == 200
    assert r.json()["refund"]["is_manual"] is True


def test_admin_manual_refund_requires_correct_password():
    r = client.post("/api/admin/refunds/manual", json={
        "password": "wrong", "user_email": "x@example.com", "amount_usd": 9.0, "reason": "x", "admin_note": "x",
    })
    assert r.status_code == 403


def test_admin_list_refunds_returns_both_dodo_and_manual_entries():
    record_dodo_refund(dodo_refund_id="refund_list_1", dodo_payment_id="pay_list_1", user_email="a@example.com", amount_usd=29.0, currency="usd", reason=None, status="succeeded")
    record_manual_refund(user_email="b@example.com", amount_usd=9.0, currency="USD", reason="manual test", admin_note="test note")

    r = client.post("/api/admin/refunds/list", json={"password": "test-admin-pw"})
    assert r.status_code == 200
    refunds = r.json()["refunds"]
    assert any(x["dodo_refund_id"] == "refund_list_1" for x in refunds)
    assert any(x["is_manual"] is True and x["user_email"] == "b@example.com" for x in refunds)


def test_admin_list_refunds_requires_correct_password():
    r = client.post("/api/admin/refunds/list", json={"password": "wrong"})
    assert r.status_code == 403


def test_refund_webhook_updates_a_record_issued_via_the_admin_panel():
    """Confirms the full real lifecycle: admin issues a refund (status
    starts as whatever Dodo returned immediately, e.g. "pending"), then
    the real refund.succeeded webhook arrives later and updates that
    same record to its final, confirmed status — the two-step flow
    admin_issue_refund's own docstring describes."""
    record = record_dodo_refund(
        dodo_refund_id="refund_webhook_lifecycle",
        dodo_payment_id="pay_webhook_lifecycle",
        user_email="lifecycle@example.com",
        amount_usd=29.0,
        currency="usd",
        reason=None,
        status="pending",
    )

    fake_event = MagicMock()
    fake_event.type = "refund.succeeded"
    fake_event.data = MagicMock()
    fake_event.data.refund_id = "refund_webhook_lifecycle"
    fake_event.data.payment_id = "pay_webhook_lifecycle"
    fake_event.data.customer = MagicMock()
    fake_event.data.customer.email = "lifecycle@example.com"
    fake_event.data.amount = 2900
    fake_event.data.currency = "usd"
    fake_event.data.reason = None
    fake_event.data.metadata = {}
    fake_event.data.subscription_id = None
    fake_event.data.status = None

    fake_webhook_client = MagicMock()
    fake_webhook_client.webhooks.unwrap.return_value = fake_event

    with patch("backend.api.get_dodo_webhook_client", return_value=fake_webhook_client):
        response = client.post(
            "/api/webhooks/dodo",
            content=b"{}",
            headers={"webhook-id": "wh_test", "webhook-signature": "sig_test", "webhook-timestamp": "0"},
        )

    assert response.status_code == 200
    updated = get_refund(record["id"])
    assert updated["status"] == "succeeded"


def test_refund_webhook_creates_a_record_for_a_refund_issued_directly_in_dodo():
    """The other real path: a refund issued directly in Dodo's own
    dashboard, never touching PropertyIQ's admin panel at all, must
    still show up in the refund store once the webhook fires."""
    fake_event = MagicMock()
    fake_event.type = "refund.succeeded"
    fake_event.data = MagicMock()
    fake_event.data.refund_id = "refund_direct_from_dodo_dashboard"
    fake_event.data.payment_id = "pay_direct_from_dodo"
    fake_event.data.customer = MagicMock()
    fake_event.data.customer.email = "directdodo@example.com"
    fake_event.data.amount = 900
    fake_event.data.currency = "usd"
    fake_event.data.reason = "issued in Dodo dashboard directly"
    fake_event.data.metadata = {}
    fake_event.data.subscription_id = None
    fake_event.data.status = None

    fake_webhook_client = MagicMock()
    fake_webhook_client.webhooks.unwrap.return_value = fake_event

    with patch("backend.api.get_dodo_webhook_client", return_value=fake_webhook_client):
        response = client.post(
            "/api/webhooks/dodo",
            content=b"{}",
            headers={"webhook-id": "wh_test", "webhook-signature": "sig_test", "webhook-timestamp": "0"},
        )

    assert response.status_code == 200
    matching = [r for r in list_all_refunds() if r["dodo_refund_id"] == "refund_direct_from_dodo_dashboard"]
    assert len(matching) == 1
    assert matching[0]["user_email"] == "directdodo@example.com"
    assert matching[0]["amount_usd"] == 9.0
