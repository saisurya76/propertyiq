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


class _FakeResponse:
    """Minimal stand-in for requests.Response, used to mock LocationIQ's
    real HTTP responses without making a real network call in tests."""
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        return self._json_data


def test_autocomplete_proxies_locationiq_and_returns_its_real_shape(monkeypatch):
    """Confirms the endpoint genuinely forwards to LocationIQ's own
    /autocomplete (correct params) and passes its response straight
    through, matching the real shape AccidentIQ's own frontend code
    expects (display_name/lat/lon)."""
    monkeypatch.setenv("LOCATIONIQ_API_KEY", "pk.test_key_123")
    import backend.api as api_module
    monkeypatch.setattr(api_module, "LOCATIONIQ_API_KEY", "pk.test_key_123")

    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse(200, [{"display_name": "Banjara Hills, Hyderabad, India", "lat": "17.41", "lon": "78.43"}])

    monkeypatch.setattr(api_module.requests, "get", fake_get)

    r = client.get("/api/neighborhood-insights/autocomplete?q=Banjara+Hills")
    assert r.status_code == 200
    data = r.json()
    assert data[0]["display_name"] == "Banjara Hills, Hyderabad, India"
    assert captured["url"] == "https://us1.locationiq.com/v1/autocomplete"
    assert captured["params"]["key"] == "pk.test_key_123"
    assert captured["params"]["q"] == "Banjara Hills"
    assert captured["params"]["countrycodes"] == "in"


def test_autocomplete_honestly_returns_empty_for_too_short_a_query(monkeypatch):
    """Matches LocationIQ's own real minimum-length UX (AccidentIQ's own
    attachAutocomplete only fires past 3 characters) -- confirms this
    endpoint doesn't waste a real API call on an unusably short query."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "LOCATIONIQ_API_KEY", "pk.test_key_123")

    def fake_get(*a, **k):
        raise AssertionError("should not call LocationIQ for a too-short query")

    monkeypatch.setattr(api_module.requests, "get", fake_get)

    r = client.get("/api/neighborhood-insights/autocomplete?q=Ba")
    assert r.status_code == 200
    assert r.json() == []


def test_autocomplete_returns_503_when_key_is_not_configured(monkeypatch):
    import backend.api as api_module
    monkeypatch.setattr(api_module, "LOCATIONIQ_API_KEY", "")

    r = client.get("/api/neighborhood-insights/autocomplete?q=Banjara+Hills")
    assert r.status_code == 503


def test_nearby_proxies_locationiq_with_the_real_osm_tag_format(monkeypatch):
    """Confirms the endpoint forwards the real 'amenity:hospital' style
    tag (matching AccidentIQ's own POI_CATEGORIES format) unmodified."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "LOCATIONIQ_API_KEY", "pk.test_key_123")

    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["params"] = params
        return _FakeResponse(200, [{"name": "Apollo Hospital", "lat": "17.41", "lon": "78.43"}])

    monkeypatch.setattr(api_module.requests, "get", fake_get)

    r = client.get("/api/neighborhood-insights/nearby?lat=17.41&lon=78.43&tag=amenity:hospital")
    assert r.status_code == 200
    data = r.json()
    assert data[0]["name"] == "Apollo Hospital"
    assert captured["params"]["tag"] == "amenity:hospital"
    assert captured["params"]["lat"] == 17.41
    assert captured["params"]["radius"] == 2000  # the real default, matching AccidentIQ's own


def test_nearby_gracefully_returns_empty_on_a_locationiq_failure_not_a_crash(monkeypatch):
    """A real, important resilience property: if LocationIQ itself
    errors or times out, this must degrade to an empty result (letting
    the frontend fall back to its own Google Maps search link, same as
    AccidentIQ's own loadPOIs does) rather than surface a raw 500."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "LOCATIONIQ_API_KEY", "pk.test_key_123")

    import requests as requests_module

    def fake_get(*a, **k):
        raise requests_module.exceptions.Timeout("simulated timeout")

    monkeypatch.setattr(api_module.requests, "get", fake_get)

    r = client.get("/api/neighborhood-insights/nearby?lat=17.41&lon=78.43&tag=amenity:hospital")
    assert r.status_code == 200
    assert r.json() == []


def test_nearby_returns_503_when_key_is_not_configured(monkeypatch):
    import backend.api as api_module
    monkeypatch.setattr(api_module, "LOCATIONIQ_API_KEY", "")

    r = client.get("/api/neighborhood-insights/nearby?lat=17.41&lon=78.43&tag=amenity:hospital")
    assert r.status_code == 503


def test_both_new_endpoints_are_genuinely_public_no_auth_required(monkeypatch):
    import backend.api as api_module
    monkeypatch.setattr(api_module, "LOCATIONIQ_API_KEY", "pk.test_key_123")
    monkeypatch.setattr(api_module.requests, "get", lambda *a, **k: _FakeResponse(200, []))

    r1 = client.get("/api/neighborhood-insights/autocomplete?q=Test+Query")
    r2 = client.get("/api/neighborhood-insights/nearby?lat=17.41&lon=78.43&tag=amenity:hospital")
    assert r1.status_code == 200
    assert r2.status_code == 200
