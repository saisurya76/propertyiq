import os

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from unittest.mock import patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app  # noqa: E402
from backend.neighborhood_comparison_store import (  # noqa: E402
    create_comparison,
    get_comparison,
    list_monitored_comparisons,
    MAX_AREAS_PER_COMPARISON,
)

client = TestClient(app)


def _area(city="Hyderabad", country="India", locality="Kompally", lat=17.4, lon=78.4):
    return {"city": city, "country": country, "locality": locality, "lat": lat, "lon": lon, "property_type": "Apartment"}


def test_create_comparison_requires_at_least_two_areas():
    r = client.post("/api/neighborhood-insights/compare", json={"areas": [_area()]})
    assert r.status_code == 400
    assert "at least 2" in r.json()["detail"]


def test_create_comparison_rejects_more_than_five_areas():
    areas = [_area(city=f"City{i}") for i in range(6)]
    r = client.post("/api/neighborhood-insights/compare", json={"areas": areas})
    assert r.status_code == 400
    assert "at most 5" in r.json()["detail"]


def test_create_comparison_fetches_real_data_for_each_area():
    """Confirms the comparison genuinely reuses the same real data
    sources the single-area page uses -- not a separate, fabricated
    pipeline."""
    areas = [_area(city="Hyderabad", locality="Kompally"), _area(city="Bangkok", country="Thailand", locality="Sukhumvit", lat=13.7, lon=100.5)]

    with patch("backend.api.neighborhood_nearby", return_value=[{"name": "fake river"}]):
        r = client.post("/api/neighborhood-insights/compare", json={"areas": areas})

    assert r.status_code == 200
    data = r.json()
    assert len(data["results"]) == 2
    assert data["results"][0]["city"] == "Hyderabad"
    assert data["results"][1]["city"] == "Bangkok"
    assert data["results"][0]["flood_risk"]["has_data"] is True
    assert data["results"][0]["flood_risk"]["nearby_water_count"] == 2  # river + water, both mocked to return 1 each
    assert "resale_signal" in data["results"][0]
    assert "infrastructure" in data["results"][0]
    assert data["monitoring"] is False


def test_comparison_is_reachable_instantly_after_creation():
    """The real "ready when the page loads" requirement: a comparison,
    once created, must be retrievable by ID with its already-fetched
    results, no re-fetching needed."""
    areas = [_area(city="Manila", country="Philippines"), _area(city="Jakarta", country="Indonesia")]
    with patch("backend.api.neighborhood_nearby", return_value=[]):
        created = client.post("/api/neighborhood-insights/compare", json={"areas": areas}).json()

    r = client.get(f"/api/neighborhood-insights/compare/{created['comparison_id']}")
    assert r.status_code == 200
    assert r.json()["comparison_id"] == created["comparison_id"]
    assert len(r.json()["results"]) == 2


def test_getting_a_nonexistent_comparison_returns_404():
    r = client.get("/api/neighborhood-insights/compare/does-not-exist")
    assert r.status_code == 404


def test_monitoring_can_be_turned_on_and_shows_up_for_the_scheduler():
    """Direct proof of the "keep monitoring" feature: toggling it on
    makes the comparison appear in the scheduler's own list of what to
    refresh; toggling it off removes it again."""
    areas = [_area(), _area(city="Vietnam City", country="Vietnam")]
    with patch("backend.api.neighborhood_nearby", return_value=[]):
        created = client.post("/api/neighborhood-insights/compare", json={"areas": areas}).json()
    comparison_id = created["comparison_id"]

    monitored_ids_before = [c["comparison_id"] for c in list_monitored_comparisons()]
    assert comparison_id not in monitored_ids_before

    r_on = client.post(f"/api/neighborhood-insights/compare/{comparison_id}/monitor", json={"monitoring": True})
    assert r_on.status_code == 200
    assert r_on.json()["monitoring"] is True

    monitored_ids_after = [c["comparison_id"] for c in list_monitored_comparisons()]
    assert comparison_id in monitored_ids_after

    r_off = client.post(f"/api/neighborhood-insights/compare/{comparison_id}/monitor", json={"monitoring": False})
    assert r_off.status_code == 200
    monitored_ids_final = [c["comparison_id"] for c in list_monitored_comparisons()]
    assert comparison_id not in monitored_ids_final


def test_monitoring_a_nonexistent_comparison_returns_404():
    r = client.post("/api/neighborhood-insights/compare/does-not-exist/monitor", json={"monitoring": True})
    assert r.status_code == 404


def test_manual_refresh_updates_the_results_and_timestamp():
    areas = [_area(), _area(city="Pune")]
    with patch("backend.api.neighborhood_nearby", return_value=[]):
        created = client.post("/api/neighborhood-insights/compare", json={"areas": areas}).json()

    original_refreshed_at = created["last_refreshed_at"]

    with patch("backend.api.neighborhood_nearby", return_value=[{"name": "new result"}]):
        refreshed = client.post(f"/api/neighborhood-insights/compare/{created['comparison_id']}/refresh").json()

    assert refreshed["last_refreshed_at"] >= original_refreshed_at
    assert refreshed["results"][0]["flood_risk"]["nearby_water_count"] == 2


def test_refreshing_a_nonexistent_comparison_returns_404():
    r = client.post("/api/neighborhood-insights/compare/does-not-exist/refresh")
    assert r.status_code == 404


def test_a_single_area_failing_does_not_break_the_whole_comparison():
    """A real resilience requirement: infrastructure/comparables data
    being unavailable for one area must not prevent the comparison
    from being created at all -- has_data=False for that piece, not a
    500 for the whole request."""
    areas = [_area(city="RealCityWithData"), _area(city="ObscureVillageNoDataAnywhere", country="Nowhereland")]
    with patch("backend.api.neighborhood_nearby", return_value=[]):
        r = client.post("/api/neighborhood-insights/compare", json={"areas": areas})

    assert r.status_code == 200
    assert len(r.json()["results"]) == 2


def test_store_max_areas_constant_matches_the_real_requirement():
    assert MAX_AREAS_PER_COMPARISON == 5


def test_currency_matches_the_areas_real_country_not_hardcoded_india():
    """The exact real bug reported: Bangkok, Thailand showed its price
    in INR because currency was hardcoded regardless of country."""
    areas = [_area(city="Hyderabad"), _area(city="Bangkok", country="Thailand", locality="Bangkok, Thailand", lat=13.7, lon=100.5)]
    with patch("backend.api.neighborhood_nearby", return_value=[]):
        r = client.post("/api/neighborhood-insights/compare", json={"areas": areas})
    assert r.status_code == 200
    data = r.json()
    assert data["results"][0]["resale_signal"]["currency"] == "INR"
    assert data["results"][1]["resale_signal"]["currency"] == "THB"


def test_locality_level_search_falls_back_to_the_parent_city_for_resale_data():
    """The other exact real bug reported: searching a specific
    locality/mandal (not the city itself) returned "No data" even
    though real data exists for the parent city it belongs to."""
    from backend.api import _resolve_comparables_city

    comps, resolved_city = _resolve_comparables_city(
        "Gandipet mandal", "Gandipet mandal, Hyderabad, Telangana, India", "Apartment"
    )
    assert len(comps) > 0
    assert resolved_city == "Hyderabad"

    comps2, resolved_city2 = _resolve_comparables_city(
        "Marredpally", "Marredpally, Hyderabad, Telangana, India", "Apartment"
    )
    assert len(comps2) > 0
    assert resolved_city2 == "Hyderabad"


def test_a_genuinely_unknown_locality_still_honestly_reports_no_data():
    """The fallback must not invent a match where none genuinely
    exists -- an area with no real parent-city match anywhere in its
    address stays has_data=False, not silently mapped to a wrong city."""
    from backend.api import _resolve_comparables_city

    comps, resolved_city = _resolve_comparables_city(
        "Nowhereville", "Nowhereville, Nowhereland", "Apartment"
    )
    assert comps == []


def test_comparison_endpoint_reflects_the_resolved_city_fallback():
    """End-to-end: a locality-level search through the real API
    endpoint gets real resale data via the parent-city fallback, not
    just at the unit-tested helper level."""
    areas = [
        {"city": "Gandipet mandal", "country": "India", "locality": "Gandipet mandal, Hyderabad, Telangana, India", "lat": 17.4, "lon": 78.3, "property_type": "Apartment"},
        {"city": "Marredpally", "country": "India", "locality": "Marredpally, Hyderabad, Telangana, India", "lat": 17.45, "lon": 78.5, "property_type": "Apartment"},
    ]
    with patch("backend.api.neighborhood_nearby", return_value=[]):
        r = client.post("/api/neighborhood-insights/compare", json={"areas": areas})
    assert r.status_code == 200
    data = r.json()
    for result in data["results"]:
        assert result["resale_signal"]["has_data"] is True
        assert result["resale_signal"]["resolved_city"] == "Hyderabad"
