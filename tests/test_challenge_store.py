import pytest

from backend.challenge_store import initialize_challenge_store, create_challenge, get_challenge, reveal_challenge_guess


def test_create_and_retrieve_a_challenge():
    initialize_challenge_store()
    challenge = create_challenge(price=6600000, city="Hyderabad", property_type="Apartment", area_value=1200)
    assert challenge["challenge_id"]
    assert len(challenge["challenge_id"]) == 10

    retrieved = get_challenge(challenge["challenge_id"])
    assert retrieved == challenge


def test_get_nonexistent_challenge_returns_none():
    initialize_challenge_store()
    assert get_challenge("this-does-not-exist-at-all") is None


def test_each_challenge_gets_a_unique_id():
    initialize_challenge_store()
    a = create_challenge(price=5000000, city="Hyderabad", property_type="Apartment", area_value=1000)
    b = create_challenge(price=5000000, city="Hyderabad", property_type="Apartment", area_value=1000)
    assert a["challenge_id"] != b["challenge_id"]


def test_rejects_non_positive_price_or_area():
    initialize_challenge_store()
    with pytest.raises(ValueError):
        create_challenge(price=0, city="Hyderabad", property_type="Apartment", area_value=1200)
    with pytest.raises(ValueError):
        create_challenge(price=5000000, city="Hyderabad", property_type="Apartment", area_value=0)


def test_rejects_invalid_area_unit():
    initialize_challenge_store()
    with pytest.raises(ValueError):
        create_challenge(price=5000000, city="Hyderabad", property_type="Apartment", area_value=1200, area_unit="acres")


def test_reveal_correctly_computes_fair_value_and_diff():
    from backend.comparables import get_comparables, average_price_per_sqft
    initialize_challenge_store()

    comparables = get_comparables("Hyderabad", "Apartment")
    market_avg = average_price_per_sqft(comparables)
    area_sqft = 1200
    challenge = create_challenge(price=market_avg * 1.10 * area_sqft, city="Hyderabad", property_type="Apartment", area_value=area_sqft)

    reveal = reveal_challenge_guess(challenge["challenge_id"], guessed_price=market_avg * area_sqft)

    assert reveal["coverage"] == "supported"
    assert reveal["fair_value"] == round(market_avg * area_sqft)
    assert reveal["guess_diff_percent"] == 0  # guessed exactly the fair value
    assert reveal["market_position"] in ("Strong", "Investigate", "Avoid / Overpriced")
    assert len(reveal["findings"]) == 3


def test_reveal_raises_for_nonexistent_challenge():
    initialize_challenge_store()
    with pytest.raises(ValueError, match="No challenge found"):
        reveal_challenge_guess("does-not-exist", guessed_price=5000000)


def test_reveal_rejects_non_positive_guess():
    initialize_challenge_store()
    challenge = create_challenge(price=5000000, city="Hyderabad", property_type="Apartment", area_value=1200)
    with pytest.raises(ValueError, match="greater than zero"):
        reveal_challenge_guess(challenge["challenge_id"], guessed_price=0)


def test_reveal_is_honest_for_unsupported_cities():
    initialize_challenge_store()
    challenge = create_challenge(price=5000000, city="SomeUnsupportedCity", property_type="Apartment", area_value=1200)
    reveal = reveal_challenge_guess(challenge["challenge_id"], guessed_price=4500000)
    assert reveal["coverage"] == "unsupported"
    assert "reason" in reveal


def test_endpoints_are_public_no_auth_required_full_flow():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)

    create_resp = client.post("/api/challenges", json={
        "price": 8000000, "city": "Hyderabad", "property_type": "Apartment", "area_value": 1200,
    })
    assert create_resp.status_code == 200
    challenge_id = create_resp.json()["challenge_id"]

    get_resp = client.get(f"/api/challenges/{challenge_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["city"] == "Hyderabad"

    guess_resp = client.post(f"/api/challenges/{challenge_id}/guess", json={"guessed_price": 7000000})
    assert guess_resp.status_code == 200
    assert guess_resp.json()["coverage"] == "supported"
    assert "fair_value" in guess_resp.json()


def test_get_nonexistent_challenge_returns_404():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.get("/api/challenges/totally-fake-id")
    assert r.status_code == 404


def test_guess_on_nonexistent_challenge_returns_404():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.post("/api/challenges/totally-fake-id/guess", json={"guessed_price": 5000000})
    assert r.status_code == 404


def test_create_challenge_rejects_invalid_input_with_400():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.post("/api/challenges", json={
        "price": 0, "city": "Hyderabad", "property_type": "Apartment", "area_value": 1200,
    })
    assert r.status_code == 400


def test_endpoint_creates_and_reveals_challenge_with_location():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    create_resp = client.post("/api/challenges", json={
        "price": 9500000, "city": "Hyderabad", "property_type": "Apartment",
        "area_value": 1200, "location": "Gachibowli",
    })
    assert create_resp.status_code == 200
    assert create_resp.json()["location"] == "Gachibowli"

    challenge_id = create_resp.json()["challenge_id"]
    get_resp = client.get(f"/api/challenges/{challenge_id}")
    assert get_resp.json()["location"] == "Gachibowli"

    guess_resp = client.post(f"/api/challenges/{challenge_id}/guess", json={"guessed_price": 8500000})
    assert guess_resp.json()["challenge"]["location"] == "Gachibowli"


def test_rejects_empty_or_whitespace_city():
    initialize_challenge_store()
    for bad_city in ["", "   "]:
        with pytest.raises(ValueError, match="City is required"):
            create_challenge(price=5000000, city=bad_city, property_type="Apartment", area_value=1200)


def test_rejects_empty_or_whitespace_property_type():
    initialize_challenge_store()
    for bad_type in ["", "   "]:
        with pytest.raises(ValueError, match="Property type is required"):
            create_challenge(price=5000000, city="Hyderabad", property_type=bad_type, area_value=1200)
