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


def _property_payload():
    return {
        "country": "India", "stateProvince": "Telangana", "city": "Hyderabad", "location": "Tellapur",
        "propertyType": "Apartment", "propertyName": "Aparna Sarovar Zenith", "developerName": "Aparna",
        "quotedPrice": 18000000, "governmentGuidance": 6500, "marketAverage": 10125, "unitArea": 1800,
        "monthlyRent": 45000, "areaUnit": "sqft",
    }


def test_generate_report_requires_authentication():
    r = client.post("/generate-report", json=_property_payload())
    assert r.status_code == 401


def test_generate_report_requires_subscription():
    """Direct proof of the real fix: this endpoint previously had NO
    gate at all and could be called directly to bypass /assess's own
    paywall entirely."""
    headers = _authed_headers("mainreportnosub@example.com")
    r = client.post("/generate-report", json=_property_payload(), headers=headers)
    assert r.status_code == 403
    assert "property_assessment" not in r.json()["detail"]  # human-readable message, not the internal feature key
    assert "subscription" in r.json()["detail"].lower()


def test_generate_report_produces_a_real_pdf_for_an_entitled_user():
    headers = _entitled_headers("mainreportworks@example.com")
    r = client.post("/generate-report", json=_property_payload(), headers=headers)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"]
    assert r.content[:4] == b"%PDF"


def test_generate_report_matches_the_live_assess_endpoints_own_numbers():
    """The actual, direct proof of the fix: the PDF and the live
    /assess JSON response must show the exact same real numbers for
    the exact same input, since both now render from the same
    assessment object -- confirmed by extracting real text from the
    generated PDF and comparing it against the live endpoint's JSON."""
    headers = _entitled_headers("mainreportmatch@example.com")
    payload = _property_payload()

    assess_response = client.post("/assess", json=payload, headers=headers)
    assert assess_response.status_code == 200
    assess_data = assess_response.json()

    pdf_response = client.post("/generate-report", json=payload, headers=headers)
    assert pdf_response.status_code == 200

    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(pdf_response.content))
    text = "".join(page.extract_text() for page in reader.pages)

    assert str(assess_data["rating"]) in text
    assert assess_data["recommendation"] in text
    assert f"{assess_data['fairValue']:,.0f}" in text.replace(",", ",")  # formatted the same way


def test_generate_report_includes_decision_narrative_and_buyer_advantage(monkeypatch):
    """Direct proof the new report includes fields the OLD pdf_renderer
    never had at all (decision narrative, buyer advantage, recommendation
    confidence) -- this is the actual gap that made the old PDF and the
    live page poles apart."""
    headers = _entitled_headers("mainreportnewfields@example.com")
    r = client.post("/generate-report", json=_property_payload(), headers=headers)
    assert r.status_code == 200

    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(r.content))
    text = "".join(page.extract_text() for page in reader.pages)
    assert "Buyer Advantage" in text
    assert "Recommendation Confidence" in text
    assert "Decision" in text
    assert "Why This Recommendation" in text
    assert "Fraud Risk Intelligence" in text


def test_generate_report_shows_real_local_currency_for_a_thailand_property():
    headers = _entitled_headers("mainreportthaicurrency@example.com")
    payload = _property_payload()
    payload.update({"country": "Thailand", "stateProvince": "", "city": "Bangkok", "location": "Sukhumvit"})
    r = client.post("/generate-report", json=payload, headers=headers)
    assert r.status_code == 200

    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(r.content))
    text = "".join(page.extract_text() for page in reader.pages)
    assert "THB" in text
    assert "INR" not in text


def test_generate_report_has_real_footer_link_annotations_on_every_page():
    headers = _entitled_headers("mainreportfooterlinks@example.com")
    r = client.post("/generate-report", json=_property_payload(), headers=headers)
    assert r.status_code == 200

    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(r.content))
    for page in reader.pages:
        annots = page.get("/Annots")
        assert annots is not None and len(annots) == 3
