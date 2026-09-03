import os
import uuid

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from unittest.mock import patch, MagicMock  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app  # noqa: E402
from backend.payment_email import build_payment_confirmation_html  # noqa: E402

client = TestClient(app)


def test_build_payment_confirmation_html_includes_the_real_logo():
    html = build_payment_confirmation_html(product_name="Studio Pro", amount_usd=29.0, currency="usd", payment_id="pay_123")
    assert "favicon.svg" in html
    assert "PropertyIQ" in html


def test_build_payment_confirmation_html_includes_order_details_and_payment_id():
    html = build_payment_confirmation_html(product_name="Studio Pro", amount_usd=29.0, currency="usd", payment_id="pay_abc123")
    assert "Studio Pro" in html
    assert "USD 29.00" in html
    assert "pay_abc123" in html


def test_build_payment_confirmation_html_includes_the_real_footer_links():
    """Matches the user's explicit ask for a footer -- the same three
    legal links the site's own LegalFooter component uses."""
    html = build_payment_confirmation_html(product_name="Insight Add-on", amount_usd=4.0, currency="usd", payment_id="pay_x")
    assert "privacy-policy.html" in html
    assert "terms-of-service.html" in html
    assert "refund-policy.html" in html


def test_build_payment_confirmation_html_handles_a_missing_amount_gracefully():
    """A real degradation case: don't crash or show a broken value if
    amount data genuinely isn't available."""
    html = build_payment_confirmation_html(product_name="Studio Starter", amount_usd=None, currency="usd", payment_id=None)
    assert "—" in html  # the honest placeholder, not a crash or "None"
    assert "None" not in html


def _fake_webhook_event(event_type, data_attrs):
    fake_data = MagicMock()
    for key, value in data_attrs.items():
        setattr(fake_data, key, value)
    fake_event = MagicMock()
    fake_event.type = event_type
    fake_event.data = fake_data
    return fake_event


def _post_webhook(fake_event, webhook_id=None):
    fake_webhook_client = MagicMock()
    fake_webhook_client.webhooks.unwrap.return_value = fake_event
    with patch("backend.api.get_dodo_webhook_client", return_value=fake_webhook_client):
        return client.post(
            "/api/webhooks/dodo",
            content=b"{}",
            headers={
                "webhook-id": webhook_id or f"wh_test_{uuid.uuid4().hex}",
                "webhook-signature": "sig_test",
                "webhook-timestamp": "0",
            },
        )


def test_subscription_activation_sends_a_confirmation_with_the_real_dodo_price():
    """Confirms the real, necessary lookup: subscription.active has no
    amount of its own, so the real, current Dodo price is fetched
    directly rather than left blank or guessed."""
    event = _fake_webhook_event("subscription.active", {
        "subscription_id": "sub_email_test",
        "payment_id": "pay_sub_1",
        "metadata": {"tier_id": "studio_pro", "user_email": "subtest@example.com"},
        "amount": None,
        "currency": None,
        "customer": None,
    })

    with patch("backend.api.send_email") as mock_send, \
         patch("backend.api.TIER_DODO_PRODUCT_IDS", {"studio_pro": "prod_pro_123"}), \
         patch("backend.api.get_dodo_product_price", return_value={"price_usd": 35.0, "currency": "usd", "is_recurring": True}):
        r = _post_webhook(event)

    assert r.status_code == 200
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["to_email"] == "subtest@example.com"
    assert "35.0" in call_kwargs["html"] or "35.00" in call_kwargs["html"]


def test_subscription_activation_falls_back_to_local_price_if_dodo_unreachable():
    event = _fake_webhook_event("subscription.active", {
        "subscription_id": "sub_fallback_test",
        "payment_id": "pay_sub_2",
        "metadata": {"tier_id": "studio_starter", "user_email": "fallbacktest@example.com"},
        "amount": None,
        "currency": None,
        "customer": None,
    })

    with patch("backend.api.send_email") as mock_send, \
         patch("backend.api.TIER_DODO_PRODUCT_IDS", {"studio_starter": "prod_starter_123"}), \
         patch("backend.api.get_dodo_product_price", return_value=None):
        r = _post_webhook(event)

    assert r.status_code == 200
    mock_send.assert_called_once()


def test_insight_addon_purchase_sends_a_confirmation():
    event = _fake_webhook_event("payment.succeeded", {
        "subscription_id": None,
        "payment_id": "pay_insight_1",
        "metadata": {"tier_id": "insight_addon", "user_email": "insighttest@example.com", "report_id": "report_xyz"},
        "amount": 400,
        "currency": "usd",
        "customer": None,
    })

    with patch("backend.api.send_email") as mock_send:
        r = _post_webhook(event)

    assert r.status_code == 200
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["to_email"] == "insighttest@example.com"
    assert "Insight Add-on" in call_kwargs["subject"]
    assert "4.0" in call_kwargs["html"] or "4.00" in call_kwargs["html"]


def test_standard_report_purchase_sends_a_confirmation_using_dodo_customer_email():
    """Confirms the real, necessary fallback: report_orders has no
    email field of its own, so the customer email for this specific
    product type has to come from Dodo's own payment.customer.email,
    not metadata.user_email (which this product type never sets)."""
    fake_customer = MagicMock()
    fake_customer.email = "reportbuyer@example.com"
    event = _fake_webhook_event("payment.succeeded", {
        "subscription_id": None,
        "payment_id": "pay_report_1",
        "metadata": {"product": "propertyiq_report", "order_id": "order_123"},
        "amount": 1900,
        "currency": "usd",
        "customer": fake_customer,
    })

    with patch("backend.api.send_email") as mock_send, \
         patch("backend.api.mark_order_paid"):
        r = _post_webhook(event)

    assert r.status_code == 200
    mock_send.assert_called_once()
    call_kwargs = mock_send.call_args.kwargs
    assert call_kwargs["to_email"] == "reportbuyer@example.com"
    assert "19.0" in call_kwargs["html"] or "19.00" in call_kwargs["html"]


def test_standard_report_purchase_sends_no_email_if_no_customer_email_available():
    """A real, honest degradation: if Dodo's own payload genuinely
    doesn't have a customer email either, no confirmation is sent --
    _send_payment_confirmation_email must not crash or send to a blank
    address."""
    event = _fake_webhook_event("payment.succeeded", {
        "subscription_id": None,
        "payment_id": "pay_report_2",
        "metadata": {"product": "propertyiq_report", "order_id": "order_456"},
        "amount": 1900,
        "currency": "usd",
        "customer": None,
    })

    with patch("backend.api.send_email") as mock_send, \
         patch("backend.api.mark_order_paid"):
        r = _post_webhook(event)

    assert r.status_code == 200
    mock_send.assert_not_called()


def test_confirmation_email_failure_does_not_break_webhook_processing():
    """A real resilience requirement: the actual, important state
    change (granting access, activating a tier) must succeed even if
    the confirmation email itself fails to send."""
    event = _fake_webhook_event("payment.succeeded", {
        "subscription_id": None,
        "payment_id": "pay_insight_2",
        "metadata": {"tier_id": "insight_addon", "user_email": "emailwillfail@example.com", "report_id": "report_abc"},
        "amount": 400,
        "currency": "usd",
        "customer": None,
    })

    with patch("backend.api.send_email", side_effect=Exception("simulated email outage")), \
         patch("backend.api.grant_insight_access") as mock_grant:
        r = _post_webhook(event)

    assert r.status_code == 200
    mock_grant.assert_called_once_with("report_abc", "emailwillfail@example.com")


def test_webhook_redelivery_of_the_same_event_does_not_double_process():
    """The real, previously-missing safeguard Dodo's own docs require:
    a redelivery of an event already handled must be a genuine no-op --
    not send a second confirmation email for the same, single payment."""
    event = _fake_webhook_event("payment.succeeded", {
        "subscription_id": None,
        "payment_id": "pay_dedup_test",
        "metadata": {"tier_id": "insight_addon", "user_email": "dedup@example.com", "report_id": "report_dedup"},
        "amount": 400,
        "currency": "usd",
        "customer": None,
    })

    shared_webhook_id = f"wh_dedup_test_{uuid.uuid4().hex}"
    with patch("backend.api.send_email") as mock_send:
        r1 = _post_webhook(event, webhook_id=shared_webhook_id)
        r2 = _post_webhook(event, webhook_id=shared_webhook_id)

    assert r1.status_code == 200
    assert r1.json().get("duplicate") is not True
    assert r2.status_code == 200
    assert r2.json().get("duplicate") is True
    mock_send.assert_called_once()  # not called twice


def test_webhook_with_a_genuinely_different_id_is_processed_normally():
    """A real, necessary contrast case: two DIFFERENT real events must
    both be processed -- the dedup check must key on the actual
    webhook-id, not accidentally suppress unrelated events."""
    event1 = _fake_webhook_event("payment.succeeded", {
        "subscription_id": None,
        "payment_id": "pay_distinct_1",
        "metadata": {"tier_id": "insight_addon", "user_email": "distinct1@example.com", "report_id": "report_distinct_1"},
        "amount": 400,
        "currency": "usd",
        "customer": None,
    })
    event2 = _fake_webhook_event("payment.succeeded", {
        "subscription_id": None,
        "payment_id": "pay_distinct_2",
        "metadata": {"tier_id": "insight_addon", "user_email": "distinct2@example.com", "report_id": "report_distinct_2"},
        "amount": 400,
        "currency": "usd",
        "customer": None,
    })

    with patch("backend.api.send_email") as mock_send:
        r1 = _post_webhook(event1)
        r2 = _post_webhook(event2)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert mock_send.call_count == 2
