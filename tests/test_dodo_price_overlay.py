import os

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from unittest.mock import patch, MagicMock  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app, get_dodo_product_price, overlay_dodo_prices  # noqa: E402

client = TestClient(app)


def _fake_product(price_cents, currency="usd", is_recurring=True):
    product = MagicMock()
    product.price.price = price_cents
    product.price.currency = currency
    product.price.type = "recurring_price" if is_recurring else "one_time_price"
    return product


def test_get_dodo_product_price_returns_the_real_current_price():
    """Confirms the actual real bug this fixes: price_usd was never
    sent to Dodo at checkout at all, so it could silently drift from
    what a customer is really charged. This reads the real, live value
    directly from Dodo's own product record instead."""
    with patch("backend.api.get_app_setting", return_value=None), \
         patch("backend.api.set_app_setting"), \
         patch("backend.api.DODO_API_KEY", "fake_key"), \
         patch("backend.api.DodoPayments") as mock_client_cls:
        mock_client_cls.return_value.products.retrieve.return_value = _fake_product(2900)
        result = get_dodo_product_price("prod_test_123")

    assert result["price_usd"] == 29.0
    assert result["currency"] == "usd"
    assert result["is_recurring"] is True


def test_get_dodo_product_price_correctly_converts_from_cents():
    """A real, easy-to-get-wrong detail confirmed directly from Dodo's
    own SDK type: price.price is in the smallest currency denomination
    (cents for USD), not dollars."""
    with patch("backend.api.get_app_setting", return_value=None), \
         patch("backend.api.set_app_setting"), \
         patch("backend.api.DODO_API_KEY", "fake_key"), \
         patch("backend.api.DodoPayments") as mock_client_cls:
        mock_client_cls.return_value.products.retrieve.return_value = _fake_product(499)
        result = get_dodo_product_price("prod_insight")

    assert result["price_usd"] == 4.99


def test_get_dodo_product_price_returns_none_when_key_not_configured():
    with patch("backend.api.DODO_API_KEY", ""):
        result = get_dodo_product_price("prod_test_123")
    assert result is None


def test_get_dodo_product_price_returns_none_for_an_empty_product_id():
    with patch("backend.api.DODO_API_KEY", "fake_key"):
        result = get_dodo_product_price("")
    assert result is None


def test_get_dodo_product_price_degrades_gracefully_on_api_failure():
    """A real resilience requirement: a Dodo outage must not break the
    pricing page or the admin dashboard -- it should fall back to the
    locally-stored value, not surface a raw error."""
    with patch("backend.api.get_app_setting", return_value=None), \
         patch("backend.api.DODO_API_KEY", "fake_key"), \
         patch("backend.api.DodoPayments") as mock_client_cls:
        mock_client_cls.return_value.products.retrieve.side_effect = Exception("simulated Dodo outage")
        result = get_dodo_product_price("prod_test_123")
    assert result is None


def test_get_dodo_product_price_is_cached_not_fetched_on_every_call():
    with patch("backend.api.get_app_setting", return_value=None), \
         patch("backend.api.set_app_setting"), \
         patch("backend.api.DODO_API_KEY", "fake_key"), \
         patch("backend.api.DodoPayments") as mock_client_cls:
        mock_client_cls.return_value.products.retrieve.return_value = _fake_product(2900)
        get_dodo_product_price("prod_test_123")
        assert mock_client_cls.return_value.products.retrieve.call_count == 1

    import json
    from datetime import datetime, timezone
    cached_json = json.dumps({"result": {"price_usd": 29.0, "currency": "usd", "is_recurring": True}, "fetched_at": datetime.now(timezone.utc).isoformat()})
    with patch("backend.api.get_app_setting", return_value=cached_json), \
         patch("backend.api.DODO_API_KEY", "fake_key"), \
         patch("backend.api.DodoPayments") as mock_client_cls2:
        result = get_dodo_product_price("prod_test_123")
        mock_client_cls2.assert_not_called()
    assert result["price_usd"] == 29.0


def test_overlay_dodo_prices_replaces_local_price_with_the_real_dodo_one():
    tiers = {
        "studio_pro": {"label": "Studio Pro", "price_usd": 29, "billing": "subscription", "features": []},
    }
    with patch("backend.api.TIER_DODO_PRODUCT_IDS", {"studio_pro": "prod_pro_123"}), \
         patch("backend.api.get_dodo_product_price", return_value={"price_usd": 35.0, "currency": "usd", "is_recurring": True}):
        result = overlay_dodo_prices(tiers)

    assert result["studio_pro"]["price_usd"] == 35.0
    assert result["studio_pro"]["price_source"] == "dodo"


def test_overlay_dodo_prices_falls_back_to_local_price_when_dodo_is_unreachable():
    """The honest fallback behavior: a transient Dodo outage or an
    unconfigured product_id must not break the pricing page -- the
    locally-stored price is kept, but clearly marked as a fallback
    rather than presented identically to a real, live Dodo price."""
    tiers = {
        "studio_pro": {"label": "Studio Pro", "price_usd": 29, "billing": "subscription", "features": []},
    }
    with patch("backend.api.TIER_DODO_PRODUCT_IDS", {"studio_pro": "prod_pro_123"}), \
         patch("backend.api.get_dodo_product_price", return_value=None):
        result = overlay_dodo_prices(tiers)

    assert result["studio_pro"]["price_usd"] == 29  # untouched, the original local value
    assert result["studio_pro"]["price_source"] == "local_fallback"


def test_overlay_dodo_prices_marks_fallback_when_no_product_id_is_configured_at_all():
    tiers = {"studio_starter": {"label": "Studio Starter", "price_usd": 9, "billing": "subscription", "features": []}}
    with patch("backend.api.TIER_DODO_PRODUCT_IDS", {"studio_starter": ""}):
        result = overlay_dodo_prices(tiers)
    assert result["studio_starter"]["price_source"] == "local_fallback"
    assert result["studio_starter"]["price_usd"] == 9


def test_tiers_endpoint_returns_dodo_overlaid_prices():
    with patch("backend.api.TIER_DODO_PRODUCT_IDS", {"studio_pro": "prod_pro_123", "studio_starter": "", "studio_unlimited": "", "insight_addon": ""}), \
         patch("backend.api.get_dodo_product_price", side_effect=lambda pid: {"price_usd": 35.0, "currency": "usd", "is_recurring": True} if pid == "prod_pro_123" else None):
        r = client.get("/api/tiers")
    assert r.status_code == 200
    data = r.json()
    assert data["studio_pro"]["price_usd"] == 35.0
    assert data["studio_pro"]["price_source"] == "dodo"


def test_overlay_dodo_prices_rejects_a_non_usd_dodo_product():
    """A real, necessary safety check: every other part of the app's
    pricing (get_fx_rates's own USD-based FX table) assumes price_usd
    genuinely is USD. A Dodo product misconfigured in a different
    currency must not get silently treated as a raw USD figure -- that
    would double-convert incorrectly once the frontend's own local-
    currency display logic multiplies it by the FX rate again."""
    tiers = {"studio_pro": {"label": "Studio Pro", "price_usd": 29, "billing": "subscription", "features": []}}
    with patch("backend.api.TIER_DODO_PRODUCT_IDS", {"studio_pro": "prod_pro_123"}), \
         patch("backend.api.get_dodo_product_price", return_value={"price_usd": 2500.0, "currency": "inr", "is_recurring": True}):
        result = overlay_dodo_prices(tiers)

    assert result["studio_pro"]["price_usd"] == 29  # untouched local value, NOT the raw INR figure
    assert result["studio_pro"]["price_source"] == "local_fallback"


def test_overlay_dodo_prices_accepts_usd_case_insensitively():
    tiers = {"studio_pro": {"label": "Studio Pro", "price_usd": 29, "billing": "subscription", "features": []}}
    with patch("backend.api.TIER_DODO_PRODUCT_IDS", {"studio_pro": "prod_pro_123"}), \
         patch("backend.api.get_dodo_product_price", return_value={"price_usd": 35.0, "currency": "USD", "is_recurring": True}):
        result = overlay_dodo_prices(tiers)

    assert result["studio_pro"]["price_usd"] == 35.0
    assert result["studio_pro"]["price_source"] == "dodo"
