import pytest

from backend.red_flag_hunt import evaluate_red_flag_guess, VALID_CATEGORIES


def test_rejects_invalid_category():
    with pytest.raises(ValueError):
        evaluate_red_flag_guess(
            price=5000000, city="Hyderabad", property_type="Apartment",
            area_value=1200, area_unit="sqft", guessed_category="NotARealCategory",
        )


def test_unsupported_city_returns_honest_unknown_verdict():
    result = evaluate_red_flag_guess(
        price=5000000, city="SomeUnsupportedCity", property_type="Apartment",
        area_value=1200, area_unit="sqft", guessed_category="Price",
    )
    assert result["coverage"] == "unsupported"
    assert result["verdict"] == "unknown"


def test_guessing_price_when_genuinely_overpriced_is_marked_correct():
    from backend.comparables import get_comparables, average_price_per_sqft
    comparables = get_comparables("Hyderabad", "Apartment")
    market_avg = average_price_per_sqft(comparables)
    overpriced = market_avg * 1.30 * 1200

    result = evaluate_red_flag_guess(
        price=overpriced, city="Hyderabad", property_type="Apartment",
        area_value=1200, area_unit="sqft", guessed_category="Price",
    )
    assert result["verdict"] == "correct"
    assert "Good catch" in result["verdict_detail"]


def test_guessing_price_when_actually_fairly_priced_is_a_false_alarm():
    from backend.comparables import get_comparables, average_price_per_sqft
    comparables = get_comparables("Hyderabad", "Apartment")
    market_avg = average_price_per_sqft(comparables)
    fair_price = market_avg * 1200  # at market average, no real anomaly

    result = evaluate_red_flag_guess(
        price=fair_price, city="Hyderabad", property_type="Apartment",
        area_value=1200, area_unit="sqft", guessed_category="Price",
    )
    assert result["verdict"] == "false_alarm"


def test_guessing_area_is_treated_the_same_as_price():
    """Price and Area are mathematically linked via price-per-sqft — a
    guess of either should be judged against the same real signal."""
    from backend.comparables import get_comparables, average_price_per_sqft
    comparables = get_comparables("Hyderabad", "Apartment")
    market_avg = average_price_per_sqft(comparables)
    overpriced = market_avg * 1.30 * 1200

    price_guess = evaluate_red_flag_guess(
        price=overpriced, city="Hyderabad", property_type="Apartment",
        area_value=1200, area_unit="sqft", guessed_category="Price",
    )
    area_guess = evaluate_red_flag_guess(
        price=overpriced, city="Hyderabad", property_type="Apartment",
        area_value=1200, area_unit="sqft", guessed_category="Area",
    )
    assert price_guess["verdict"] == area_guess["verdict"] == "correct"


@pytest.mark.parametrize("category", ["Builder", "Location", "Amenities", "Other"])
def test_categories_with_no_real_basis_get_honest_unknown_verdict(category):
    """Must never fabricate a correct/false-alarm judgment about
    something this quick check has zero actual data on."""
    result = evaluate_red_flag_guess(
        price=6000000, city="Hyderabad", property_type="Apartment",
        area_value=1200, area_unit="sqft", guessed_category=category,
    )
    assert result["verdict"] == "unknown"
    assert result["verdict_detail"]  # a real, non-empty explanation, not a blank


def test_additional_findings_includes_price_anomaly_when_user_missed_it():
    """If the user guessed something other than Price/Area, and there IS
    a genuine price anomaly, it should surface as an additional finding
    they should still investigate."""
    from backend.comparables import get_comparables, average_price_per_sqft
    comparables = get_comparables("Hyderabad", "Apartment")
    market_avg = average_price_per_sqft(comparables)
    overpriced = market_avg * 1.30 * 1200

    result = evaluate_red_flag_guess(
        price=overpriced, city="Hyderabad", property_type="Apartment",
        area_value=1200, area_unit="sqft", guessed_category="Builder",
    )
    titles = [f["title"] for f in result["additional_findings"]]
    assert "Pricing Anomaly" in titles
    assert "Risk / Missing Information" in titles


def test_additional_findings_omits_price_anomaly_when_not_genuinely_present():
    """Must not pad findings with a fabricated pricing concern when
    there genuinely isn't one — a real, honest gap in the findings list
    is correct, not a bug to paper over."""
    from backend.comparables import get_comparables, average_price_per_sqft
    comparables = get_comparables("Hyderabad", "Apartment")
    market_avg = average_price_per_sqft(comparables)
    fair_price = market_avg * 1200

    result = evaluate_red_flag_guess(
        price=fair_price, city="Hyderabad", property_type="Apartment",
        area_value=1200, area_unit="sqft", guessed_category="Builder",
    )
    titles = [f["title"] for f in result["additional_findings"]]
    assert "Pricing Anomaly" not in titles
    assert "Risk / Missing Information" in titles


def test_endpoint_is_public_no_auth_required():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.post("/api/red-flag-hunt", json={
        "price": 12000000, "city": "Hyderabad", "property_type": "Apartment",
        "area_value": 1200, "guessed_category": "Price",
    })
    assert r.status_code == 200
    assert r.json()["coverage"] == "supported"


def test_endpoint_rejects_invalid_category():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.post("/api/red-flag-hunt", json={
        "price": 12000000, "city": "Hyderabad", "property_type": "Apartment",
        "area_value": 1200, "guessed_category": "NotReal",
    })
    assert r.status_code == 400
    assert "guessed_category" in r.json()["detail"]


def test_endpoint_rejects_non_positive_values():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.post("/api/red-flag-hunt", json={
        "price": 0, "city": "Hyderabad", "property_type": "Apartment",
        "area_value": 1200, "guessed_category": "Price",
    })
    assert r.status_code == 400


def test_endpoint_passes_location_through_for_display():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.post("/api/red-flag-hunt", json={
        "price": 12000000, "city": "Hyderabad", "property_type": "Apartment",
        "area_value": 1200, "guessed_category": "Price", "location": "Gachibowli",
    })
    assert r.json()["location"] == "Gachibowli"
