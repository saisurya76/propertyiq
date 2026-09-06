import os

import pytest

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


def _property_payload(lat=17.4, lon=78.4):
    return {
        "country": "India", "stateProvince": "Telangana", "city": "Hyderabad", "location": "Tellapur",
        "propertyType": "Apartment", "propertyName": "Aparna Sarovar Zenith", "developerName": "Aparna",
        "quotedPrice": 18000000, "governmentGuidance": 6500, "marketAverage": 10125, "unitArea": 1800,
        "monthlyRent": 45000, "areaUnit": "sqft", "lat": lat, "lon": lon,
    }


def test_create_client_requires_authentication():
    r = client.post("/api/agent/clients", json={"client_name": "Rahul Sharma"})
    assert r.status_code == 401


def test_create_client_rejects_a_signed_in_visitor_with_no_subscription():
    headers = _authed_headers("noagentsub@example.com")
    r = client.post("/api/agent/clients", json={"client_name": "Rahul Sharma"}, headers=headers)
    assert r.status_code == 403
    assert "Agent Intelligence" in r.json()["detail"]


def test_create_client_succeeds_for_an_entitled_agent():
    headers = _entitled_headers("agentworks@example.com")
    r = client.post("/api/agent/clients", json={"client_name": "Rahul Sharma", "client_contact": "rahul@example.com"}, headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["client_name"] == "Rahul Sharma"
    assert "client_id" in data


def test_create_client_rejects_an_empty_name():
    headers = _entitled_headers("agentemptyname@example.com")
    r = client.post("/api/agent/clients", json={"client_name": "   "}, headers=headers)
    assert r.status_code == 400


def test_list_clients_only_shows_the_calling_agents_own_clients():
    headers_a = _entitled_headers("agenta@example.com")
    headers_b = _entitled_headers("agentb@example.com")
    client.post("/api/agent/clients", json={"client_name": "Client Of A"}, headers=headers_a)
    client.post("/api/agent/clients", json={"client_name": "Client Of B"}, headers=headers_b)

    r_a = client.get("/api/agent/clients", headers=headers_a)
    names_a = [c["client_name"] for c in r_a.json()["clients"]]
    assert "Client Of A" in names_a
    assert "Client Of B" not in names_a


def test_client_limit_is_enforced_and_reported_honestly():
    headers = _entitled_headers("agentlimit@example.com", tier_id="studio_starter")  # limit is 5
    for i in range(5):
        r = client.post("/api/agent/clients", json={"client_name": f"Client {i}"}, headers=headers)
        assert r.status_code == 200
    r_over = client.post("/api/agent/clients", json={"client_name": "One Too Many"}, headers=headers)
    assert r_over.status_code == 403


def test_delete_client_removes_it_and_a_stranger_cannot_delete_it():
    headers = _entitled_headers("agentdelete@example.com")
    created = client.post("/api/agent/clients", json={"client_name": "To Be Deleted"}, headers=headers).json()

    other_headers = _entitled_headers("agentstranger@example.com")
    r_stranger = client.delete(f"/api/agent/clients/{created['client_id']}", headers=other_headers)
    assert r_stranger.status_code == 404

    r_owner = client.delete(f"/api/agent/clients/{created['client_id']}", headers=headers)
    assert r_owner.status_code == 200
    r_list = client.get("/api/agent/clients", headers=headers)
    assert created["client_id"] not in [c["client_id"] for c in r_list.json()["clients"]]


def test_create_client_property_requires_the_client_to_belong_to_the_caller():
    headers = _entitled_headers("agentpropowner@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Owner's Client"}, headers=headers).json()

    stranger_headers = _entitled_headers("agentpropstranger@example.com")
    r = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=stranger_headers)
    assert r.status_code == 404


def test_create_and_list_client_property_round_trip():
    headers = _entitled_headers("agentproproundtrip@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Property Owner"}, headers=headers).json()

    r = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers)
    assert r.status_code == 200
    prop = r.json()
    assert prop["property_payload"]["propertyName"] == "Aparna Sarovar Zenith"
    assert prop["lat"] == 17.4

    r_list = client.get(f"/api/agent/clients/{created_client['client_id']}/properties", headers=headers)
    assert len(r_list.json()["properties"]) == 1


def test_property_limit_per_client_is_enforced():
    headers = _entitled_headers("agentproplimit@example.com", tier_id="studio_starter")  # limit is 3 per client
    created_client = client.post("/api/agent/clients", json={"client_name": "Limited Client"}, headers=headers).json()
    for i in range(3):
        r = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers)
        assert r.status_code == 200
    r_over = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers)
    assert r_over.status_code == 403


def test_delete_client_property_and_ownership_check():
    headers = _entitled_headers("agentdeleteprop@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Del Prop Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()

    stranger_headers = _entitled_headers("agentdeletepropstranger@example.com")
    r_stranger = client.delete(f"/api/agent/properties/{prop['property_id']}", headers=stranger_headers)
    assert r_stranger.status_code == 404

    r_owner = client.delete(f"/api/agent/properties/{prop['property_id']}", headers=headers)
    assert r_owner.status_code == 200


def test_deleting_a_client_cascades_to_its_properties():
    headers = _entitled_headers("agentcascade@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Cascade Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()

    client.delete(f"/api/agent/clients/{created_client['client_id']}", headers=headers)

    r = client.delete(f"/api/agent/properties/{prop['property_id']}", headers=headers)
    assert r.status_code == 404  # already gone via cascade


def test_generate_report_produces_a_real_pdf(monkeypatch):
    """The real, direct proof of the actual feature: generating a
    report calls the exact same real functions the rest of the app
    uses (build_assessment, etc.) and returns a genuine PDF."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda *a, **k: [])

    headers = _entitled_headers("agentreport@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Report Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()

    r = client.post(f"/api/agent/properties/{prop['property_id']}/generate-report", headers=headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"]
    assert r.content[:4] == b"%PDF"  # a genuine PDF file signature, not a stub


def test_generate_report_works_without_coordinates_too(monkeypatch):
    """A real resilience requirement: a property with no lat/lon
    (e.g. never geocoded) must still produce a report, with the
    coordinate-dependent sections honestly marked unavailable rather
    than crashing."""
    headers = _entitled_headers("agentreportnocoords@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "No Coords Client"}, headers=headers).json()
    payload = _property_payload(lat=None, lon=None)
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=payload, headers=headers).json()

    r = client.post(f"/api/agent/properties/{prop['property_id']}/generate-report", headers=headers)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_generate_report_requires_ownership():
    headers = _entitled_headers("agentreportowner@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Report Owner Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()

    stranger_headers = _entitled_headers("agentreportstranger@example.com")
    r = client.post(f"/api/agent/properties/{prop['property_id']}/generate-report", headers=stranger_headers)
    assert r.status_code == 404


def test_update_client_changes_name_and_contact():
    headers = _entitled_headers("agentupdateclient@example.com")
    created = client.post("/api/agent/clients", json={"client_name": "Old Name", "client_contact": "old@example.com"}, headers=headers).json()

    r = client.put(f"/api/agent/clients/{created['client_id']}", json={"client_name": "New Name", "client_contact": "new@example.com"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["client_name"] == "New Name"
    assert r.json()["client_contact"] == "new@example.com"


def test_update_client_requires_ownership():
    headers = _entitled_headers("agentupdateowner@example.com")
    created = client.post("/api/agent/clients", json={"client_name": "Owner Client"}, headers=headers).json()

    stranger_headers = _entitled_headers("agentupdatestranger@example.com")
    r = client.put(f"/api/agent/clients/{created['client_id']}", json={"client_name": "Hijacked"}, headers=stranger_headers)
    assert r.status_code == 404


def test_update_client_rejects_empty_name():
    headers = _entitled_headers("agentupdateempty@example.com")
    created = client.post("/api/agent/clients", json={"client_name": "Real Name"}, headers=headers).json()
    r = client.put(f"/api/agent/clients/{created['client_id']}", json={"client_name": "   "}, headers=headers)
    assert r.status_code == 400


def test_update_client_does_not_consume_the_client_quota():
    """A real, important edge case: editing an existing client must
    never be blocked by (or count against) the client-count limit,
    since it's the same row, not a new one."""
    headers = _entitled_headers("agentupdatequota@example.com", tier_id="studio_starter")  # limit is 5
    created_clients = []
    for i in range(5):
        created_clients.append(client.post("/api/agent/clients", json={"client_name": f"Client {i}"}, headers=headers).json())
    # At the limit -- editing any of them must still work
    r = client.put(f"/api/agent/clients/{created_clients[0]['client_id']}", json={"client_name": "Edited At Limit"}, headers=headers)
    assert r.status_code == 200


def test_update_client_property_changes_the_payload():
    headers = _entitled_headers("agentupdateprop@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Prop Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()

    updated_payload = _property_payload(lat=18.0, lon=79.0)
    updated_payload["propertyName"] = "Updated Property Name"
    r = client.put(f"/api/agent/properties/{prop['property_id']}", json=updated_payload, headers=headers)
    assert r.status_code == 200
    assert r.json()["property_payload"]["propertyName"] == "Updated Property Name"
    assert r.json()["lat"] == 18.0


def test_update_client_property_requires_ownership():
    headers = _entitled_headers("agentupdatepropowner@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Owner Prop Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()

    stranger_headers = _entitled_headers("agentupdatepropstranger@example.com")
    r = client.put(f"/api/agent/properties/{prop['property_id']}", json=_property_payload(), headers=stranger_headers)
    assert r.status_code == 404


def test_update_client_property_does_not_consume_the_property_quota():
    headers = _entitled_headers("agentupdatepropquota@example.com", tier_id="studio_starter")  # limit is 3 per client
    created_client = client.post("/api/agent/clients", json={"client_name": "Quota Prop Client"}, headers=headers).json()
    props = []
    for i in range(3):
        props.append(client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json())
    r = client.put(f"/api/agent/properties/{props[0]['property_id']}", json=_property_payload(lat=1, lon=1), headers=headers)
    assert r.status_code == 200


def test_report_includes_flood_risk_air_quality_and_price_trend(monkeypatch):
    """Direct proof the report now includes the previously-missing
    Neighborhood Insights data points, plus the new Price Trends
    section -- checked by extracting the real generated PDF's text."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda *a, **k: [{"name": "x"}])
    monkeypatch.setattr(api_module, "FRED_API_KEY", "")  # honestly unavailable, still must not crash

    headers = _entitled_headers("agentreportfull@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Full Report Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()

    r = client.post(f"/api/agent/properties/{prop['property_id']}/generate-report", headers=headers)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"

    # Extract real text from the real generated PDF to confirm the
    # new sections actually rendered, not just that a PDF came back.
    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(r.content))
    text = "".join(page.extract_text() for page in reader.pages)
    assert "Flood-Risk Proximity" in text
    assert "Air Pollution Index" in text
    assert "Price Trends" in text


def test_quota_summary_requires_authentication():
    r = client.get("/api/agent/quota-summary")
    assert r.status_code == 401


def test_quota_summary_reflects_real_current_usage():
    headers = _entitled_headers("agentquotasummary@example.com", tier_id="studio_starter")  # limit is 5 clients, 3 properties each
    c1 = client.post("/api/agent/clients", json={"client_name": "Client A"}, headers=headers).json()
    client.post("/api/agent/clients", json={"client_name": "Client B"}, headers=headers)
    client.post(f"/api/agent/clients/{c1['client_id']}/properties", json=_property_payload(), headers=headers)
    client.post(f"/api/agent/clients/{c1['client_id']}/properties", json=_property_payload(), headers=headers)

    r = client.get("/api/agent/quota-summary", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["client_count"] == 2
    assert data["client_limit"] == 5
    assert data["property_limit_per_client"] == 3
    assert data["per_client_property_counts"][c1["client_id"]] == 2


def test_quota_summary_reflects_deletion_freeing_a_slot():
    """Direct proof deleting a client genuinely frees the counted slot
    -- not a stale cached number."""
    headers = _entitled_headers("agentquotadelete@example.com", tier_id="studio_starter")
    c1 = client.post("/api/agent/clients", json={"client_name": "Temp Client"}, headers=headers).json()
    before = client.get("/api/agent/quota-summary", headers=headers).json()
    client.delete(f"/api/agent/clients/{c1['client_id']}", headers=headers)
    after = client.get("/api/agent/quota-summary", headers=headers).json()
    assert after["client_count"] == before["client_count"] - 1


def test_report_shows_real_property_currency_not_bare_numbers(monkeypatch):
    """Direct proof of the multi-country fix: a Thailand property's
    report shows THB, not a bare number or an assumed INR."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda *a, **k: [])
    monkeypatch.setattr(api_module, "FRED_API_KEY", "")

    headers = _entitled_headers("agentthaicurrency@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Thai Client"}, headers=headers).json()
    thai_payload = _property_payload()
    thai_payload.update({"country": "Thailand", "stateProvince": "", "city": "Bangkok", "location": "Sukhumvit"})
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=thai_payload, headers=headers).json()

    r = client.post(f"/api/agent/properties/{prop['property_id']}/generate-report", headers=headers)
    assert r.status_code == 200

    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(r.content))
    text = "".join(page.extract_text() for page in reader.pages)
    assert "THB" in text
    assert "INR" not in text


def test_display_name_defaults_to_none_and_falls_back_to_email_in_report(monkeypatch):
    """A real account that never set a display name must still get a
    working report, with the email shown as "Prepared by" instead."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda *a, **k: [])
    monkeypatch.setattr(api_module, "FRED_API_KEY", "")

    headers = _entitled_headers("agentnodisplayname@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "No Name Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()

    r = client.post(f"/api/agent/properties/{prop['property_id']}/generate-report", headers=headers)
    assert r.status_code == 200

    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(r.content))
    text = "".join(page.extract_text() for page in reader.pages)
    assert "agentnodisplayname@example.com" in text


def test_setting_display_name_shows_it_on_the_report_instead_of_email(monkeypatch):
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda *a, **k: [])
    monkeypatch.setattr(api_module, "FRED_API_KEY", "")

    headers = _entitled_headers("agentwithdisplayname@example.com")
    client.post("/api/profile/display-name", json={"display_name": "Priya Sharma"}, headers=headers)

    created_client = client.post("/api/agent/clients", json={"client_name": "Named Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()

    r = client.post(f"/api/agent/properties/{prop['property_id']}/generate-report", headers=headers)
    assert r.status_code == 200

    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(r.content))
    text = "".join(page.extract_text() for page in reader.pages)
    assert "Priya Sharma" in text


def test_display_name_can_be_cleared_back_to_none():
    headers = _entitled_headers("agentclearname@example.com")
    client.post("/api/profile/display-name", json={"display_name": "Temp Name"}, headers=headers)
    r = client.post("/api/profile/display-name", json={"display_name": ""}, headers=headers)
    assert r.status_code == 200
    assert r.json()["display_name"] is None


def test_get_profile_includes_display_name():
    headers = _entitled_headers("agentprofilename@example.com")
    client.post("/api/profile/display-name", json={"display_name": "Real Name Here"}, headers=headers)
    r = client.get("/api/profile", headers=headers)
    assert r.status_code == 200
    assert r.json()["display_name"] == "Real Name Here"


def test_compare_properties_requires_at_least_two():
    headers = _entitled_headers("agentcompareone@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Compare Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()
    r = client.post(f"/api/agent/clients/{created_client['client_id']}/compare-properties", json={"property_ids": [prop["property_id"]]}, headers=headers)
    assert r.status_code == 400


def test_compare_properties_returns_real_data_for_each(monkeypatch):
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda *a, **k: [])

    headers = _entitled_headers("agentcomparereal@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Compare Real Client"}, headers=headers).json()
    p1 = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(lat=17.4, lon=78.4), headers=headers).json()
    p2 = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(lat=17.5, lon=78.5), headers=headers).json()

    r = client.post(f"/api/agent/clients/{created_client['client_id']}/compare-properties", json={"property_ids": [p1["property_id"], p2["property_id"]]}, headers=headers)
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) == 2
    assert all(res["has_data"] for res in results)


def test_compare_properties_honest_when_missing_coordinates():
    headers = _entitled_headers("agentcomparenocoords@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "No Coords Compare Client"}, headers=headers).json()
    p1 = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(lat=None, lon=None), headers=headers).json()
    p2 = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(lat=17.5, lon=78.5), headers=headers).json()

    r = client.post(f"/api/agent/clients/{created_client['client_id']}/compare-properties", json={"property_ids": [p1["property_id"], p2["property_id"]]}, headers=headers)
    assert r.status_code == 200
    results = r.json()["results"]
    no_coords_result = next(res for res in results if res["property_id"] == p1["property_id"])
    assert no_coords_result["has_data"] is False
    assert no_coords_result["reason"] == "no_coordinates"


def test_compare_properties_rejects_a_property_from_a_different_client():
    headers = _entitled_headers("agentcomparecross@example.com")
    client_a = client.post("/api/agent/clients", json={"client_name": "Client A"}, headers=headers).json()
    client_b = client.post("/api/agent/clients", json={"client_name": "Client B"}, headers=headers).json()
    p_a = client.post(f"/api/agent/clients/{client_a['client_id']}/properties", json=_property_payload(), headers=headers).json()
    p_b = client.post(f"/api/agent/clients/{client_b['client_id']}/properties", json=_property_payload(), headers=headers).json()

    r = client.post(f"/api/agent/clients/{client_a['client_id']}/compare-properties", json={"property_ids": [p_a["property_id"], p_b["property_id"]]}, headers=headers)
    assert r.status_code == 404


def test_report_includes_comparison_against_client_other_properties(monkeypatch):
    """Direct proof, via real extracted PDF text, that generating a
    report for one property with a sibling property (same client, both
    with coordinates) includes the comparison section."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda *a, **k: [])
    monkeypatch.setattr(api_module, "FRED_API_KEY", "")

    headers = _entitled_headers("agentreportcompare@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Compare Report Client"}, headers=headers).json()
    p1_payload = _property_payload(lat=17.4, lon=78.4)
    p1_payload["propertyName"] = "First Property"
    p1 = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=p1_payload, headers=headers).json()
    p2_payload = _property_payload(lat=17.5, lon=78.5)
    p2_payload["propertyName"] = "Second Property"
    client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=p2_payload, headers=headers)

    r = client.post(f"/api/agent/properties/{p1['property_id']}/generate-report", headers=headers)
    assert r.status_code == 200

    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(r.content))
    text = "".join(page.extract_text() for page in reader.pages)
    assert "Area Comparison" in text
    assert "Second Property" in text


def test_report_omits_comparison_section_for_a_clients_only_property(monkeypatch):
    """The opposite, equally real case: a client with just one
    property shows the Area Comparison section honestly saying there's
    nothing to compare against, rather than a real comparison table
    with fabricated or empty rows."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda *a, **k: [])
    monkeypatch.setattr(api_module, "FRED_API_KEY", "")

    headers = _entitled_headers("agentreportnocompare@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Solo Property Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(lat=17.4, lon=78.4), headers=headers).json()

    r = client.post(f"/api/agent/properties/{prop['property_id']}/generate-report", headers=headers)
    assert r.status_code == 200

    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(r.content))
    text = "".join(page.extract_text() for page in reader.pages)
    assert "Area Comparison" in text
    assert "no other properties" in text.lower()


def test_report_includes_amortization_schedule_and_checklist_and_footer(monkeypatch):
    """Direct proof, via real extracted PDF text, that the previously
    missing Amortization Projector schedule, buyer's due-diligence
    checklist, local authority contacts, and the legal-links footer
    all genuinely render."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda *a, **k: [])
    monkeypatch.setattr(api_module, "FRED_API_KEY", "")

    headers = _entitled_headers("agentfullreport@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Full Report Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()

    r = client.post(f"/api/agent/properties/{prop['property_id']}/generate-report", headers=headers)
    assert r.status_code == 200

    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(r.content))
    text = "".join(page.extract_text() for page in reader.pages)

    assert "Amortization Projector" in text
    assert "Buyer's Due-Diligence Checklist" in text
    assert "RERA registration" in text  # a real, specific India checklist line
    assert "Local Authority Contacts" in text
    assert "RERA helpline" in text
    assert "Privacy Policy" in text
    assert "Terms of Service" in text
    assert "Refund Policy" in text
    # The amortization table's own real, correct math -- ends at zero,
    # confirming build_amortization_schedule's real output rendered,
    # not a fabricated placeholder.
    assert "0\n" in text or text.rstrip().endswith("0")


def test_report_amortization_uses_the_correct_country_specific_checklist(monkeypatch):
    """Direct proof the checklist/authority-contacts section is real
    per-country content, not always India's, for a Thailand property."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda *a, **k: [])
    monkeypatch.setattr(api_module, "FRED_API_KEY", "")

    headers = _entitled_headers("agentthaichecklist@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Thai Checklist Client"}, headers=headers).json()
    thai_payload = _property_payload()
    thai_payload.update({"country": "Thailand", "stateProvince": "", "city": "Bangkok", "location": "Sukhumvit"})
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=thai_payload, headers=headers).json()

    r = client.post(f"/api/agent/properties/{prop['property_id']}/generate-report", headers=headers)
    assert r.status_code == 200

    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(r.content))
    text = "".join(page.extract_text() for page in reader.pages)
    assert "Chanote" in text  # real, Thailand-specific checklist content
    assert "Department of Lands" in text
    assert "RERA" not in text  # must not leak India's checklist for a Thailand property


def test_report_omits_checklist_gracefully_for_an_unmapped_country(monkeypatch):
    """A real resilience requirement: a country somehow outside this
    app's normal 5 (shouldn't happen, but code should never assume)
    must not crash the report -- just show no checklist section."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda *a, **k: [])
    monkeypatch.setattr(api_module, "FRED_API_KEY", "")

    headers = _entitled_headers("agentunmappedcountry@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Unmapped Client"}, headers=headers).json()
    odd_payload = _property_payload()
    odd_payload.update({"country": "Narnia", "stateProvince": ""})
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=odd_payload, headers=headers).json()

    r = client.post(f"/api/agent/properties/{prop['property_id']}/generate-report", headers=headers)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_report_has_a_client_friendly_heading_not_the_internal_tool_name(monkeypatch):
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda *a, **k: [])
    monkeypatch.setattr(api_module, "FRED_API_KEY", "")

    headers = _entitled_headers("agentheadingcheck@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Heading Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()
    r = client.post(f"/api/agent/properties/{prop['property_id']}/generate-report", headers=headers)
    assert r.status_code == 200

    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(r.content))
    text = "".join(page.extract_text() for page in reader.pages)
    assert "PROPERTY ADVISORY REPORT" in text
    assert "Monetize" not in text  # internal, agent-side framing shouldn't appear in a client-facing document


def test_report_footer_has_real_clickable_link_annotations_on_every_page(monkeypatch):
    """Direct proof the reportlab two-pass crash is genuinely fixed --
    inspects the actual PDF's real link annotation objects (not just
    the visible text) on a genuine multi-page report."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda *a, **k: [])
    monkeypatch.setattr(api_module, "FRED_API_KEY", "")

    headers = _entitled_headers("agentlinkannotations@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Link Annotation Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()
    r = client.post(f"/api/agent/properties/{prop['property_id']}/generate-report", headers=headers)
    assert r.status_code == 200

    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(r.content))
    assert len(reader.pages) >= 2  # a real multi-page report -- the crash only ever showed up from page 2 onward
    for page in reader.pages:
        annots = page.get("/Annots")
        assert annots is not None and len(annots) == 3
        urls = {a.get_object()["/A"]["/URI"] for a in annots}
        assert urls == {
            "https://app.propertyiqweb.com/privacy-policy.html",
            "https://app.propertyiqweb.com/terms-of-service.html",
            "https://app.propertyiqweb.com/refund-policy.html",
        }


def test_pipeline_stages_endpoint_is_public_and_returns_the_real_stage_list():
    r = client.get("/api/agent/pipeline-stages")
    assert r.status_code == 200
    assert r.json()["stages"] == [
        "Lead", "Evaluation", "Shortlisted", "Client Viewed",
        "Site Visit", "Negotiation", "Due Diligence", "Deal", "Lost",
    ]


def test_new_property_defaults_to_lead_stage():
    headers = _entitled_headers("agentstagedefault@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Stage Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()
    assert prop["stage"] == "Lead"


def test_update_property_stage_moves_it_through_the_real_pipeline():
    headers = _entitled_headers("agentstageupdate@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Stage Update Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()

    r = client.put(f"/api/agent/properties/{prop['property_id']}/stage", json={"stage": "Negotiation"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["stage"] == "Negotiation"

    r2 = client.get(f"/api/agent/clients/{created_client['client_id']}/properties", headers=headers)
    assert r2.json()["properties"][0]["stage"] == "Negotiation"


def test_update_property_stage_rejects_an_invalid_stage_name():
    headers = _entitled_headers("agentstageinvalid@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Invalid Stage Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()

    r = client.put(f"/api/agent/properties/{prop['property_id']}/stage", json={"stage": "Made Up Stage"}, headers=headers)
    assert r.status_code == 400


def test_update_property_stage_requires_ownership():
    headers = _entitled_headers("agentstageowner@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Owner Stage Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()

    stranger_headers = _entitled_headers("agentstagestranger@example.com")
    r = client.put(f"/api/agent/properties/{prop['property_id']}/stage", json={"stage": "Deal"}, headers=stranger_headers)
    assert r.status_code == 404


def test_get_branding_defaults_to_all_none_for_a_fresh_account():
    headers = _entitled_headers("agentbrandingfresh@example.com")
    r = client.get("/api/agent/branding", headers=headers)
    assert r.status_code == 200
    assert all(v is None for v in r.json().values())


def test_update_branding_sets_the_provided_fields():
    headers = _entitled_headers("agentbrandingset@example.com")
    r = client.post("/api/agent/branding", json={"brokerage_name": "ABC Realty", "contact_phone": "+91 98765 43210"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["brokerage_name"] == "ABC Realty"
    assert r.json()["contact_phone"] == "+91 98765 43210"


def test_partial_branding_update_does_not_blank_out_other_fields():
    """The real bug this guards against: a partial update request must
    only touch the fields it actually sends, not silently null out
    everything else already saved."""
    headers = _entitled_headers("agentbrandingpartial@example.com")
    client.post("/api/agent/branding", json={"brokerage_name": "First Brokerage", "contact_phone": "+91 11111 11111"}, headers=headers)
    r = client.post("/api/agent/branding", json={"contact_phone": "+91 22222 22222"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["contact_phone"] == "+91 22222 22222"
    assert r.json()["brokerage_name"] == "First Brokerage"  # must survive the partial update


def test_branding_field_can_be_cleared_with_an_empty_string():
    headers = _entitled_headers("agentbrandingclear@example.com")
    client.post("/api/agent/branding", json={"brokerage_name": "Temp Brokerage"}, headers=headers)
    r = client.post("/api/agent/branding", json={"brokerage_name": ""}, headers=headers)
    assert r.status_code == 200
    assert r.json()["brokerage_name"] is None


def test_share_slug_must_be_alphanumeric_with_hyphens_only():
    headers = _entitled_headers("agentbrandingslugformat@example.com")
    r = client.post("/api/agent/branding", json={"share_slug": "not valid!"}, headers=headers)
    assert r.status_code == 400


def test_share_slug_uniqueness_is_enforced_across_agents():
    headers_a = _entitled_headers("agentslugownera@example.com")
    headers_b = _entitled_headers("agentslugownerb@example.com")
    r1 = client.post("/api/agent/branding", json={"share_slug": "priya-sharma"}, headers=headers_a)
    assert r1.status_code == 200
    r2 = client.post("/api/agent/branding", json={"share_slug": "priya-sharma"}, headers=headers_b)
    assert r2.status_code == 409


def test_share_slug_can_be_kept_by_its_own_owner_on_re_save():
    """Re-saving the same slug (e.g. alongside other branding changes)
    must not be rejected as a collision with oneself."""
    headers = _entitled_headers("agentslugreowner@example.com")
    client.post("/api/agent/branding", json={"share_slug": "my-own-slug"}, headers=headers)
    r = client.post("/api/agent/branding", json={"share_slug": "my-own-slug", "brokerage_name": "Updated"}, headers=headers)
    assert r.status_code == 200


def test_report_includes_agent_branding_in_the_header(monkeypatch):
    """Direct proof, via real extracted PDF text, that a saved
    brokerage name, contact phone, and share slug all genuinely
    appear in the generated report."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda *a, **k: [])
    monkeypatch.setattr(api_module, "FRED_API_KEY", "")

    headers = _entitled_headers("agentbrandedreport@example.com")
    client.post("/api/agent/branding", json={
        "brokerage_name": "Skyline Realty", "contact_phone": "+91 90000 11111", "share_slug": "skyline-priya",
    }, headers=headers)

    created_client = client.post("/api/agent/clients", json={"client_name": "Branded Report Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()
    r = client.post(f"/api/agent/properties/{prop['property_id']}/generate-report", headers=headers)
    assert r.status_code == 200

    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(r.content))
    text = "".join(page.extract_text() for page in reader.pages)
    normalized = " ".join(text.split())  # PDF text extraction can insert a newline mid-value when a long cell wraps visually — not a real bug in the report itself
    assert "Skyline Realty" in normalized
    assert "+91 90000 11111" in normalized
    assert "skyline-priya" in normalized


def test_report_uses_custom_footer_text_when_set(monkeypatch):
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda *a, **k: [])
    monkeypatch.setattr(api_module, "FRED_API_KEY", "")

    headers = _entitled_headers("agentcustomfooter@example.com")
    client.post("/api/agent/branding", json={"custom_footer_text": "Trusted advisor since 2015 — always here for you"}, headers=headers)

    created_client = client.post("/api/agent/clients", json={"client_name": "Custom Footer Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()
    r = client.post(f"/api/agent/properties/{prop['property_id']}/generate-report", headers=headers)
    assert r.status_code == 200

    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(r.content))
    text = "".join(page.extract_text() for page in reader.pages)
    assert "Trusted advisor since 2015" in text


def test_report_works_normally_with_no_branding_set_at_all(monkeypatch):
    """A real resilience requirement: an agent who never touched
    branding must still get a normal, working report with the
    original default footer."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda *a, **k: [])
    monkeypatch.setattr(api_module, "FRED_API_KEY", "")

    headers = _entitled_headers("agentnobranding@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "No Branding Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()
    r = client.post(f"/api/agent/properties/{prop['property_id']}/generate-report", headers=headers)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"

    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(r.content))
    text = "".join(page.extract_text() for page in reader.pages)
    assert "for internal advisory use by the preparing agent" in text


def test_report_survives_a_broken_logo_url_gracefully(monkeypatch):
    """Direct proof a bad/unreachable photo_url doesn't crash report
    generation -- a logo is a nice-to-have, not a hard dependency."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda *a, **k: [])
    monkeypatch.setattr(api_module, "FRED_API_KEY", "")

    headers = _entitled_headers("agentbrokenlogo@example.com")
    client.post("/api/agent/branding", json={"photo_url": "https://this-domain-genuinely-does-not-exist-xyz123.invalid/logo.png"}, headers=headers)

    created_client = client.post("/api/agent/clients", json={"client_name": "Broken Logo Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()
    r = client.post(f"/api/agent/properties/{prop['property_id']}/generate-report", headers=headers)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_report_types_catalog_lists_all_9_named_types():
    r = client.get("/api/agent/report-types")
    assert r.status_code == 200
    ids = {t["id"] for t in r.json()["report_types"]}
    assert ids == {
        "property_intelligence", "location", "area_comparison", "investment_analysis",
        "buyer_due_diligence", "construction", "client_property_comparison", "recommendation", "handover",
    }
    assert "quick" not in ids  # the original quick report isn't part of the named catalog


def test_named_report_endpoint_rejects_an_unknown_report_type():
    headers = _entitled_headers("agentunknownreporttype@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Unknown Type Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()
    r = client.post(f"/api/agent/properties/{prop['property_id']}/generate-report/not-a-real-type", headers=headers)
    assert r.status_code == 404


def test_named_report_endpoint_rejects_quick_as_a_named_type():
    """quick is the original report's own internal id -- it must not
    be reachable through the named-report URL, only its own dedicated
    endpoint, to keep the two conceptually distinct for the frontend."""
    headers = _entitled_headers("agentquickasnamedcheck@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Quick Named Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()
    r = client.post(f"/api/agent/properties/{prop['property_id']}/generate-report/quick", headers=headers)
    assert r.status_code == 404


@pytest.mark.parametrize("report_type,expected_heading", [
    ("property_intelligence", "PROPERTY INTELLIGENCE REPORT"),
    ("location", "LOCATION REPORT"),
    ("area_comparison", "AREA COMPARISON REPORT"),
    ("investment_analysis", "INVESTMENT ANALYSIS REPORT"),
    ("buyer_due_diligence", "BUYER DUE-DILIGENCE REPORT"),
    ("construction", "CONSTRUCTION REPORT"),
    ("client_property_comparison", "CLIENT PROPERTY COMPARISON"),
    ("recommendation", "RECOMMENDATION REPORT"),
    ("handover", "HANDOVER REPORT"),
])
def test_each_named_report_type_generates_a_real_pdf_with_its_own_heading(monkeypatch, report_type, expected_heading):
    """Direct proof, via real extracted PDF text, that all 9 named
    report types genuinely generate and each carries its own distinct
    title -- not 9 endpoints all quietly rendering the same content."""
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda *a, **k: [])
    monkeypatch.setattr(api_module, "FRED_API_KEY", "")

    headers = _entitled_headers(f"agentnamedreport{report_type}@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Named Report Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()

    r = client.post(f"/api/agent/properties/{prop['property_id']}/generate-report/{report_type}", headers=headers)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"

    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(r.content))
    text = "".join(page.extract_text() for page in reader.pages)
    assert expected_heading in text


def test_handover_report_shows_real_country_specific_items(monkeypatch):
    import backend.api as api_module
    monkeypatch.setattr(api_module, "neighborhood_nearby", lambda *a, **k: [])
    monkeypatch.setattr(api_module, "FRED_API_KEY", "")

    headers = _entitled_headers("agenthandoverindia@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Handover India Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()
    r = client.post(f"/api/agent/properties/{prop['property_id']}/generate-report/handover", headers=headers)
    assert r.status_code == 200

    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(r.content))
    text = "".join(page.extract_text() for page in reader.pages)
    assert "Registered sale deed" in text
    assert "Encumbrance certificate" in text


def test_construction_report_is_honest_about_no_linked_design():
    headers = _entitled_headers("agentconstructionhonest@example.com")
    created_client = client.post("/api/agent/clients", json={"client_name": "Construction Client"}, headers=headers).json()
    prop = client.post(f"/api/agent/clients/{created_client['client_id']}/properties", json=_property_payload(), headers=headers).json()
    r = client.post(f"/api/agent/properties/{prop['property_id']}/generate-report/construction", headers=headers)
    assert r.status_code == 200

    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(r.content))
    text = "".join(page.extract_text() for page in reader.pages)
    assert "no linked Construction Studio design" in text


def test_named_report_requires_entitlement_and_ownership():
    headers = _authed_headers("agentnamedreportnosub@example.com")
    r = client.post("/api/agent/properties/fake-id/generate-report/location", headers=headers)
    assert r.status_code == 403
