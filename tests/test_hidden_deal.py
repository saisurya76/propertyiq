import pytest

from backend.hidden_deal import find_hidden_deal_insights


def test_unsupported_city_returns_only_the_honest_scope_finding():
    """No comparables data means no basis for a pricing/negotiation
    finding — must not fabricate one, only the finding that's true
    regardless of data coverage."""
    result = find_hidden_deal_insights(
        price=5000000, city="SomeUnsupportedCity", property_type="Apartment", area_value=1200,
    )
    assert result["coverage"] == "unsupported"
    assert len(result["findings"]) == 1
    assert result["findings"][0]["title"] == "Risk / Missing Information"


def test_overpriced_property_gets_three_real_findings():
    from backend.comparables import get_comparables, average_price_per_sqft
    comparables = get_comparables("Hyderabad", "Apartment")
    market_avg = average_price_per_sqft(comparables)
    area_sqft = 1200
    overpriced = market_avg * 1.30 * area_sqft

    result = find_hidden_deal_insights(
        price=overpriced, city="Hyderabad", property_type="Apartment", area_value=area_sqft,
    )
    assert result["coverage"] == "supported"
    assert len(result["findings"]) == 3
    titles = [f["title"] for f in result["findings"]]
    assert titles == ["Pricing Anomaly", "Risk / Missing Information", "Potential Negotiation Opportunity"]
    assert "above comparable" in result["findings"][0]["detail"]
    assert "room to negotiate" in result["findings"][2]["detail"]


def test_underpriced_property_gets_different_negotiation_framing():
    """A genuinely below-market price should NOT suggest negotiating
    further down — that would be a nonsensical, ungrounded finding."""
    from backend.comparables import get_comparables, average_price_per_sqft
    comparables = get_comparables("Hyderabad", "Apartment")
    market_avg = average_price_per_sqft(comparables)
    area_sqft = 1200
    underpriced = market_avg * 0.80 * area_sqft

    result = find_hidden_deal_insights(
        price=underpriced, city="Hyderabad", property_type="Apartment", area_value=area_sqft,
    )
    assert "below comparable" in result["findings"][0]["detail"]
    assert "move quickly" in result["findings"][2]["detail"]
    assert "room to negotiate" not in result["findings"][2]["detail"]


def test_fairly_priced_property_gets_neutral_findings():
    from backend.comparables import get_comparables, average_price_per_sqft
    comparables = get_comparables("Hyderabad", "Apartment")
    market_avg = average_price_per_sqft(comparables)
    area_sqft = 1200
    at_market = market_avg * area_sqft

    result = find_hidden_deal_insights(
        price=at_market, city="Hyderabad", property_type="Apartment", area_value=area_sqft,
    )
    assert "close to the market average" in result["findings"][0]["detail"]


def test_findings_include_the_underlying_score_for_context():
    from backend.comparables import get_comparables, average_price_per_sqft
    comparables = get_comparables("Hyderabad", "Apartment")
    market_avg = average_price_per_sqft(comparables)
    result = find_hidden_deal_insights(
        price=market_avg * 1200, city="Hyderabad", property_type="Apartment", area_value=1200,
    )
    assert result["score"] is not None
    assert result["label"] is not None


def test_rejects_invalid_input_same_as_instant_score():
    with pytest.raises(ValueError):
        find_hidden_deal_insights(price=0, city="Hyderabad", property_type="Apartment", area_value=1200)


def test_endpoint_is_public_no_auth_required():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.post("/api/hidden-deal", json={
        "price": 12000000, "city": "Hyderabad", "property_type": "Apartment", "area_value": 1200,
    })
    assert r.status_code == 200
    assert r.json()["coverage"] == "supported"
    assert len(r.json()["findings"]) == 3


def test_endpoint_rejects_non_positive_values():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.post("/api/hidden-deal", json={
        "price": 0, "city": "Hyderabad", "property_type": "Apartment", "area_value": 1200,
    })
    assert r.status_code == 400
    assert "greater than zero" in r.json()["detail"]


def test_endpoint_passes_location_through_for_display():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.post("/api/hidden-deal", json={
        "price": 12000000, "city": "Hyderabad", "property_type": "Apartment",
        "area_value": 1200, "location": "Gachibowli",
    })
    assert r.json()["location"] == "Gachibowli"


def test_endpoint_rejects_empty_city():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.post("/api/hidden-deal", json={
        "price": 9500000, "city": "", "property_type": "Apartment", "area_value": 1200,
    })
    assert r.status_code == 400
    assert r.json()["detail"] == "City is required."
