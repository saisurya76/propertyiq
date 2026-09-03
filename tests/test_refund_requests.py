import os

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from unittest.mock import patch, MagicMock  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app  # noqa: E402
from backend.refund_store import (  # noqa: E402
    create_refund_request,
    list_refund_requests,
    get_refund_request_for_user,
)

client = TestClient(app)


def _submit(reason_code="duplicate_charge", email="requester@example.com", **kwargs):
    payload = {"user_email": email, "reason_code": reason_code, **kwargs}
    with patch("backend.api.send_email"):
        return client.post("/api/refund-requests", json=payload)


def test_submit_refund_request_creates_a_pending_record():
    r = _submit(details="Charged twice for the same report")
    assert r.status_code == 200
    data = r.json()["request"]
    assert data["status"] == "pending"
    assert data["reason_code"] == "duplicate_charge"
    assert data["user_email"] == "requester@example.com"


def test_submit_refund_request_rejects_an_invalid_reason_code():
    r = _submit(reason_code="i_just_dont_like_it")
    assert r.status_code == 400
    assert "reason_code must be one of" in r.json()["detail"]


def test_submit_refund_request_requires_details_when_reason_is_other():
    r = _submit(reason_code="other")
    assert r.status_code == 400
    assert "other" in r.json()["detail"].lower()


def test_submit_refund_request_with_other_and_details_succeeds():
    r = _submit(reason_code="other", details="A scenario the fixed list doesn't cover")
    assert r.status_code == 200


def test_submit_refund_request_sends_a_confirmation_email():
    with patch("backend.api.send_email") as mock_send:
        r = client.post("/api/refund-requests", json={"user_email": "emailme@example.com", "reason_code": "duplicate_charge"})
    assert r.status_code == 200
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["to_email"] == "emailme@example.com"


def test_submit_refund_request_succeeds_even_if_email_sending_fails():
    """A real resilience requirement: the request itself must be safely
    recorded regardless of whether the confirmation email succeeds."""
    with patch("backend.api.send_email", side_effect=Exception("simulated email outage")):
        r = client.post("/api/refund-requests", json={"user_email": "emailfails@example.com", "reason_code": "duplicate_charge"})
    assert r.status_code == 200
    assert r.json()["request"]["status"] == "pending"


def test_check_status_requires_matching_email_not_just_the_id():
    """A real, necessary privacy check: a guessed/leaked request id
    alone must not expose someone else's refund request details."""
    created = create_refund_request(user_email="owner@example.com", reason_code="duplicate_charge", details=None, purchase_reference=None)

    r_wrong_email = client.post("/api/refund-requests/status", json={"request_id": created["id"], "user_email": "someone_else@example.com"})
    assert r_wrong_email.status_code == 404

    r_correct = client.post("/api/refund-requests/status", json={"request_id": created["id"], "user_email": "owner@example.com"})
    assert r_correct.status_code == 200
    assert r_correct.json()["request"]["id"] == created["id"]


def test_admin_list_refund_requests_requires_correct_password():
    r = client.post("/api/admin/refund-requests/list", json={"password": "wrong"})
    assert r.status_code == 403


def test_admin_list_refund_requests_filters_by_status():
    create_refund_request(user_email="pendingcheck@example.com", reason_code="duplicate_charge", details=None, purchase_reference=None)

    r = client.post("/api/admin/refund-requests/list", json={"password": "test-admin-pw", "status": "pending"})
    assert r.status_code == 200
    assert all(x["status"] == "pending" for x in r.json()["requests"])

    r_denied = client.post("/api/admin/refund-requests/list", json={"password": "test-admin-pw", "status": "denied"})
    assert all(x["status"] == "denied" for x in r_denied.json()["requests"])


def test_admin_approve_via_dodo_issues_a_real_refund_and_links_the_request():
    created = create_refund_request(user_email="approveme@example.com", reason_code="duplicate_charge", details=None, purchase_reference="pay_dup_123")

    fake_refund = MagicMock()
    fake_refund.refund_id = "refund_approved_1"
    fake_refund.amount = 900
    fake_refund.currency = "usd"
    fake_refund.status = "succeeded"

    with patch("backend.api.DODO_API_KEY", "fake_key"), \
         patch("backend.api.DodoPayments") as mock_client_cls, \
         patch("backend.api.send_email"):
        mock_client_cls.return_value.refunds.create.return_value = fake_refund
        r = client.post("/api/admin/refund-requests/approve-dodo", json={
            "password": "test-admin-pw", "request_id": created["id"], "payment_id": "pay_dup_123",
        })

    assert r.status_code == 200
    data = r.json()
    assert data["request"]["status"] == "approved"
    assert data["request"]["linked_refund_id"] == data["refund"]["id"]
    assert data["refund"]["status"] == "succeeded"


def test_admin_approve_manually_records_a_refund_and_links_the_request():
    created = create_refund_request(user_email="manualapprove@example.com", reason_code="charged_after_cancellation", details=None, purchase_reference=None)

    with patch("backend.api.send_email"):
        r = client.post("/api/admin/refund-requests/approve-manual", json={
            "password": "test-admin-pw", "request_id": created["id"],
            "amount_usd": 29.0, "currency": "USD", "admin_note": "Refunded by hand via bank transfer",
        })

    assert r.status_code == 200
    data = r.json()
    assert data["request"]["status"] == "approved"
    assert data["refund"]["is_manual"] is True
    assert data["request"]["linked_refund_id"] == data["refund"]["id"]


def test_admin_deny_requires_a_reason_and_notifies_the_user():
    created = create_refund_request(user_email="denyme@example.com", reason_code="other", details="renewal I forgot to cancel", purchase_reference=None)

    r_no_reason = client.post("/api/admin/refund-requests/deny", json={"password": "test-admin-pw", "request_id": created["id"], "admin_response": ""})
    assert r_no_reason.status_code == 400

    with patch("backend.api.send_email") as mock_send:
        r = client.post("/api/admin/refund-requests/deny", json={
            "password": "test-admin-pw", "request_id": created["id"], "admin_response": "Renewal charges for a used period aren't refundable per policy.",
        })
    assert r.status_code == 200
    assert r.json()["request"]["status"] == "denied"
    assert r.json()["request"]["admin_response"] == "Renewal charges for a used period aren't refundable per policy."
    mock_send.assert_called_once()


def test_cannot_approve_or_deny_an_already_decided_request():
    """A real, necessary guard: a request that's already been approved
    or denied must not be actionable again — prevents double-refunding
    via the request flow specifically."""
    created = create_refund_request(user_email="alreadydone@example.com", reason_code="duplicate_charge", details=None, purchase_reference=None)
    with patch("backend.api.send_email"):
        client.post("/api/admin/refund-requests/deny", json={"password": "test-admin-pw", "request_id": created["id"], "admin_response": "Already handled"})

    r = client.post("/api/admin/refund-requests/deny", json={"password": "test-admin-pw", "request_id": created["id"], "admin_response": "Trying again"})
    assert r.status_code == 409


def test_approve_dodo_requires_correct_password():
    r = client.post("/api/admin/refund-requests/approve-dodo", json={"password": "wrong", "request_id": "x", "payment_id": "pay_1"})
    assert r.status_code == 403


def test_approve_manual_requires_correct_password():
    r = client.post("/api/admin/refund-requests/approve-manual", json={
        "password": "wrong", "request_id": "x", "amount_usd": 9.0, "admin_note": "x",
    })
    assert r.status_code == 403


def test_approving_a_nonexistent_request_returns_404():
    r = client.post("/api/admin/refund-requests/approve-manual", json={
        "password": "test-admin-pw", "request_id": "does-not-exist", "amount_usd": 9.0, "admin_note": "x",
    })
    assert r.status_code == 404


def test_approve_dodo_cancels_subscription_for_subscription_related_reasons():
    """The real, critical safeguard: approving a first_month_guarantee
    (or other subscription-related) refund request must also cancel
    the subscription immediately -- otherwise a customer keeps active,
    unlimited access after getting their money back."""
    from backend.subscription_store import upsert_subscription, get_subscription

    email = "guaranteeabuse@example.com"
    upsert_subscription(email=email, tier_id="studio_unlimited", status="active", dodo_subscription_id="sub_guarantee_test")
    created = create_refund_request(user_email=email, reason_code="first_month_guarantee", details=None, purchase_reference="pay_guarantee_123")

    fake_refund = MagicMock()
    fake_refund.refund_id = "refund_guarantee_1"
    fake_refund.amount = 7900
    fake_refund.currency = "usd"
    fake_refund.status = "succeeded"

    with patch("backend.api.DODO_API_KEY", "fake_key"), \
         patch("backend.api.DodoPayments") as mock_client_cls, \
         patch("backend.api.send_email"):
        mock_client_cls.return_value.refunds.create.return_value = fake_refund
        r = client.post("/api/admin/refund-requests/approve-dodo", json={
            "password": "test-admin-pw", "request_id": created["id"], "payment_id": "pay_guarantee_123",
        })

    assert r.status_code == 200
    mock_client_cls.return_value.subscriptions.update.assert_called_once_with("sub_guarantee_test", status="cancelled")
    assert get_subscription(email)["status"] == "cancelled"


def test_approve_dodo_does_not_cancel_subscription_for_one_time_purchase_reasons():
    """A real, necessary boundary: a refund for an unrelated one-time
    purchase (a Standard Report, say) must NOT touch a customer's
    separate, still-valid Studio subscription."""
    from backend.subscription_store import upsert_subscription, get_subscription

    email = "unrelatedsub@example.com"
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_unrelated_test")
    created = create_refund_request(user_email=email, reason_code="report_never_generated", details=None, purchase_reference="pay_report_999")

    fake_refund = MagicMock()
    fake_refund.refund_id = "refund_unrelated_1"
    fake_refund.amount = 1900
    fake_refund.currency = "usd"
    fake_refund.status = "succeeded"

    with patch("backend.api.DODO_API_KEY", "fake_key"), \
         patch("backend.api.DodoPayments") as mock_client_cls, \
         patch("backend.api.send_email"):
        mock_client_cls.return_value.refunds.create.return_value = fake_refund
        r = client.post("/api/admin/refund-requests/approve-dodo", json={
            "password": "test-admin-pw", "request_id": created["id"], "payment_id": "pay_report_999",
        })

    assert r.status_code == 200
    mock_client_cls.return_value.subscriptions.update.assert_not_called()
    assert get_subscription(email)["status"] == "active"
