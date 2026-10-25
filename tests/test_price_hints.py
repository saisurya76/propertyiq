import os

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app  # noqa: E402
from backend import price_hints  # noqa: E402

client = TestClient(app)


def _no_live(monkeypatch):
    monkeypatch.setattr("backend.live_comparables.get_live_price_per_sqft", lambda city: None)


def test_hyderabad_has_both_suggestions_and_converts_units(monkeypatch):
    _no_live(monkeypatch)
    sq = price_hints.get_hints("India", "Telangana", "Hyderabad", "Apartment", "sqft")
    m2 = price_hints.get_hints("India", "Telangana", "Hyderabad", "Apartment", "sq meter")
    assert sq["market"]["available"] and sq["government"]["available"]
    assert sq["government"]["value"] == 6500
    assert abs(m2["government"]["value"] - 6500 * 10.7639) < 10
    assert sq["market"]["low"] <= sq["market"]["value"] <= sq["market"]["high"]
    assert sq["currency"] == "INR"


def test_city_without_data_gets_a_how_to_not_a_made_up_number(monkeypatch):
    _no_live(monkeypatch)
    h = price_hints.get_hints("India", "Goa", "Panaji", "Apartment", "sqft", locality="Porvorim")
    assert h["market"]["available"] is False
    assert h["government"]["available"] is False
    how = h["government"]["how_to"]
    assert "Goa" in how["search_url"] and "Porvorim" in how["search_url"] and how["name"]


def test_other_countries_have_local_terms(monkeypatch):
    _no_live(monkeypatch)
    assert "NJOP" in price_hints.get_hints("Indonesia", "", "Jakarta", "Apartment", "sqft")["government"]["how_to"]["name"]
    assert "appraised" in price_hints.get_hints("Thailand", "", "Bangkok", "Apartment", "sqft")["government"]["how_to"]["name"]
    assert price_hints.get_hints("Thailand", "", "Bangkok", "Apartment", "sqft")["market"]["available"]


def test_endpoint_is_public_and_tolerates_junk(monkeypatch):
    _no_live(monkeypatch)
    r = client.get("/api/price-hints", params={"country": "India", "state_province": "Telangana", "city": "Hyderabad", "area_unit": "sq yard"})
    assert r.status_code == 200 and r.json()["area_unit"] == "sq yard"
    r = client.get("/api/price-hints", params={"country": "India", "city": "Hyderabad", "area_unit": "bogus"})
    assert r.status_code == 200 and r.json()["area_unit"] == "sqft"
    assert client.get("/api/price-hints").status_code == 200
