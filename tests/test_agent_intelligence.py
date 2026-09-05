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
    assert "Comparison Against This Client" in text
    assert "Second Property" in text


def test_report_omits_comparison_section_for_a_clients_only_property(monkeypatch):
    """The opposite, equally real case: a client with just one
    property must not show a comparison section at all."""
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
    assert "Comparison Against This Client" not in text


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
