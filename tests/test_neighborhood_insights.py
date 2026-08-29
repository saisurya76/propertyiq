from fastapi.testclient import TestClient

from backend.api import app

client = TestClient(app)


def test_resale_signal_returns_real_data_for_a_covered_city():
    r = client.get("/api/neighborhood-insights/resale-signal?city=Hyderabad&property_type=Apartment")
    assert r.status_code == 200
    data = r.json()
    # Hyderabad has real live data (per comparables.py's own live-data
    # path for Apartment) OR falls back to its real static snapshot --
    # either way, has_data must be true and count/average must be real,
    # non-fabricated numbers.
    assert data["has_data"] is True
    assert data["comparable_count"] >= 1
    assert data["average_price_per_sqft"] > 0
    assert data["data_source"] in ("live", "static_snapshot")


def test_resale_signal_honestly_reports_no_data_for_an_uncovered_city():
    """The real honesty guarantee: a city this app genuinely has no
    comparables for must say so plainly, not return a fabricated zero
    that looks like a real (if low) answer."""
    r = client.get("/api/neighborhood-insights/resale-signal?city=Nowheresville&property_type=Apartment")
    assert r.status_code == 200
    data = r.json()
    assert data["has_data"] is False
    assert data["comparable_count"] == 0
    assert data["average_price_per_sqft"] == 0
    assert data["data_source"] == "none"


def test_resale_signal_endpoint_is_genuinely_public_no_auth_required():
    """Matches instant_score's own established pattern -- a free,
    no-signup entry point, not a gated feature."""
    r = client.get("/api/neighborhood-insights/resale-signal?city=Hyderabad&property_type=Apartment")
    assert r.status_code == 200  # no Authorization header sent at all


def test_resale_signal_distinguishes_live_from_static_data_source():
    """Hyderabad + Apartment specifically exercises comparables.py's own
    live-data path when it succeeds -- confirms this endpoint correctly
    surfaces which kind of data backs the number, not just a bare count."""
    r = client.get("/api/neighborhood-insights/resale-signal?city=Hyderabad&property_type=Apartment")
    data = r.json()
    assert data["data_source"] in ("live", "static_snapshot")

    # A non-Apartment type never has a live-data path (per comparables.py's
    # own logic) -- if it has data at all, it must be the static snapshot.
    r2 = client.get("/api/neighborhood-insights/resale-signal?city=Hyderabad&property_type=Villa")
    data2 = r2.json()
    if data2["has_data"]:
        assert data2["data_source"] == "static_snapshot"
