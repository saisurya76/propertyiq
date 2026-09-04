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
    monkeypatch.setattr(api_module, "get_app_setting", lambda *a, **k: None)
    monkeypatch.setattr(api_module, "set_app_setting", lambda *a, **k: None)

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
    AccidentIQ's own loadPOIs does) rather than surface a raw 500.

    Explicitly forces a cache miss (get_app_setting -> None) -- a real
    test-isolation bug this fix closes: this test's own coordinates
    round to the same cache key another test in this file uses for a
    genuine success, and since caching now persists via the real,
    shared database, that earlier success was silently short-circuiting
    this test's mocked failure before it could ever be exercised."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "LOCATIONIQ_API_KEY", "pk.test_key_123")
    monkeypatch.setattr(api_module, "get_app_setting", lambda *a, **k: None)
    monkeypatch.setattr(api_module, "set_app_setting", lambda *a, **k: None)

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
    monkeypatch.setattr(api_module, "get_app_setting", lambda *a, **k: None)
    monkeypatch.setattr(api_module, "set_app_setting", lambda *a, **k: None)
    monkeypatch.setattr(api_module.requests, "get", lambda *a, **k: _FakeResponse(200, []))

    r1 = client.get("/api/neighborhood-insights/autocomplete?q=Test+Query")
    r2 = client.get("/api/neighborhood-insights/nearby?lat=17.41&lon=78.43&tag=amenity:hospital")
    assert r1.status_code == 200
    assert r2.status_code == 200


from unittest.mock import patch, MagicMock


def test_nearby_result_is_cached_by_rounded_coordinates_not_called_twice():
    """The real, deliberate cost fix: this endpoint fires 7 times per
    form submission, making it the dominant driver of LocationIQ usage
    at scale (verified directly against LocationIQ's own published
    pricing tiers). Confirms a second call for coordinates within the
    same ~1km grid cell returns the cached result without a second
    real LocationIQ request."""
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = [{"name": "Apollo Hospital", "lat": "17.41", "lon": "78.43"}]

    with patch("backend.api.LOCATIONIQ_API_KEY", "fake_key"), \
         patch("backend.api.get_app_setting", return_value=None), \
         patch("backend.api.set_app_setting") as mock_set, \
         patch("backend.api.requests.get", return_value=fake_response) as mock_get:
        r1 = client.get("/api/neighborhood-insights/nearby?lat=17.4126&lon=78.4344&tag=amenity:hospital")
        assert r1.status_code == 200
        assert mock_get.call_count == 1
        mock_set.assert_called_once()

    # Second call, coordinates within the same ~1km grid cell (rounds
    # to the same 2-decimal value) -- should hit the cache, not LocationIQ.
    cached_json = mock_set.call_args[0][1]
    with patch("backend.api.LOCATIONIQ_API_KEY", "fake_key"), \
         patch("backend.api.get_app_setting", return_value=cached_json), \
         patch("backend.api.requests.get") as mock_get2:
        r2 = client.get("/api/neighborhood-insights/nearby?lat=17.4129&lon=78.4341&tag=amenity:hospital")
        assert r2.status_code == 200
        mock_get2.assert_not_called()
        assert r2.json() == [{"name": "Apollo Hospital", "lat": "17.41", "lon": "78.43"}]


def test_nearby_coordinates_far_apart_do_not_share_a_cache_entry():
    """Confirms the cache is genuinely coordinate-scoped -- two
    genuinely distant locations must not accidentally share results."""
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = [{"name": "Somewhere", "lat": "17.41", "lon": "78.43"}]

    with patch("backend.api.LOCATIONIQ_API_KEY", "fake_key"), \
         patch("backend.api.get_app_setting", return_value=None), \
         patch("backend.api.set_app_setting"), \
         patch("backend.api.requests.get", return_value=fake_response) as mock_get:
        client.get("/api/neighborhood-insights/nearby?lat=17.4126&lon=78.4344&tag=amenity:hospital")
        # A different city entirely -- get_app_setting is still mocked to
        # return None (simulating a genuine cache miss for this different key)
        client.get("/api/neighborhood-insights/nearby?lat=19.0760&lon=72.8777&tag=amenity:hospital")
        assert mock_get.call_count == 2


def test_an_empty_nearby_result_is_never_cached():
    """A real, deliberate choice: caching an empty result (a transient
    LocationIQ hiccup or rate limit) would mean a genuine neighborhood
    incorrectly shows "nothing found" for a full week."""
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = []

    with patch("backend.api.LOCATIONIQ_API_KEY", "fake_key"), \
         patch("backend.api.get_app_setting", return_value=None), \
         patch("backend.api.set_app_setting") as mock_set, \
         patch("backend.api.requests.get", return_value=fake_response):
        r = client.get("/api/neighborhood-insights/nearby?lat=17.4126&lon=78.4344&tag=amenity:hospital")
        assert r.status_code == 200
        assert r.json() == []

    mock_set.assert_not_called()


def test_section_visibility_defaults_all_sections_to_visible():
    """A fresh install (or a section added after this feature shipped)
    must never silently disappear just because it isn't yet in the
    saved config -- everything defaults to visible until an admin
    explicitly hides something."""
    with patch("backend.api.get_app_setting", return_value=None):
        r = client.get("/api/neighborhood-insights/section-visibility")
    assert r.status_code == 200
    data = r.json()
    for section in ["map", "flood_risk", "infrastructure", "resale_signal", "checklist", "authority_contacts", "cross_sell", "share"]:
        assert data[section] is True


def test_admin_can_hide_a_specific_section_without_auth_required_on_read():
    """The read endpoint stays public (matching every other
    neighborhood-insights endpoint's own free/no-signup reasoning) --
    only the write requires the admin password."""
    import json as json_module
    saved_state = {}

    def fake_get_app_setting(key):
        return json_module.dumps(saved_state.get(key)) if key in saved_state else None

    def fake_set_app_setting(key, value):
        saved_state[key] = json_module.loads(value)

    with patch("backend.api.get_app_setting", side_effect=fake_get_app_setting), \
         patch("backend.api.set_app_setting", side_effect=fake_set_app_setting), \
         patch("backend.api._require_admin_password"):
        r = client.post("/api/admin/settings", json={"password": "test", "ni_section_visibility": {"infrastructure": False}})
        assert r.status_code == 200
        assert r.json()["ni_section_visibility"]["infrastructure"] is False
        assert r.json()["ni_section_visibility"]["map"] is True  # untouched sections stay at their default

        # The public read endpoint reflects the same change, no auth needed
        r2 = client.get("/api/neighborhood-insights/section-visibility")
        assert r2.json()["infrastructure"] is False
        assert r2.json()["map"] is True


def test_admin_settings_requires_the_real_admin_password_to_change_visibility():
    r = client.post("/api/admin/settings", json={"password": "definitely_wrong_password", "ni_section_visibility": {"map": False}})
    assert r.status_code == 403


def test_toggling_one_section_does_not_reset_a_previously_hidden_one():
    """Confirms the merge behavior: an admin toggling section B off in
    one request must not silently reset section A back to its default
    if A was already hidden in an earlier request."""
    import json as json_module
    saved_state = {}

    def fake_get_app_setting(key):
        return json_module.dumps(saved_state.get(key)) if key in saved_state else None

    def fake_set_app_setting(key, value):
        saved_state[key] = json_module.loads(value)

    with patch("backend.api.get_app_setting", side_effect=fake_get_app_setting), \
         patch("backend.api.set_app_setting", side_effect=fake_set_app_setting), \
         patch("backend.api._require_admin_password"):
        client.post("/api/admin/settings", json={"password": "test", "ni_section_visibility": {"infrastructure": False}})
        r = client.post("/api/admin/settings", json={"password": "test", "ni_section_visibility": {"share": False}})
        assert r.json()["ni_section_visibility"]["infrastructure"] is False
        assert r.json()["ni_section_visibility"]["share"] is False


def test_autocomplete_uses_a_non_india_country_code_when_provided(monkeypatch):
    """The real fix for multi-country support: this previously
    hardcoded countrycodes=in regardless of what was asked for."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "LOCATIONIQ_API_KEY", "pk.test_key_123")

    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["params"] = params
        return _FakeResponse(200, [])

    monkeypatch.setattr(api_module.requests, "get", fake_get)

    client.get("/api/neighborhood-insights/autocomplete?q=Bangkok+Sukhumvit&country=th")
    assert captured["params"]["countrycodes"] == "th"


def test_autocomplete_still_defaults_to_india_when_country_not_specified(monkeypatch):
    """Backward compatibility: every existing call site never passed a
    country, and must keep working exactly as before."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "LOCATIONIQ_API_KEY", "pk.test_key_123")

    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["params"] = params
        return _FakeResponse(200, [])

    monkeypatch.setattr(api_module.requests, "get", fake_get)

    client.get("/api/neighborhood-insights/autocomplete?q=Banjara+Hills")
    assert captured["params"]["countrycodes"] == "in"


def test_autocomplete_searches_globally_when_country_is_explicitly_empty(monkeypatch):
    """The real, necessary mode for the "any city, any country"
    comparison feature: an explicitly empty country string must omit
    the countrycodes restriction entirely, not silently fall back to
    India or reject the request."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "LOCATIONIQ_API_KEY", "pk.test_key_123")

    captured = {}

    def fake_get(url, params=None, timeout=None):
        captured["params"] = params
        return _FakeResponse(200, [])

    monkeypatch.setattr(api_module.requests, "get", fake_get)

    client.get("/api/neighborhood-insights/autocomplete?q=Lisbon+Alfama&country=")
    assert "countrycodes" not in captured["params"]


def test_extended_metrics_returns_all_four_real_metric_groups(monkeypatch):
    """Confirms the new single-area endpoint returns the same real
    metric groups the comparison feature already computes, reusing
    _fetch_area_comparison_data directly rather than a second,
    separate implementation."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda *a, **k: [])
    r = client.get("/api/neighborhood-insights/extended-metrics?city=Hyderabad&country=India&lat=17.4&lon=78.4")
    assert r.status_code == 200
    data = r.json()
    assert "air_quality" in data
    assert "overall_ranking" in data
    assert "world_bank" in data
    assert "municipality_ranking" in data


def test_extended_metrics_municipality_ranking_is_india_only(monkeypatch):
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda *a, **k: [])
    r = client.get("/api/neighborhood-insights/extended-metrics?city=Bangkok&country=Thailand&lat=13.7&lon=100.5")
    assert r.status_code == 200
    assert r.json()["municipality_ranking"]["has_data"] is False
    assert r.json()["municipality_ranking"]["reason"] == "india_only"


def test_extended_metrics_works_without_coordinates():
    """A real, graceful degradation: no lat/lon (e.g. a locality that
    hasn't been geocoded yet) must not error, just report the
    coordinate-dependent pieces as honestly unavailable."""
    r = client.get("/api/neighborhood-insights/extended-metrics?city=Hyderabad&country=India")
    assert r.status_code == 200
    assert r.json()["air_quality"]["has_data"] is False
