import json
from unittest.mock import patch, MagicMock

import pytest

from backend.property_url_extract import fetch_page_text, extract_property_data, EXTRACTABLE_FIELDS


def test_fetch_page_text_strips_script_and_style_tags():
    """Real extraction quality depends on this: a listing page's actual
    text needs to be clean of script/style noise, or the model would be
    fed JS code and CSS rules mixed into the content it's trying to
    read facts out of."""
    fake_html = """
    <html><head><style>.price { color: red; }</style></head>
    <body>
        <script>console.log('tracking pixel junk');</script>
        <h1>Sunrise Towers</h1>
        <p>Developer: ABC Builders</p>
        <p>Price: 6,600,000</p>
    </body></html>
    """
    with patch("backend.property_url_extract.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_response.text = fake_html
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        text = fetch_page_text("https://example.com/listing/123")

    assert "Sunrise Towers" in text
    assert "ABC Builders" in text
    assert "6,600,000" in text
    assert "console.log" not in text
    assert "color: red" not in text


def test_fetch_page_text_rejects_non_html_content():
    with patch("backend.property_url_extract.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": "application/pdf"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        with pytest.raises(ValueError, match="did not return an HTML page"):
            fetch_page_text("https://example.com/some-file.pdf")


def test_extract_property_data_rejects_suspiciously_short_pages():
    """A real, deliberate design decision, not just an edge case: a page
    with almost no text is a strong signal the fetch hit a login wall or
    bot-block rather than real content — failing clearly here is better
    than silently sending near-empty content to the model and getting
    back an all-null result that looks identical to 'nothing found'."""
    with patch("backend.property_url_extract.ANTHROPIC_API_KEY", "fake_key_for_test"), \
         patch("backend.property_url_extract.fetch_page_text", return_value="Sign in to view this listing."):
        with pytest.raises(ValueError, match="very little content"):
            extract_property_data("https://example.com/blocked")


def test_extract_property_data_returns_exactly_the_expected_keys():
    """Even when the model's response omits a field entirely (rather than
    explicitly returning null for it), the function must still return
    all 10 keys with None for anything missing — the caller should never
    have to guess whether a key's absence means 'not found' vs 'the
    response was malformed'."""
    fake_page_text = "Sunrise Towers by ABC Builders. 1200 sqft. Priced at 6,600,000. Located in Hyderabad." * 5

    fake_claude_response = MagicMock()
    fake_claude_response.content = [MagicMock(text=json.dumps({
        "propertyName": "Sunrise Towers",
        "developerName": "ABC Builders",
        "quotedPrice": 6600000,
        "areaValue": 1200,
        "areaUnit": "sqft",
        "city": "Hyderabad",
        # location, propertyType, totalUnits, monthlyRent deliberately omitted
    }))]

    with patch("backend.property_url_extract.ANTHROPIC_API_KEY", "fake_key_for_test"), \
         patch("backend.property_url_extract.fetch_page_text", return_value=fake_page_text), \
         patch("backend.property_url_extract.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = fake_claude_response
        mock_anthropic_cls.return_value = mock_client

        result = extract_property_data("https://example.com/listing/456")

    assert set(result.keys()) == set(EXTRACTABLE_FIELDS)
    assert result["propertyName"] == "Sunrise Towers"
    assert result["developerName"] == "ABC Builders"
    assert result["quotedPrice"] == 6600000
    # Fields the model omitted entirely still come back as None, not missing
    assert result["location"] is None
    assert result["propertyType"] is None
    assert result["totalUnits"] is None
    assert result["monthlyRent"] is None


def test_extract_property_data_raises_clearly_on_invalid_json_response():
    """The model returning something that isn't valid JSON must be a
    clear, caught error — not a silent crash or a nonsense result passed
    through to the frontend."""
    fake_page_text = "Some real-looking listing content here. " * 20

    fake_claude_response = MagicMock()
    fake_claude_response.content = [MagicMock(text="I couldn't find a JSON object, sorry!")]

    with patch("backend.property_url_extract.ANTHROPIC_API_KEY", "fake_key_for_test"), \
         patch("backend.property_url_extract.fetch_page_text", return_value=fake_page_text), \
         patch("backend.property_url_extract.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = fake_claude_response
        mock_anthropic_cls.return_value = mock_client

        with pytest.raises(RuntimeError, match="did not return valid JSON"):
            extract_property_data("https://example.com/listing/789")


def test_extract_property_data_requires_api_key_configured():
    with patch("backend.property_url_extract.ANTHROPIC_API_KEY", ""):
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY is not configured"):
            extract_property_data("https://example.com/listing/999")


def test_endpoint_requires_auth_and_feature():
    """Real end-to-end gating check: the endpoint itself, not just the
    underlying extraction function, must require auth and the
    property_url_import feature — matching every other tier feature's
    enforcement pattern."""
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from backend.api import app
    from backend.auth_store import create_otp
    from backend.subscription_store import upsert_subscription

    client = TestClient(app)

    no_auth = client.post("/api/property/extract-from-url", json={"url": "https://example.com/listing/1"})
    assert no_auth.status_code == 401

    email = "url_import_gate_test@example.com"
    code = create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    headers = {"Authorization": f"Bearer {r.json()['session_token']}"}

    # No subscription at all -- feature gate should block it
    no_tier = client.post("/api/property/extract-from-url", json={"url": "https://example.com/listing/1"}, headers=headers)
    assert no_tier.status_code == 403

    # Studio Starter includes property_url_import -- should pass the gate
    # (mock the actual extraction so this doesn't attempt a real fetch)
    upsert_subscription(email=email, tier_id="studio_starter", dodo_subscription_id="sub_url_import_test", status="active")
    with patch("backend.api.extract_property_data", return_value={"propertyName": "Test Property"}):
        gated_ok = client.post("/api/property/extract-from-url", json={"url": "https://example.com/listing/1"}, headers=headers)
    assert gated_ok.status_code == 200
    assert gated_ok.json()["extracted"]["propertyName"] == "Test Property"

    # An invalid URL should be rejected before even attempting extraction
    bad_url = client.post("/api/property/extract-from-url", json={"url": "not-a-url"}, headers=headers)
    assert bad_url.status_code == 400
