import os

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from unittest.mock import patch  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app  # noqa: E402
from backend.auth_store import create_otp  # noqa: E402
from backend.subscription_store import upsert_subscription  # noqa: E402
from backend.neighborhood_comparison_store import (  # noqa: E402
    create_comparison,
    get_comparison,
    list_monitored_comparisons,
    MAX_AREAS_PER_COMPARISON,
)

client = TestClient(app)


def _authed_headers(email: str) -> dict:
    code = create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    token = r.json()["session_token"]
    return {"Authorization": f"Bearer {token}"}


def _entitled_headers(email: str, tier_id: str = "studio_pro") -> dict:
    """A real, active subscription whose tier genuinely includes the
    area_comparison feature — the actual gate the comparison endpoints
    check, not just a signed-in session."""
    upsert_subscription(email=email, tier_id=tier_id, status="active", dodo_subscription_id=f"sub_{email}")
    return _authed_headers(email)


def _area(city="Hyderabad", country="India", locality="Kompally", lat=17.4, lon=78.4):
    return {"city": city, "country": country, "locality": locality, "lat": lat, "lon": lon, "property_type": "Apartment"}


def test_create_comparison_requires_at_least_two_areas():
    headers = _entitled_headers("twoareas@example.com")
    r = client.post("/api/neighborhood-insights/compare", json={"areas": [_area()]}, headers=headers)
    assert r.status_code == 400
    assert "at least 2" in r.json()["detail"]


def test_create_comparison_rejects_more_than_five_areas():
    headers = _entitled_headers("fiveareas@example.com")
    areas = [_area(city=f"City{i}") for i in range(6)]
    r = client.post("/api/neighborhood-insights/compare", json={"areas": areas}, headers=headers)
    assert r.status_code == 400
    assert "at most 5" in r.json()["detail"]


def test_create_comparison_fetches_real_data_for_each_area():
    """Confirms the comparison genuinely reuses the same real data
    sources the single-area page uses -- not a separate, fabricated
    pipeline."""
    headers = _entitled_headers("realdata@example.com")
    areas = [_area(city="Hyderabad", locality="Kompally"), _area(city="Bangkok", country="Thailand", locality="Sukhumvit", lat=13.7, lon=100.5)]

    with patch("backend.api.neighborhood_nearby", return_value=[{"name": "fake river"}]):
        r = client.post("/api/neighborhood-insights/compare", json={"areas": areas}, headers=headers)

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
    headers = _entitled_headers("reachable@example.com")
    areas = [_area(city="Manila", country="Philippines"), _area(city="Jakarta", country="Indonesia")]
    with patch("backend.api.neighborhood_nearby", return_value=[]):
        created = client.post("/api/neighborhood-insights/compare", json={"areas": areas}, headers=headers).json()

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
    refresh; toggling it off removes it again. Turning ON requires the
    real entitlement (the paid gate); turning OFF never does."""
    headers = _entitled_headers("monitortest@example.com")
    areas = [_area(), _area(city="Vietnam City", country="Vietnam")]
    with patch("backend.api.neighborhood_nearby", return_value=[]):
        created = client.post("/api/neighborhood-insights/compare", json={"areas": areas}, headers=headers).json()
    comparison_id = created["comparison_id"]

    monitored_ids_before = [c["comparison_id"] for c in list_monitored_comparisons()]
    assert comparison_id not in monitored_ids_before

    r_on = client.post(f"/api/neighborhood-insights/compare/{comparison_id}/monitor", json={"monitoring": True}, headers=headers)
    assert r_on.status_code == 200
    assert r_on.json()["monitoring"] is True

    monitored_ids_after = [c["comparison_id"] for c in list_monitored_comparisons()]
    assert comparison_id in monitored_ids_after

    # Turning off requires no auth at all -- stopping an ongoing cost is
    # never paywalled.
    r_off = client.post(f"/api/neighborhood-insights/compare/{comparison_id}/monitor", json={"monitoring": False})
    assert r_off.status_code == 200
    monitored_ids_final = [c["comparison_id"] for c in list_monitored_comparisons()]
    assert comparison_id not in monitored_ids_final


def test_turning_monitoring_on_without_entitlement_is_rejected():
    """The real, direct proof of the paid gate on monitoring
    specifically: a signed-in visitor with no active/qualifying
    subscription cannot turn monitoring on, even for a comparison that
    already exists."""
    headers = _entitled_headers("willturnon@example.com")
    areas = [_area(), _area(city="Pune")]
    with patch("backend.api.neighborhood_nearby", return_value=[]):
        created = client.post("/api/neighborhood-insights/compare", json={"areas": areas}, headers=headers).json()

    unentitled_headers = _authed_headers("notsubscribed@example.com")
    r = client.post(
        f"/api/neighborhood-insights/compare/{created['comparison_id']}/monitor",
        json={"monitoring": True}, headers=unentitled_headers,
    )
    assert r.status_code == 403


def test_monitoring_a_nonexistent_comparison_returns_404():
    headers = _entitled_headers("monitor404@example.com")
    r = client.post("/api/neighborhood-insights/compare/does-not-exist/monitor", json={"monitoring": True}, headers=headers)
    assert r.status_code == 404


def test_manual_refresh_updates_the_results_and_timestamp():
    headers = _entitled_headers("refreshtest@example.com")
    areas = [_area(), _area(city="Pune")]
    with patch("backend.api.neighborhood_nearby", return_value=[]):
        created = client.post("/api/neighborhood-insights/compare", json={"areas": areas}, headers=headers).json()

    original_refreshed_at = created["last_refreshed_at"]

    with patch("backend.api.neighborhood_nearby", return_value=[{"name": "new result"}]):
        refreshed = client.post(f"/api/neighborhood-insights/compare/{created['comparison_id']}/refresh", headers=headers).json()

    assert refreshed["last_refreshed_at"] >= original_refreshed_at
    assert refreshed["results"][0]["flood_risk"]["nearby_water_count"] == 2


def test_refreshing_a_nonexistent_comparison_returns_404():
    headers = _entitled_headers("refresh404@example.com")
    r = client.post("/api/neighborhood-insights/compare/does-not-exist/refresh", headers=headers)
    assert r.status_code == 404


def test_a_single_area_failing_does_not_break_the_whole_comparison():
    """A real resilience requirement: infrastructure/comparables data
    being unavailable for one area must not prevent the comparison
    from being created at all -- has_data=False for that piece, not a
    500 for the whole request."""
    headers = _entitled_headers("singlefail@example.com")
    areas = [_area(city="RealCityWithData"), _area(city="ObscureVillageNoDataAnywhere", country="Nowhereland")]
    with patch("backend.api.neighborhood_nearby", return_value=[]):
        r = client.post("/api/neighborhood-insights/compare", json={"areas": areas}, headers=headers)

    assert r.status_code == 200
    assert len(r.json()["results"]) == 2


def test_store_max_areas_constant_matches_the_real_requirement():
    assert MAX_AREAS_PER_COMPARISON == 5


def test_currency_matches_the_areas_real_country_not_hardcoded_india():
    """The exact real bug reported: Bangkok, Thailand showed its price
    in INR because currency was hardcoded regardless of country."""
    headers = _entitled_headers("currencytest@example.com")
    areas = [_area(city="Hyderabad"), _area(city="Bangkok", country="Thailand", locality="Bangkok, Thailand", lat=13.7, lon=100.5)]
    with patch("backend.api.neighborhood_nearby", return_value=[]):
        r = client.post("/api/neighborhood-insights/compare", json={"areas": areas}, headers=headers)
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
    headers = _entitled_headers("resolvedcity@example.com")
    with patch("backend.api.neighborhood_nearby", return_value=[]):
        r = client.post("/api/neighborhood-insights/compare", json={"areas": areas}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    for result in data["results"]:
        assert result["resale_signal"]["has_data"] is True
        assert result["resale_signal"]["resolved_city"] == "Hyderabad"


def test_air_quality_returns_not_configured_when_no_api_key(monkeypatch):
    """Honest, real behavior: with no OpenWeather key set, air quality
    reports itself as unavailable rather than silently returning
    fabricated numbers."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "OPENWEATHER_API_KEY", "")
    result = api_module._fetch_air_quality(17.4, 78.4)
    assert result["has_data"] is False
    assert result["reason"] == "not_configured"


def test_air_quality_parses_a_real_openweather_response_shape(monkeypatch):
    """Confirms the parsing matches OpenWeather's actual, real Air
    Pollution API response shape (main.aqi 1-5 scale + components)."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "OPENWEATHER_API_KEY", "fake_key_123")
    monkeypatch.setattr(api_module, "_get_cached_json", lambda *a, **k: None)
    monkeypatch.setattr(api_module, "_set_cached_json", lambda *a, **k: None)

    class FakeResp:
        status_code = 200
        def json(self):
            return {"list": [{"main": {"aqi": 4}, "components": {"pm2_5": 55.2, "pm10": 88.1, "co": 500, "no2": 20, "o3": 60, "so2": 5, "nh3": 1}}]}

    monkeypatch.setattr(api_module.requests, "get", lambda *a, **k: FakeResp())
    result = api_module._fetch_air_quality(13.7, 100.5)
    assert result["has_data"] is True
    assert result["aqi"] == 4
    assert result["aqi_label"] == "Poor"
    assert result["pm2_5"] == 55.2


def test_air_quality_handles_a_real_fetch_failure_honestly(monkeypatch):
    import backend.api as api_module
    monkeypatch.setattr(api_module, "OPENWEATHER_API_KEY", "fake_key_123")
    monkeypatch.setattr(api_module, "_get_cached_json", lambda *a, **k: None)

    class FakeResp:
        status_code = 500
        def json(self):
            return {}

    monkeypatch.setattr(api_module.requests, "get", lambda *a, **k: FakeResp())
    result = api_module._fetch_air_quality(13.7, 100.5)
    assert result["has_data"] is False
    assert result["reason"] == "fetch_failed"


def test_overall_ranking_is_computed_only_from_genuinely_available_metrics():
    from backend.api import _compute_overall_ranking

    resale = {"has_data": True, "comparable_count": 10}
    air_quality = {"has_data": True, "aqi": 1}
    flood_risk = {"has_data": True, "nearby_water_count": 0}
    infrastructure = {"has_data": True}

    result = _compute_overall_ranking(resale, air_quality, flood_risk, infrastructure)
    assert result["has_data"] is True
    assert 0 <= result["score"] <= 100
    assert "resale market activity" in result["contributors"]
    assert "air quality" in result["contributors"]
    assert "flood-risk proximity" in result["contributors"]
    assert "infrastructure news activity" in result["contributors"]


def test_overall_ranking_scores_worse_air_quality_lower():
    from backend.api import _compute_overall_ranking

    no_data = {"has_data": False}
    good_air = _compute_overall_ranking(no_data, {"has_data": True, "aqi": 1}, no_data, no_data)
    bad_air = _compute_overall_ranking(no_data, {"has_data": True, "aqi": 5}, no_data, no_data)
    assert good_air["score"] > bad_air["score"]


def test_overall_ranking_honest_when_nothing_is_available():
    from backend.api import _compute_overall_ranking

    no_data = {"has_data": False}
    result = _compute_overall_ranking(no_data, no_data, no_data, no_data)
    assert result["has_data"] is False
    assert result["contributors"] == []


def test_comparison_endpoint_includes_air_quality_and_overall_ranking(monkeypatch):
    """End-to-end: the real comparison endpoint response includes both
    new fields, not just the underlying helper functions in isolation."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "OPENWEATHER_API_KEY", "")  # not configured is fine -- still must appear, honestly empty
    headers = _entitled_headers("airqualitytest@example.com")
    areas = [_area(city="Hyderabad"), _area(city="Pune")]
    with patch("backend.api.neighborhood_nearby", return_value=[]):
        r = client.post("/api/neighborhood-insights/compare", json={"areas": areas}, headers=headers)
    assert r.status_code == 200
    for result in r.json()["results"]:
        assert "air_quality" in result
        assert "overall_ranking" in result
        assert result["air_quality"]["has_data"] is False  # no key configured in this test env


def test_world_bank_indicators_parses_a_real_response_shape(monkeypatch):
    """Confirms parsing matches the World Bank API's actual, documented
    response shape: a 2-element array, [0]=metadata, [1]=list of
    entries with value/date."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "_get_cached_json", lambda *a, **k: None)
    monkeypatch.setattr(api_module, "_set_cached_json", lambda *a, **k: None)

    def fake_get(url, params=None, timeout=None):
        class FakeResp:
            status_code = 200
            def json(self):
                if "SL.UEM.TOTL.ZS" in url:
                    return [{"page": 1}, [{"value": 7.3, "date": "2024"}]]
                if "NY.GDP.MKTP.KD.ZG" in url:
                    return [{"page": 1}, [{"value": 6.1, "date": "2024"}]]
                if "ST.INT.ARVL" in url:
                    return [{"page": 1}, [{"value": 18000000, "date": "2023"}]]
                if "SP.DYN.LE00.IN" in url:
                    return [{"page": 1}, [{"value": 70.2, "date": "2022"}]]
                return [{"page": 1}, []]
        return FakeResp()

    monkeypatch.setattr(api_module.requests, "get", fake_get)
    result = api_module._fetch_world_bank_indicators("India")
    assert result["has_data"] is True
    assert result["unemployment_rate"]["value"] == 7.3
    assert result["gdp_growth"]["value"] == 6.1
    assert result["tourist_arrivals"]["value"] == 18000000
    assert result["life_expectancy"]["value"] == 70.2


def test_world_bank_indicators_honest_for_unrecognized_country():
    from backend.api import _fetch_world_bank_indicators
    result = _fetch_world_bank_indicators("Atlantis")
    assert result["has_data"] is False
    assert result["reason"] == "country_not_recognized"


def test_world_bank_indicators_handles_a_real_fetch_failure(monkeypatch):
    import backend.api as api_module
    monkeypatch.setattr(api_module, "_get_cached_json", lambda *a, **k: None)

    def fake_get(*a, **k):
        raise api_module.requests.RequestException("network error")

    monkeypatch.setattr(api_module.requests, "get", fake_get)
    result = api_module._fetch_world_bank_indicators("Thailand")
    assert result["has_data"] is False
    assert result["reason"] == "fetch_failed"


def test_comparison_endpoint_includes_world_bank_data(monkeypatch):
    """End-to-end: the real comparison endpoint response includes the
    world_bank field."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "_get_cached_json", lambda *a, **k: None)
    monkeypatch.setattr(api_module, "_set_cached_json", lambda *a, **k: None)

    class FakeJsonResp:
        status_code = 200
        def json(self):
            return [{"page": 1}, [{"value": 5.0, "date": "2024"}]]

    class FakeCsvResp:
        status_code = 200
        content = b"Rank,State/UT Name,ULB Name,Total Score (12500)\n1,X,Y,100\n"

    def fake_get(url, params=None, timeout=None):
        return FakeCsvResp() if "opencity.in" in url else FakeJsonResp()

    monkeypatch.setattr(api_module.requests, "get", fake_get)
    headers = _entitled_headers("worldbanktest@example.com")
    areas = [_area(city="Hyderabad"), _area(city="Pune")]
    with patch("backend.api.neighborhood_nearby", return_value=[]):
        r = client.post("/api/neighborhood-insights/compare", json={"areas": areas}, headers=headers)
    assert r.status_code == 200
    for result in r.json()["results"]:
        assert "world_bank" in result
        assert result["world_bank"]["has_data"] is True


_REAL_SWACHH_SURVEKSHAN_CSV = ("Rank,State/UT Name,ULB Name,Total Score (12500),SS2024(10000),SS2025(2500),ODF(1200)\n"
    "1,GUJARAT,AHMEDABAD,12079,9579,1300,1200\n"
    "6,TELANGANA,GREATER HYDERABAD,11805,9350,1300,1200\n"
    "36,KARNATAKA,BRUHAT BENGALURU MAHANAGARA PALIKE,6842,6247,0,1200\n"
).encode("utf-8-sig")


def test_municipality_ranking_india_only():
    from backend.api import _fetch_municipality_ranking
    result = _fetch_municipality_ranking("Bangkok", "Thailand")
    assert result["has_data"] is False
    assert result["reason"] == "india_only"


def test_municipality_ranking_matches_real_csv_data(monkeypatch):
    """Confirms parsing against the ACTUAL, real CSV content fetched
    from the live data source, including a real alias case (Hyderabad
    -> "Greater Hyderabad" in the official ranking)."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "_get_cached_json", lambda *a, **k: None)
    monkeypatch.setattr(api_module, "_set_cached_json", lambda *a, **k: None)

    class FakeResp:
        status_code = 200
        content = _REAL_SWACHH_SURVEKSHAN_CSV

    monkeypatch.setattr(api_module.requests, "get", lambda *a, **k: FakeResp())

    result = api_module._fetch_municipality_ranking("Hyderabad", "India")
    assert result["has_data"] is True
    assert result["rank"] == 6
    assert result["ulb_name"] == "GREATER HYDERABAD"
    assert result["total_cities_ranked"] == 3


def test_municipality_ranking_bangalore_alias(monkeypatch):
    import backend.api as api_module
    monkeypatch.setattr(api_module, "_get_cached_json", lambda *a, **k: None)
    monkeypatch.setattr(api_module, "_set_cached_json", lambda *a, **k: None)

    class FakeResp:
        status_code = 200
        content = _REAL_SWACHH_SURVEKSHAN_CSV

    monkeypatch.setattr(api_module.requests, "get", lambda *a, **k: FakeResp())
    result = api_module._fetch_municipality_ranking("Bangalore", "India")
    assert result["has_data"] is True
    assert result["rank"] == 36


def test_municipality_ranking_honest_for_a_city_not_in_the_survey(monkeypatch):
    import backend.api as api_module
    monkeypatch.setattr(api_module, "_get_cached_json", lambda *a, **k: None)
    monkeypatch.setattr(api_module, "_set_cached_json", lambda *a, **k: None)

    class FakeResp:
        status_code = 200
        content = _REAL_SWACHH_SURVEKSHAN_CSV

    monkeypatch.setattr(api_module.requests, "get", lambda *a, **k: FakeResp())
    result = api_module._fetch_municipality_ranking("SomeSmallTownNotSurveyed", "India")
    assert result["has_data"] is False
    assert result["reason"] == "city_not_in_ranking"


def test_municipality_ranking_handles_fetch_failure(monkeypatch):
    import backend.api as api_module
    monkeypatch.setattr(api_module, "_get_cached_json", lambda *a, **k: None)

    def fake_get(*a, **k):
        raise api_module.requests.RequestException("network down")

    monkeypatch.setattr(api_module.requests, "get", fake_get)
    result = api_module._fetch_municipality_ranking("Hyderabad", "India")
    assert result["has_data"] is False
    assert result["reason"] == "fetch_failed"


def test_comparison_endpoint_includes_municipality_ranking(monkeypatch):
    import backend.api as api_module
    monkeypatch.setattr(api_module, "_get_cached_json", lambda *a, **k: None)
    monkeypatch.setattr(api_module, "_set_cached_json", lambda *a, **k: None)

    class FakeCsvResp:
        status_code = 200
        content = _REAL_SWACHH_SURVEKSHAN_CSV

    class FakeJsonResp:
        status_code = 200
        def json(self):
            return [{"page": 1}, [{"value": 5.0, "date": "2024"}]]

    def fake_get(url, *a, **k):
        return FakeCsvResp() if "opencity.in" in url else FakeJsonResp()

    monkeypatch.setattr(api_module.requests, "get", fake_get)
    headers = _entitled_headers("municipalitytest@example.com")
    areas = [_area(city="Hyderabad"), _area(city="Bangkok", country="Thailand")]
    with patch("backend.api.neighborhood_nearby", return_value=[]):
        r = client.post("/api/neighborhood-insights/compare", json={"areas": areas}, headers=headers)
    assert r.status_code == 200
    results = r.json()["results"]
    assert results[0]["municipality_ranking"]["has_data"] is True
    assert results[1]["municipality_ranking"]["has_data"] is False
    assert results[1]["municipality_ranking"]["reason"] == "india_only"


def test_create_comparison_requires_authentication():
    """The real, direct proof this is now a paid, tier-gated feature:
    no session at all is rejected, not silently treated as public."""
    r = client.post("/api/neighborhood-insights/compare", json={"areas": [_area(), _area(city="Pune")]})
    assert r.status_code == 401


def test_create_comparison_rejects_a_signed_in_visitor_with_no_subscription():
    headers = _authed_headers("nosubscription@example.com")
    r = client.post("/api/neighborhood-insights/compare", json={"areas": [_area(), _area(city="Pune")]}, headers=headers)
    assert r.status_code == 403
    assert "area comparison" in r.json()["detail"]


def test_create_comparison_rejects_a_tier_without_the_feature_enabled(monkeypatch):
    """A real, subscribed customer whose specific tier has had this
    feature disabled by an admin must still be rejected -- has_feature,
    not just has_any_subscription."""
    import backend.config_store as config_module
    email = "disabledfeature@example.com"
    headers = _entitled_headers(email, tier_id="studio_starter")

    # Simulate an admin having turned area_comparison off for this tier.
    tiers = config_module.get_all_tiers_merged()
    tiers["studio_starter"]["features"] = [f for f in tiers["studio_starter"]["features"] if f != "area_comparison"]
    monkeypatch.setattr(config_module, "get_tier_config", lambda: tiers)

    r = client.post("/api/neighborhood-insights/compare", json={"areas": [_area(), _area(city="Pune")]}, headers=headers)
    assert r.status_code == 403


def test_refresh_requires_authentication():
    r = client.post("/api/neighborhood-insights/compare/does-not-exist/refresh")
    assert r.status_code == 401


def test_viewing_an_existing_comparison_stays_free_no_login_required():
    """The real, deliberate exception: viewing a comparison someone
    else created and shared costs nothing and needs no login, matching
    how a shared report link works elsewhere in the app."""
    headers = _entitled_headers("viewsharer@example.com")
    with patch("backend.api.neighborhood_nearby", return_value=[]):
        created = client.post(
            "/api/neighborhood-insights/compare",
            json={"areas": [_area(), _area(city="Pune")]}, headers=headers,
        ).json()

    r = client.get(f"/api/neighborhood-insights/compare/{created['comparison_id']}")
    assert r.status_code == 200


def test_scheduler_disables_monitoring_when_creator_loses_entitlement():
    """Direct proof of the real business-rule fix: a comparison whose
    creator's subscription has since lapsed must have its monitoring
    automatically turned off by the scheduler, not keep refreshing for
    free forever."""
    import asyncio
    from backend.neighborhood_comparison_scheduler import _refresh_one_comparison
    from backend.subscription_store import upsert_subscription

    email = "lapsedsubscriber@example.com"
    headers = _entitled_headers(email)
    with patch("backend.api.neighborhood_nearby", return_value=[]):
        created = client.post(
            "/api/neighborhood-insights/compare",
            json={"areas": [_area(), _area(city="Pune")]}, headers=headers,
        ).json()
    client.post(f"/api/neighborhood-insights/compare/{created['comparison_id']}/monitor", json={"monitoring": True}, headers=headers)

    # Simulate the subscription lapsing.
    upsert_subscription(email=email, tier_id="studio_pro", status="cancelled", dodo_subscription_id=f"sub_{email}")

    comparison = get_comparison(created["comparison_id"])
    with patch("backend.api.neighborhood_nearby", return_value=[]):
        asyncio.run(_refresh_one_comparison(comparison))

    updated = get_comparison(created["comparison_id"])
    assert updated["monitoring"] is False


def test_scheduler_keeps_refreshing_while_entitlement_is_still_active():
    """The contrast case: a creator who still has a valid, qualifying
    subscription keeps getting real refreshes."""
    import asyncio
    from backend.neighborhood_comparison_scheduler import _refresh_one_comparison

    email = "stillsubscribed@example.com"
    headers = _entitled_headers(email)
    with patch("backend.api.neighborhood_nearby", return_value=[]):
        created = client.post(
            "/api/neighborhood-insights/compare",
            json={"areas": [_area(), _area(city="Pune")]}, headers=headers,
        ).json()
    client.post(f"/api/neighborhood-insights/compare/{created['comparison_id']}/monitor", json={"monitoring": True}, headers=headers)

    comparison = get_comparison(created["comparison_id"])
    with patch("backend.api.neighborhood_nearby", return_value=[]):
        asyncio.run(_refresh_one_comparison(comparison))

    updated = get_comparison(created["comparison_id"])
    assert updated["monitoring"] is True
