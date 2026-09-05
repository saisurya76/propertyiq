import os

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app  # noqa: E402
from backend.auth_store import create_otp  # noqa: E402
from backend.subscription_store import upsert_subscription  # noqa: E402

client = TestClient(app)


def _authed_headers(email: str) -> dict:
    code = create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    token = r.json()["session_token"]
    return {"Authorization": f"Bearer {token}"}


def _entitled_headers(email: str, tier_id: str = "studio_pro") -> dict:
    upsert_subscription(email=email, tier_id=tier_id, status="active", dodo_subscription_id=f"sub_{email}")
    return _authed_headers(email)


def _valid_payload():
    return {
        "country": "India", "stateProvince": "Telangana", "city": "Hyderabad", "location": "Tellapur",
        "propertyType": "Apartment", "propertyName": "Aparna Sarovar Zenith", "developerName": "Aparna",
        "quotedPrice": 18000000, "governmentGuidance": 6500, "marketAverage": 10125, "unitArea": 1800,
        "monthlyRent": 45000, "areaUnit": "sqft",
    }


def test_assess_requires_authentication():
    """The real, direct proof this is now a paid, tier-gated feature:
    no session at all is rejected, not silently treated as public --
    confirmed this endpoint was completely open before this change."""
    r = client.post("/assess", json=_valid_payload())
    assert r.status_code == 401


def test_assess_rejects_a_signed_in_visitor_with_no_subscription():
    headers = _authed_headers("noassesssub@example.com")
    r = client.post("/assess", json=_valid_payload(), headers=headers)
    assert r.status_code == 403
    assert "property assessment" in r.json()["detail"]


def test_assess_rejects_a_tier_without_the_feature_enabled(monkeypatch):
    """A real, subscribed customer whose specific tier has had this
    feature disabled by an admin must still be rejected."""
    import backend.config_store as config_module
    email = "assessdisabled@example.com"
    headers = _entitled_headers(email, tier_id="studio_starter")

    tiers = config_module.get_all_tiers_merged()
    tiers["studio_starter"]["features"] = [f for f in tiers["studio_starter"]["features"] if f != "property_assessment"]
    monkeypatch.setattr(config_module, "get_tier_config", lambda: tiers)

    r = client.post("/assess", json=_valid_payload(), headers=headers)
    assert r.status_code == 403


def test_assess_succeeds_for_a_genuinely_entitled_subscriber():
    """The real, direct proof the gate is scoped correctly -- an
    entitled subscriber gets the actual, full assessment result, not
    just a bare 200."""
    headers = _entitled_headers("assessworks@example.com")
    r = client.post("/assess", json=_valid_payload(), headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "score" in data
    assert "rating" in data


def test_emi_calculator_requires_authentication():
    r = client.post("/api/neighborhood-insights/emi-calculator", json={"principal": 1000000, "annual_rate_percent": 10, "tenure_years": 10})
    assert r.status_code == 401


def test_emi_calculator_rejects_a_signed_in_visitor_with_no_subscription():
    headers = _authed_headers("noemisub@example.com")
    r = client.post("/api/neighborhood-insights/emi-calculator", json={"principal": 1000000, "annual_rate_percent": 10, "tenure_years": 10}, headers=headers)
    assert r.status_code == 403
    assert "EMI calculator" in r.json()["detail"]


def test_emi_calculator_succeeds_for_an_entitled_subscriber_with_the_real_reference_value():
    headers = _entitled_headers("emiworks@example.com")
    r = client.post("/api/neighborhood-insights/emi-calculator", json={"principal": 1000000, "annual_rate_percent": 10, "tenure_years": 10}, headers=headers)
    assert r.status_code == 200
    assert r.json()["emi"] == 13215.07


def test_amortization_schedule_gated_independently_from_emi_calculator():
    """Direct proof the two panels are genuinely gated separately, per
    the explicit business decision -- an entitled EMI-calculator user
    without amortization_projector must still be rejected here."""
    email = "emionly@example.com"
    headers = _entitled_headers(email, tier_id="studio_starter")

    import backend.config_store as config_module
    tiers = config_module.get_all_tiers_merged()
    tiers["studio_starter"]["features"] = [f for f in tiers["studio_starter"]["features"] if f != "amortization_projector"]
    import unittest.mock as mock
    with mock.patch.object(config_module, "get_tier_config", lambda: tiers):
        r = client.post("/api/neighborhood-insights/amortization-schedule", json={"principal": 1000000, "annual_rate_percent": 10, "tenure_years": 10}, headers=headers)
    assert r.status_code == 403

    r2 = client.post("/api/neighborhood-insights/emi-calculator", json={"principal": 1000000, "annual_rate_percent": 10, "tenure_years": 10}, headers=headers)
    assert r2.status_code == 200


def test_amortization_schedule_returns_the_full_real_schedule():
    headers = _entitled_headers("amortworks@example.com")
    r = client.post("/api/neighborhood-insights/amortization-schedule", json={"principal": 1000000, "annual_rate_percent": 10, "tenure_years": 10}, headers=headers)
    assert r.status_code == 200
    schedule = r.json()["schedule"]
    assert len(schedule) == 120
    assert schedule[-1]["remaining_balance"] == 0.0


def test_amortization_export_returns_a_real_csv():
    headers = _entitled_headers("csvexport@example.com")
    r = client.get(
        "/api/neighborhood-insights/amortization-schedule/export",
        params={"principal": 1000000, "annual_rate_percent": 10, "tenure_years": 10},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    lines = r.text.strip().split("\r\n")
    assert lines[0] == "month,payment,principal_component,interest_component,remaining_balance"
    assert len(lines) == 121  # header + 120 months


def test_amortization_export_requires_authentication():
    r = client.get(
        "/api/neighborhood-insights/amortization-schedule/export",
        params={"principal": 1000000, "annual_rate_percent": 10, "tenure_years": 10},
    )
    assert r.status_code == 401


def test_emi_calculator_rejects_invalid_input_with_a_400_not_a_500():
    headers = _entitled_headers("invalidinput@example.com")
    r = client.post("/api/neighborhood-insights/emi-calculator", json={"principal": -5, "annual_rate_percent": 10, "tenure_years": 10}, headers=headers)
    assert r.status_code == 400


def test_price_trends_requires_authentication():
    r = client.get("/api/neighborhood-insights/price-trends", params={"country": "India"})
    assert r.status_code == 401


def test_price_trends_rejects_a_signed_in_visitor_with_no_subscription():
    headers = _authed_headers("nopricetrendsub@example.com")
    r = client.get("/api/neighborhood-insights/price-trends", params={"country": "India"}, headers=headers)
    assert r.status_code == 403
    assert "Price trends" in r.json()["detail"]


def test_price_trends_rejects_an_out_of_range_years_value():
    headers = _entitled_headers("pricetrendsyears@example.com")
    r = client.get("/api/neighborhood-insights/price-trends", params={"country": "India", "years": 50}, headers=headers)
    assert r.status_code == 400


def test_price_trends_parses_a_real_fred_response_shape(monkeypatch):
    """Confirms parsing against FRED's actual, real observations
    response shape, including a genuinely real value pulled directly
    from the live Makati, Philippines series during research for this
    feature (2026-01-01: 305.9666)."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "FRED_API_KEY", "fake_key_for_test")
    monkeypatch.setattr(api_module, "_get_cached_json", lambda *a, **k: None)
    monkeypatch.setattr(api_module, "_set_cached_json", lambda *a, **k: None)

    class FakeResp:
        status_code = 200
        def json(self):
            return {"observations": [
                {"date": "2025-10-01", "value": "289.7940"},
                {"date": "2026-01-01", "value": "305.9666"},
            ]}

    monkeypatch.setattr(api_module.requests, "get", lambda *a, **k: FakeResp())
    headers = _entitled_headers("pricetrendsworks@example.com")
    r = client.get("/api/neighborhood-insights/price-trends", params={"country": "Philippines", "years": 8}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["has_data"] is True
    assert data["series_id"] == "QPHR628BIS"
    assert data["points"][-1]["value"] == 305.9666


def test_price_trends_honest_for_a_country_with_no_real_series():
    """Vietnam has genuinely no BIS/FRED series -- confirmed directly,
    not assumed. Must report this honestly, not silently omit or
    fabricate a value."""
    headers = _entitled_headers("pricetrendsvietnam@example.com")
    r = client.get("/api/neighborhood-insights/price-trends", params={"country": "Vietnam"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["has_data"] is False
    assert r.json()["reason"] == "country_not_covered"


def test_price_trends_honest_when_api_key_not_configured():
    import backend.api as api_module
    from unittest import mock
    headers = _entitled_headers("pricetrendsnokey@example.com")
    with mock.patch.object(api_module, "FRED_API_KEY", ""):
        r = client.get("/api/neighborhood-insights/price-trends", params={"country": "India"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["has_data"] is False
    assert r.json()["reason"] == "not_configured"


def test_price_trends_handles_a_real_fetch_failure(monkeypatch):
    import backend.api as api_module
    monkeypatch.setattr(api_module, "FRED_API_KEY", "fake_key")
    monkeypatch.setattr(api_module, "_get_cached_json", lambda *a, **k: None)

    def fake_get(*a, **k):
        raise api_module.requests.RequestException("network down")

    monkeypatch.setattr(api_module.requests, "get", fake_get)
    headers = _entitled_headers("pricetrendsfail@example.com")
    r = client.get("/api/neighborhood-insights/price-trends", params={"country": "Thailand"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["has_data"] is False
    assert r.json()["reason"] == "fetch_failed"


def test_cost_of_living_requires_authentication():
    r = client.get("/api/neighborhood-insights/cost-of-living", params={"lat": 17.4, "lon": 78.4})
    assert r.status_code == 401


def test_cost_of_living_rejects_a_signed_in_visitor_with_no_subscription():
    headers = _authed_headers("nocolsub@example.com")
    r = client.get("/api/neighborhood-insights/cost-of-living", params={"lat": 17.4, "lon": 78.4}, headers=headers)
    assert r.status_code == 403
    assert "cost of living" in r.json()["detail"]


def test_cost_of_living_returns_real_school_and_hospital_data(monkeypatch):
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda lat, lon, tag, radius=2000: [{"name": "x"}, {"name": "y"}] if "school" in tag else [{"name": "z"}])
    headers = _entitled_headers("colworks@example.com")
    r = client.get("/api/neighborhood-insights/cost-of-living", params={"lat": 17.4, "lon": 78.4}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["school_access"]["has_data"] is True
    assert data["school_access"]["count_within_2km"] == 2
    assert data["hospital_access"]["has_data"] is True
    assert data["hospital_access"]["count_within_2km"] == 1


def test_cost_of_living_honestly_lists_the_10_unavailable_items(monkeypatch):
    """Confirms all 10 items with no real data source are explicitly
    listed as unavailable, not silently dropped."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda *a, **k: [])
    headers = _entitled_headers("colhonest@example.com")
    r = client.get("/api/neighborhood-insights/cost-of-living", params={"lat": 17.4, "lon": 78.4}, headers=headers)
    assert r.status_code == 200
    unavailable = r.json()["unavailable_items"]
    assert len(unavailable) == 10
    assert "electricity" in unavailable
    assert "fuel" in unavailable
    assert "commute_cost" in unavailable


def test_cost_of_living_handles_missing_coordinates_gracefully():
    headers = _entitled_headers("colnocoords@example.com")
    r = client.get("/api/neighborhood-insights/cost-of-living", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["school_access"]["has_data"] is False
    assert data["school_access"]["reason"] == "no_coordinates"


def test_cost_of_living_survives_one_lookup_failing(monkeypatch):
    """A real resilience requirement: if the school lookup fails, the
    hospital data must still come through, not a total 500."""
    import backend.api as api_module

    def flaky_nearby(lat, lon, tag, radius=2000):
        if "school" in tag:
            raise Exception("simulated failure")
        return [{"name": "real hospital"}]

    monkeypatch.setattr(api_module, "neighborhood_nearby", flaky_nearby)
    headers = _entitled_headers("colflaky@example.com")
    r = client.get("/api/neighborhood-insights/cost-of-living", params={"lat": 17.4, "lon": 78.4}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["school_access"]["has_data"] is False
    assert data["hospital_access"]["has_data"] is True
    assert data["hospital_access"]["count_within_2km"] == 1


def test_hottest_properties_is_public_no_auth_required():
    r = client.get("/api/homepage/hottest-properties", params={"country": "India"})
    assert r.status_code == 200


def test_hottest_properties_returns_real_data_sorted_by_price_per_sqft():
    """Confirms this pulls from the real, existing comparables
    dataset -- not fabricated listings -- and is genuinely sorted by
    the one real, transparent number available (price/sqft), not a
    fictional "hotness" score."""
    r = client.get("/api/homepage/hottest-properties", params={"country": "India", "limit": 5})
    assert r.status_code == 200
    data = r.json()
    assert data["country"] == "India"
    props = data["properties"]
    assert len(props) > 0
    assert len(props) <= 5
    prices = [p["price_per_sqft"] for p in props]
    assert prices == sorted(prices, reverse=True)
    for p in props:
        assert p["project_name"]
        assert p["developer"]


def test_hottest_properties_only_returns_the_requested_country():
    r_india = client.get("/api/homepage/hottest-properties", params={"country": "India", "limit": 20})
    r_thailand = client.get("/api/homepage/hottest-properties", params={"country": "Thailand", "limit": 20})
    india_cities = {p["city"] for p in r_india.json()["properties"]}
    thai_cities = {p["city"] for p in r_thailand.json()["properties"]}
    assert "Hyderabad" in india_cities or "Mumbai" in india_cities or "Bangalore" in india_cities
    assert "Bangkok" in thai_cities or "Phuket" in thai_cities
    assert india_cities.isdisjoint(thai_cities)


def test_hottest_properties_honest_for_an_uncovered_country():
    """A country genuinely not in the comparables dataset returns an
    honestly empty list, not an error or fabricated data."""
    r = client.get("/api/homepage/hottest-properties", params={"country": "Germany"})
    assert r.status_code == 200
    assert r.json()["properties"] == []


def test_hottest_properties_respects_the_limit_parameter():
    r = client.get("/api/homepage/hottest-properties", params={"country": "India", "limit": 2})
    assert len(r.json()["properties"]) == 2
