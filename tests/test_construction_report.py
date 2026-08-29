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


def test_report_shows_the_real_room_names_inside_the_discipline_diagrams():
    """The exact, real bug the user reported: the structural/plumbing/
    electrical diagrams showed blank space where the room layout should
    be. Confirms the actual room names now appear as extractable text
    (meaning they're genuinely drawn, not just present in the room-
    summary table elsewhere in the report)."""
    pdf_bytes = generate_construction_report_pdf(_sample_design(), [{"floor_label": "Ground Floor", "rooms": SAMPLE_ROOMS}])
    reader = PdfReader(io.BytesIO(pdf_bytes))
    # The structural diagram page specifically (not just the room-summary
    # table page) must contain the room names as drawn text.
    structural_page_text = next(p.extract_text() for p in reader.pages if "Ground Floor — Structural" in p.extract_text())
    assert "kitchen" in structural_page_text.lower() or "Kitchen" in structural_page_text


def test_report_property_name_is_shown_prominently_even_though_header_shows_the_brand():
    """The header always shows the PropertyIQ brand name (matching the
    reference report's own convention of the product name, not a
    per-report title) -- confirms the user's own property name is still
    shown clearly elsewhere, not lost entirely."""
    pdf_bytes = generate_construction_report_pdf(_sample_design(), [{"floor_label": "Ground Floor", "rooms": SAMPLE_ROOMS}], property_name="My Dream Home")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    cover_text = reader.pages[0].extract_text()
    assert "PropertyIQ" in cover_text
    assert "My Dream Home" in cover_text


def test_report_uses_a_real_report_id_derived_from_design_id():
    pdf_bytes = generate_construction_report_pdf(_sample_design(), [{"floor_label": "Ground Floor", "rooms": SAMPLE_ROOMS}], design_id="16163735-46ee-4bfc-91ee-536d7a3dc7c5")
    reader = PdfReader(io.BytesIO(pdf_bytes))
    cover_text = reader.pages[0].extract_text()
    assert "PIQ-16163735" in cover_text
    # Every page's footer must show the same report ID, not just the cover
    last_page_text = reader.pages[-1].extract_text()
    assert "PIQ-16163735" in last_page_text


def test_report_shows_genuine_page_x_of_y_numbering():
    pdf_bytes = generate_construction_report_pdf(_sample_design(), [{"floor_label": "Ground Floor", "rooms": SAMPLE_ROOMS}])
    reader = PdfReader(io.BytesIO(pdf_bytes))
    total_pages = len(reader.pages)
    first_page_text = reader.pages[0].extract_text()
    last_page_text = reader.pages[-1].extract_text()
    assert f"Page 1 of {total_pages}" in first_page_text
    assert f"Page {total_pages} of {total_pages}" in last_page_text


def test_report_footer_includes_privacy_and_terms_links_on_every_page():
    pdf_bytes = generate_construction_report_pdf(_sample_design(), [{"floor_label": "Ground Floor", "rooms": SAMPLE_ROOMS}])
    reader = PdfReader(io.BytesIO(pdf_bytes))
    for page in reader.pages:
        text = page.extract_text()
        assert "Privacy Policy" in text
        assert "Terms of Service" in text


def test_entrance_and_road_facing_display_without_raw_underscores():
    """A real polish bug caught during visual review: an entrance
    direction like 'north_west' displayed with a literal underscore
    instead of a space -- confirms it's now formatted properly."""
    design = _sample_design()
    design["plot_spec"]["entrance_direction"] = "north_west"
    design["plot_spec"]["road_facing_side"] = "south_east"
    pdf_bytes = generate_construction_report_pdf(design, [{"floor_label": "Ground Floor", "rooms": SAMPLE_ROOMS}])
    reader = PdfReader(io.BytesIO(pdf_bytes))
    cover_text = reader.pages[0].extract_text()
    assert "North West" in cover_text
    assert "South East" in cover_text
    assert "north_west" not in cover_text
    assert "south_east" not in cover_text
