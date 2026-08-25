import json
from unittest.mock import patch, MagicMock

import pytest

from backend.property_url_extract import (
    fetch_page_html,
    extract_structured_data,
    extract_property_data,
    EXTRACTABLE_FIELDS,
)


def test_fetch_page_html_rejects_non_html_content():
    with patch("backend.property_url_extract.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": "application/pdf"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        with pytest.raises(ValueError, match="did not return an HTML page"):
            fetch_page_html("https://example.com/some-file.pdf")


def test_extract_structured_data_reads_json_ld():
    """The genuinely free path: real listing sites commonly publish
    schema.org JSON-LD for SEO — this should be parsed with zero API
    cost, not sent to an LLM."""
    html = """
    <html><head>
    <script type="application/ld+json">
    {
      "@type": "Product",
      "name": "Sunrise Towers",
      "brand": {"name": "ABC Builders"},
      "offers": {"price": "6600000"},
      "floorSize": {"value": "1200", "unitText": "sqft"},
      "address": {"addressLocality": "Hyderabad", "streetAddress": "Gachibowli"}
    }
    </script>
    </head><body><h1>Sunrise Towers</h1></body></html>
    """
    result = extract_structured_data(html)
    assert result["propertyName"] == "Sunrise Towers"
    assert result["developerName"] == "ABC Builders"
    assert result["quotedPrice"] == 6600000.0
    assert result["areaValue"] == 1200.0
    assert result["areaUnit"] == "sqft"
    assert result["city"] == "Hyderabad"
    assert result["location"] == "Gachibowli"


def test_extract_structured_data_falls_back_to_open_graph_tags():
    """When there's no JSON-LD at all, Open Graph tags (also free, also
    commonly published for social-preview purposes) should still be read."""
    html = """
    <html><head>
    <meta property="og:title" content="Palm Residences Apartment" />
    <meta property="product:price:amount" content="4500000" />
    <meta property="og:locality" content="Pune" />
    </head><body></body></html>
    """
    result = extract_structured_data(html)
    assert result["propertyName"] == "Palm Residences Apartment"
    assert result["quotedPrice"] == 4500000.0
    assert result["city"] == "Pune"
    assert result["propertyType"] == "Apartment"


def test_extract_structured_data_returns_none_for_genuinely_absent_fields():
    """A page with no structured data at all should return every field as
    None — not guess, not fabricate, not throw."""
    html = "<html><head></head><body><p>Just some prose, no metadata.</p></body></html>"
    result = extract_structured_data(html)
    assert set(result.keys()) == set(EXTRACTABLE_FIELDS)
    assert all(v is None for v in result.values())


def test_extract_property_data_skips_llm_entirely_when_free_path_is_good_enough():
    """The core cost-saving behavior this whole rework exists for: when
    the free structured-data path already finds a name plus a real
    number, the paid LLM call must never happen at all."""
    html_with_good_jsonld = """
    <html><head>
    <script type="application/ld+json">
    {"@type": "Product", "name": "Sunrise Towers", "offers": {"price": "6600000"}}
    </script>
    </head><body></body></html>
    """
    with patch("backend.property_url_extract.ANTHROPIC_API_KEY", "fake_key_for_test"), \
         patch("backend.property_url_extract.fetch_page_html", return_value=html_with_good_jsonld), \
         patch("backend.property_url_extract.Anthropic") as mock_anthropic_cls:
        result = extract_property_data("https://example.com/listing/good-jsonld")

    mock_anthropic_cls.assert_not_called()
    assert result["propertyName"] == "Sunrise Towers"
    assert result["quotedPrice"] == 6600000.0


def test_extract_property_data_falls_back_to_llm_when_free_path_is_insufficient():
    """When the free path finds nothing usable, the paid LLM fallback
    should still kick in — this feature must keep working for sites
    without structured data, just at a real cost for those specific
    cases rather than always."""
    html_no_structured_data = "<html><body>" + ("Sunrise Towers by ABC Builders, 1200 sqft, priced at 6,600,000. " * 10) + "</body></html>"

    fake_claude_response = MagicMock()
    fake_claude_response.content = [MagicMock(text=json.dumps({
        "propertyName": "Sunrise Towers", "developerName": "ABC Builders",
        "quotedPrice": 6600000, "areaValue": 1200, "areaUnit": "sqft",
        "city": None, "location": None, "propertyType": None, "totalUnits": None, "monthlyRent": None,
    }))]

    with patch("backend.property_url_extract.ANTHROPIC_API_KEY", "fake_key_for_test"), \
         patch("backend.property_url_extract.fetch_page_html", return_value=html_no_structured_data), \
         patch("backend.property_url_extract.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = fake_claude_response
        mock_anthropic_cls.return_value = mock_client

        result = extract_property_data("https://example.com/listing/no-structured-data")

    mock_anthropic_cls.assert_called_once()
    assert result["propertyName"] == "Sunrise Towers"
    assert result["quotedPrice"] == 6600000


def test_extract_property_data_rejects_suspiciously_short_pages_before_llm_call():
    """A page with almost no text is a strong signal of a login wall or
    bot-block — worth failing clearly rather than sending near-empty
    content to the model."""
    with patch("backend.property_url_extract.ANTHROPIC_API_KEY", "fake_key_for_test"), \
         patch("backend.property_url_extract.fetch_page_html", return_value="<html><body>Sign in</body></html>"):
        with pytest.raises(ValueError, match="very little content"):
            extract_property_data("https://example.com/blocked")


def test_extract_property_data_returns_partial_free_result_when_no_api_key_configured():
    """No paid fallback configured shouldn't mean the feature fails
    outright — a partial free-path result is more useful than an error,
    and an admin may have deliberately left the LLM fallback off to keep
    this feature entirely free."""
    html_no_structured_data = "<html><body>" + ("Just some listing prose with no JSON-LD at all. " * 10) + "</body></html>"
    with patch("backend.property_url_extract.ANTHROPIC_API_KEY", ""), \
         patch("backend.property_url_extract.fetch_page_html", return_value=html_no_structured_data):
        result = extract_property_data("https://example.com/listing/no-key-no-structured-data")
    assert set(result.keys()) == set(EXTRACTABLE_FIELDS)


def test_extract_property_data_raises_clearly_on_invalid_json_response():
    """The model returning something that isn't valid JSON must be a
    clear, caught error — not a silent crash or a nonsense result passed
    through to the frontend."""
    html_no_structured_data = "<html><body>" + ("Some real-looking listing content here. " * 20) + "</body></html>"

    fake_claude_response = MagicMock()
    fake_claude_response.content = [MagicMock(text="I couldn't find a JSON object, sorry!")]

    with patch("backend.property_url_extract.ANTHROPIC_API_KEY", "fake_key_for_test"), \
         patch("backend.property_url_extract.fetch_page_html", return_value=html_no_structured_data), \
         patch("backend.property_url_extract.Anthropic") as mock_anthropic_cls:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = fake_claude_response
        mock_anthropic_cls.return_value = mock_client

        with pytest.raises(RuntimeError, match="did not return valid JSON"):
            extract_property_data("https://example.com/listing/bad-json")


def test_endpoint_requires_auth_and_feature():
    """Real end-to-end gating check: the endpoint itself, not just the
    underlying extraction function, must require auth and the
    property_url_import feature — matching every other tier feature's
    enforcement pattern."""
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

    no_tier = client.post("/api/property/extract-from-url", json={"url": "https://example.com/listing/1"}, headers=headers)
    assert no_tier.status_code == 403

    upsert_subscription(email=email, tier_id="studio_starter", dodo_subscription_id="sub_url_import_test", status="active")
    with patch("backend.api.extract_property_data", return_value={"propertyName": "Test Property"}):
        gated_ok = client.post("/api/property/extract-from-url", json={"url": "https://example.com/listing/1"}, headers=headers)
    assert gated_ok.status_code == 200
    assert gated_ok.json()["extracted"]["propertyName"] == "Test Property"

    bad_url = client.post("/api/property/extract-from-url", json={"url": "not-a-url"}, headers=headers)
    assert bad_url.status_code == 400


def test_extract_structured_data_skips_irrelevant_json_ld_blocks():
    """Real-world pages commonly have multiple JSON-LD blocks on one page
    (BreadcrumbList, Organization, WebSite schemas alongside the actual
    listing) — the parser must correctly skip irrelevant types and find
    the one that actually matters, not just grab the first block."""
    html = """
    <html><head>
    <script type="application/ld+json">
    {"@type": "BreadcrumbList", "itemListElement": []}
    </script>
    <script type="application/ld+json">
    {"@type": "Organization", "name": "Some Listing Website"}
    </script>
    <script type="application/ld+json">
    {"@type": "Product", "name": "Real Property Name", "offers": {"price": "5000000"}}
    </script>
    </head><body></body></html>
    """
    result = extract_structured_data(html)
    assert result["propertyName"] == "Real Property Name"
    assert result["quotedPrice"] == 5000000.0


def test_extract_structured_data_handles_json_ld_graph_array():
    """Some sites wrap multiple schema.org entities in a single JSON-LD
    block as a list — must be handled the same as separate blocks."""
    html = """
    <html><head>
    <script type="application/ld+json">
    [
      {"@type": "BreadcrumbList", "itemListElement": []},
      {"@type": "RealEstateListing", "name": "Villa in the Graph", "offers": {"price": "8000000"}}
    ]
    </script>
    </head><body></body></html>
    """
    result = extract_structured_data(html)
    assert result["propertyName"] == "Villa in the Graph"
    assert result["quotedPrice"] == 8000000.0


def test_extract_structured_data_survives_malformed_json_ld():
    """A broken/malformed JSON-LD block on the page must not crash the
    whole extraction — just get skipped, falling through to whatever
    else can be found."""
    html = """
    <html><head>
    <script type="application/ld+json">
    { this is not valid json at all
    </script>
    <meta property="og:title" content="Still Findable Property" />
    </head><body></body></html>
    """
    result = extract_structured_data(html)
    assert result["propertyName"] == "Still Findable Property"
