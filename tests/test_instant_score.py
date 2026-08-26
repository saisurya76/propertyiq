import pytest

from backend.instant_score import compute_instant_score


def test_honest_unsupported_result_for_unknown_city():
    """Must never fabricate a score for a city/type with no real
    comparable data — matching the same honesty standard as Similar
    Properties, using the exact same underlying comparables source."""
    result = compute_instant_score(
        price=5000000, city="SomeUnsupportedCity", property_type="Apartment", area_value=1200,
    )
    assert result["coverage"] == "unsupported"
    assert result["score"] is None
    assert result["label"] is None
    assert "doesn't have real comparable data" in result["reason"]


def test_score_at_exact_market_average_is_seventy():
    """The documented formula's anchor point: exactly at the market
    average should score 70 (borderline strong/investigate), not some
    arbitrary other number."""
    from backend.comparables import get_comparables, average_price_per_sqft
    comparables = get_comparables("Hyderabad", "Apartment")
    market_avg = average_price_per_sqft(comparables)

    area_sqft = 1200
    price_at_market_avg = market_avg * area_sqft

    result = compute_instant_score(
        price=price_at_market_avg, city="Hyderabad", property_type="Apartment", area_value=area_sqft,
    )
    assert result["coverage"] == "supported"
    assert result["score"] == 70
    assert result["label"] == "Investigate"


def test_underpriced_property_scores_high_and_labeled_strong():
    from backend.comparables import get_comparables, average_price_per_sqft
    comparables = get_comparables("Hyderabad", "Apartment")
    market_avg = average_price_per_sqft(comparables)

    area_sqft = 1200
    price_20_percent_below_market = market_avg * 0.80 * area_sqft

    result = compute_instant_score(
        price=price_20_percent_below_market, city="Hyderabad", property_type="Apartment", area_value=area_sqft,
    )
    assert result["label"] == "Strong"
    assert result["score"] > 70
    assert "below" in result["reason"]


def test_overpriced_property_scores_low_and_labeled_avoid():
    from backend.comparables import get_comparables, average_price_per_sqft
    comparables = get_comparables("Hyderabad", "Apartment")
    market_avg = average_price_per_sqft(comparables)

    area_sqft = 1200
    price_30_percent_above_market = market_avg * 1.30 * area_sqft

    result = compute_instant_score(
        price=price_30_percent_above_market, city="Hyderabad", property_type="Apartment", area_value=area_sqft,
    )
    assert result["label"] == "Avoid / Overpriced"
    assert result["score"] < 45
    assert "above" in result["reason"]


def test_score_is_clamped_to_valid_range_for_extreme_prices():
    result_extreme_low = compute_instant_score(
        price=1, city="Hyderabad", property_type="Apartment", area_value=1200,
    )
    assert 0 <= result_extreme_low["score"] <= 100

    result_extreme_high = compute_instant_score(
        price=999999999, city="Hyderabad", property_type="Apartment", area_value=1200,
    )
    assert 0 <= result_extreme_high["score"] <= 100
    assert result_extreme_high["score"] == 0


def test_sqm_area_is_converted_correctly():
    """A property described in sqm must produce the same result as the
    equivalent area in sqft — not silently treated as if the number were
    already in sqft, which would badly skew the price-per-sqft math."""
    result_sqft = compute_instant_score(
        price=12000000, city="Hyderabad", property_type="Apartment", area_value=1200, area_unit="sqft",
    )
    result_sqm = compute_instant_score(
        price=12000000, city="Hyderabad", property_type="Apartment", area_value=1200 / 10.7639, area_unit="sqm",
    )
    assert result_sqft["price_per_sqft"] == pytest.approx(result_sqm["price_per_sqft"], rel=0.01)
    assert result_sqft["score"] == result_sqm["score"]


def test_rejects_non_positive_price_or_area():
    with pytest.raises(ValueError):
        compute_instant_score(price=0, city="Hyderabad", property_type="Apartment", area_value=1200)
    with pytest.raises(ValueError):
        compute_instant_score(price=5000000, city="Hyderabad", property_type="Apartment", area_value=0)
    with pytest.raises(ValueError):
        compute_instant_score(price=-100, city="Hyderabad", property_type="Apartment", area_value=1200)


def test_endpoint_is_public_no_auth_required():
    """Explicitly matches the feature's design: unlike every other paid
    feature in this app, this one must work with zero account needed."""
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.post("/api/instant-score", json={
        "price": 12000000, "city": "Hyderabad", "property_type": "Apartment", "area_value": 1200,
    })
    assert r.status_code == 200
    assert r.json()["coverage"] == "supported"


def test_endpoint_rejects_non_positive_values_with_clear_message():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.post("/api/instant-score", json={
        "price": 0, "city": "Hyderabad", "property_type": "Apartment", "area_value": 1200,
    })
    assert r.status_code == 400
    assert "greater than zero" in r.json()["detail"]


def test_endpoint_rejects_invalid_area_unit():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.post("/api/instant-score", json={
        "price": 12000000, "city": "Hyderabad", "property_type": "Apartment",
        "area_value": 1200, "area_unit": "acres",
    })
    assert r.status_code == 400
    assert "sqft" in r.json()["detail"]
