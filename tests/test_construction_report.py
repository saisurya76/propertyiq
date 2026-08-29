import io

from pypdf import PdfReader

from backend.construction_report import generate_construction_report_pdf
from backend.construction_studio import estimate_cost

SAMPLE_ROOMS = [
    {"name": "Living Room", "x": 0, "y": 0, "length": 20, "width": 15},
    {"name": "Master Bathroom", "x": 20, "y": 0, "length": 8, "width": 8},
    {"name": "Kitchen", "x": 0, "y": 15, "length": 12, "width": 10},
]
PLOT_LENGTH, PLOT_WIDTH = 30, 25


def _sample_design():
    cost_estimate = estimate_cost(
        plot_size_sqft=1200,
        selections={"structure": "rcc_frame", "flooring": "vitrified_tile", "roofing": "rcc_slab"},
        region="india", currency="INR",
    )
    return {
        "plot_spec": {"plot_length_ft": PLOT_LENGTH, "plot_width_ft": PLOT_WIDTH, "entrance_direction": "north", "road_facing_side": "north"},
        "region": "india",
        "currency": "INR",
        "cost_estimate": cost_estimate,
        "vastu_result": {"compliant": True, "scope": "full_multi_rule_check", "notes": ["Entrance facing north aligns with favorable Vastu directions."]},
        "risks": [],
    }


def test_generates_a_genuinely_valid_readable_pdf():
    """The most basic, real check: the output must be an actual, parseable
    PDF, not just some bytes that happen not to crash the generator."""
    pdf_bytes = generate_construction_report_pdf(_sample_design(), [{"floor_label": "Ground Floor", "rooms": SAMPLE_ROOMS}])
    assert pdf_bytes[:4] == b"%PDF"
    reader = PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) > 5  # cover + room summary + cost + compliance + 3 discipline sections, at minimum


def test_report_includes_the_top_level_disclaimer_text():
    pdf_bytes = generate_construction_report_pdf(_sample_design(), [{"floor_label": "Ground Floor", "rooms": SAMPLE_ROOMS}])
    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = "".join(page.extract_text() for page in reader.pages)
    assert "NOT a licensed engineer" in full_text
    assert "licensed structural engineer, plumber, and electrician" in full_text


def test_report_includes_real_room_names_and_areas():
    pdf_bytes = generate_construction_report_pdf(_sample_design(), [{"floor_label": "Ground Floor", "rooms": SAMPLE_ROOMS}])
    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = "".join(page.extract_text() for page in reader.pages)
    assert "Living Room" in full_text
    assert "Master Bathroom" in full_text
    assert "300" in full_text  # Living Room's real area: 20 x 15


def test_report_includes_the_real_cost_total_and_discipline_sections():
    design = _sample_design()
    pdf_bytes = generate_construction_report_pdf(design, [{"floor_label": "Ground Floor", "rooms": SAMPLE_ROOMS}])
    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = "".join(page.extract_text() for page in reader.pages)
    assert "Structural" in full_text
    assert "Roofing" in full_text
    assert "Finishes" in full_text
    # The real grand total, not a placeholder
    real_total = f"{design['cost_estimate']['grand_total_converted']:,.0f}"
    assert real_total in full_text


def test_report_includes_real_element_labels_and_specs():
    """Confirms the report's diagrams/tables use the SAME real
    discipline_overlays.py computation the in-app view uses -- not a
    separate, potentially-inconsistent report-only rendering."""
    pdf_bytes = generate_construction_report_pdf(_sample_design(), [{"floor_label": "Ground Floor", "rooms": SAMPLE_ROOMS}])
    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = "".join(page.extract_text() for page in reader.pages)
    assert "C1" in full_text  # a real column label
    assert "FX1" in full_text  # a real fixture label (Master Bathroom is a wet room)
    assert "L1" in full_text  # a real light label
    assert "230mm x 230mm" in full_text  # the real reference spec text (1 floor)
    assert "NOT calculated for this specific building" in full_text


def test_report_handles_a_floor_with_no_wet_rooms_honestly():
    """Must not fabricate plumbing fixtures for a floor with no
    bathroom/kitchen/utility -- must say so plainly instead."""
    no_wet_rooms = [{"name": "Living Room", "x": 0, "y": 0, "length": 20, "width": 15}]
    pdf_bytes = generate_construction_report_pdf(_sample_design(), [{"floor_label": "Ground Floor", "rooms": no_wet_rooms}])
    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = "".join(page.extract_text() for page in reader.pages)
    assert "No bathroom/kitchen/utility rooms on this floor" in full_text


def test_report_covers_every_real_floor_in_a_multi_floor_design():
    floors = [
        {"floor_label": "Ground Floor", "rooms": SAMPLE_ROOMS},
        {"floor_label": "First Floor", "rooms": [{"name": "Bedroom 2", "x": 0, "y": 0, "length": 12, "width": 12}]},
    ]
    pdf_bytes = generate_construction_report_pdf(_sample_design(), floors)
    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = "".join(page.extract_text() for page in reader.pages)
    assert "Ground Floor" in full_text
    assert "First Floor" in full_text
    assert "Bedroom 2" in full_text


def test_column_spec_in_report_reflects_the_real_total_floor_count():
    """The report must genuinely pass the real floor count through to
    the structural spec, same as the in-app overlay view does -- a
    2-floor design should quote the G+1 reference, not the single-storey
    default."""
    floors = [
        {"floor_label": "Ground Floor", "rooms": SAMPLE_ROOMS},
        {"floor_label": "First Floor", "rooms": [{"name": "Bedroom 2", "x": 0, "y": 0, "length": 12, "width": 12}]},
    ]
    pdf_bytes = generate_construction_report_pdf(_sample_design(), floors)
    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = "".join(page.extract_text() for page in reader.pages)
    assert "230mm x 300mm" in full_text  # G+1 reference, not G's 230x230
    assert "230mm x 230mm" not in full_text


def test_report_omits_compliance_section_when_there_is_no_specific_tradition():
    design = _sample_design()
    design["vastu_result"] = {"compliant": True, "scope": "no_specific_tradition", "notes": []}
    pdf_bytes = generate_construction_report_pdf(design, [{"floor_label": "Ground Floor", "rooms": SAMPLE_ROOMS}])
    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = "".join(page.extract_text() for page in reader.pages)
    assert "Vastu Compliance" not in full_text


def test_report_uses_the_given_property_name_as_its_title():
    pdf_bytes = generate_construction_report_pdf(_sample_design(), [{"floor_label": "Ground Floor", "rooms": SAMPLE_ROOMS}], property_name="My Dream Home")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = reader.pages[0].extract_text()
    assert "My Dream Home" in full_text


def test_full_http_flow_generate_design_then_download_report():
    """The real, end-to-end path a user actually takes: generate a
    design, then request its PDF report by design_id."""
    from fastapi.testclient import TestClient
    from backend.api import app
    from backend.auth_store import create_otp
    from backend.subscription_store import upsert_subscription

    client = TestClient(app)

    email = "report_download_test@example.com"
    code = create_otp(email)
    r_verify = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    headers = {"Authorization": f"Bearer {r_verify.json()['session_token']}"}
    upsert_subscription(email=email, tier_id="studio_starter", dodo_subscription_id="sub_reportdl", status="active")

    design_resp = client.post("/api/construction-studio/design", headers=headers, json={
        "plot_size_sqft": 1200, "plot_length_ft": PLOT_LENGTH, "plot_width_ft": PLOT_WIDTH,
        "selections": {"structure": "rcc_frame", "flooring": "vitrified_tile"},
        "entrance_direction": "north", "road_facing_side": "north", "region": "india", "currency": "INR",
        "rooms": SAMPLE_ROOMS,
    })
    assert design_resp.status_code == 200
    design_id = design_resp.json()["design_id"]

    report_resp = client.post(f"/api/construction-studio/design/{design_id}/report", json={
        "floors": [{"floor_label": "Ground Floor", "rooms": SAMPLE_ROOMS}],
        "property_name": "Report Download Test House",
    })
    assert report_resp.status_code == 200
    assert report_resp.headers["content-type"] == "application/pdf"
    assert "attachment" in report_resp.headers["content-disposition"]
    assert report_resp.content[:4] == b"%PDF"

    reader = PdfReader(io.BytesIO(report_resp.content))
    full_text = reader.pages[0].extract_text()
    assert "Report Download Test House" in full_text


def test_report_endpoint_404s_for_a_genuinely_nonexistent_design():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.post("/api/construction-studio/design/does-not-exist-12345/report", json={
        "floors": [{"floor_label": "Ground Floor", "rooms": SAMPLE_ROOMS}],
    })
    assert r.status_code == 404


def test_report_endpoint_rejects_empty_floors():
    from fastapi.testclient import TestClient
    from backend.api import app
    from backend.auth_store import create_otp
    from backend.subscription_store import upsert_subscription

    client = TestClient(app)
    email = "report_empty_floors_test@example.com"
    code = create_otp(email)
    r_verify = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    headers = {"Authorization": f"Bearer {r_verify.json()['session_token']}"}
    upsert_subscription(email=email, tier_id="studio_starter", dodo_subscription_id="sub_reportdl2", status="active")

    design_resp = client.post("/api/construction-studio/design", headers=headers, json={
        "plot_size_sqft": 1200, "plot_length_ft": PLOT_LENGTH, "plot_width_ft": PLOT_WIDTH,
        "selections": {"structure": "rcc_frame"},
        "entrance_direction": "north", "road_facing_side": "north", "region": "india", "currency": "INR",
        "rooms": SAMPLE_ROOMS,
    })
    design_id = design_resp.json()["design_id"]

    r = client.post(f"/api/construction-studio/design/{design_id}/report", json={"floors": []})
    assert r.status_code == 400
