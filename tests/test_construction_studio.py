from backend.construction_studio import (
    get_catalog,
    estimate_cost,
    check_vastu_basics,
    identify_construction_risks,
)


def test_catalog_returns_categories_for_region():
    catalog = get_catalog("india")
    assert "structure" in catalog
    assert "flooring" in catalog
    for cat in catalog.values():
        assert len(cat["options"]) > 0


def test_catalog_global_region_has_generic_supplier_fallback():
    catalog = get_catalog("global")
    assert "structure" in catalog


def test_estimate_cost_scales_with_plot_size():
    selections = {"structure": "rcc_frame", "flooring": "vitrified_tile"}
    small = estimate_cost(plot_size_sqft=1000, selections=selections, region="india", currency="USD")
    large = estimate_cost(plot_size_sqft=2000, selections=selections, region="india", currency="USD")
    assert large["grand_total_usd"] > small["grand_total_usd"]
    # doubling plot size should roughly double material subtotal
    assert abs(large["material_subtotal_usd"] - 2 * small["material_subtotal_usd"]) < 0.01


def test_estimate_cost_currency_conversion():
    selections = {"structure": "rcc_frame"}
    usd = estimate_cost(plot_size_sqft=1000, selections=selections, region="india", currency="USD")
    inr = estimate_cost(plot_size_sqft=1000, selections=selections, region="india", currency="INR")
    assert inr["grand_total_converted"] > usd["grand_total_converted"]
    assert inr["currency"] == "INR"


def test_estimate_cost_ignores_unknown_option():
    result = estimate_cost(
        plot_size_sqft=1000,
        selections={"structure": "does_not_exist"},
        region="india",
        currency="USD",
    )
    assert result["line_items"] == []
    assert result["grand_total_usd"] == 0


def test_vastu_favorable_entrance_compliant():
    result = check_vastu_basics(entrance_direction="north-east", road_facing_side="north-east")
    assert result["compliant"] is True


def test_vastu_unfavorable_entrance_flagged():
    result = check_vastu_basics(entrance_direction="south-west", road_facing_side="south-west")
    assert result["compliant"] is False
    assert any("less favorable" in note for note in result["notes"])


def test_vastu_unfavorable_slope_flagged():
    result = check_vastu_basics(
        entrance_direction="north", road_facing_side="north", slope_direction="south-west"
    )
    assert result["compliant"] is False


def test_construction_risks_includes_currency_note_for_non_usd():
    risks = identify_construction_risks(
        region="india", grand_total_usd=50000, currency="INR", has_imported_materials=False
    )
    assert any("currency" in r.lower() for r in risks)


def test_construction_risks_includes_import_note():
    risks = identify_construction_risks(
        region="india", grand_total_usd=50000, currency="USD", has_imported_materials=True
    )
    assert any("import" in r.lower() for r in risks)


def test_fx_rates_endpoint():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.get("/api/fx-rates")
    assert r.status_code == 200
    data = r.json()
    assert data["USD"] == 1.0
    assert "INR" in data and data["INR"] > 1


def test_dxf_hex_to_true_color_conversion():
    from backend.construction_dxf import _hex_to_true_color
    import ezdxf

    assert _hex_to_true_color("#7c3aed") == ezdxf.colors.rgb2int((124, 58, 237))
    assert _hex_to_true_color(None) is None
    assert _hex_to_true_color("") is None
    assert _hex_to_true_color("not-a-color") is None
    assert _hex_to_true_color("#zzzzzz") is None


def test_dimension_chain_segments_sum_to_full_plot():
    from backend.construction_dxf import _compute_edge_dimension_segments

    rooms = [
        {"name": "Living Room", "x": 0, "y": 20, "length": 20, "width": 10},
        {"name": "Bedroom", "x": 20, "y": 20, "length": 10, "width": 10},
        {"name": "Bathroom", "x": 0, "y": 0, "length": 8, "width": 8},
        {"name": "Master Bedroom", "x": 0, "y": 12, "length": 10, "width": 8},
    ]
    plot_length_ft, plot_width_ft = 40, 30

    north = _compute_edge_dimension_segments(rooms, plot_length_ft, plot_width_ft, "north")
    west = _compute_edge_dimension_segments(rooms, plot_length_ft, plot_width_ft, "west")

    assert abs(sum(s["length"] for s in north) - plot_length_ft) < 0.01
    assert abs(sum(s["length"] for s in west) - plot_width_ft) < 0.01
    assert len(north) == 3
    assert len(west) == 4


def test_dimension_chain_no_rooms_touching_edge_falls_back_to_full_span():
    from backend.construction_dxf import _compute_edge_dimension_segments

    rooms = [{"name": "Center Room", "x": 15, "y": 10, "length": 10, "width": 10}]
    segments = _compute_edge_dimension_segments(rooms, 40, 30, "north")
    assert len(segments) == 1
    assert segments[0]["length"] == 40


def test_generated_dxf_contains_real_dimension_entities(tmp_path):
    from backend.construction_dxf import generate_plot_dxf
    import ezdxf

    rooms = [
        {"name": "Living Room", "x": 0, "y": 20, "length": 20, "width": 10, "color": None},
        {"name": "Bedroom", "x": 20, "y": 20, "length": 10, "width": 10, "color": None},
    ]
    path = generate_plot_dxf(
        design_id="dim_pytest",
        plot_length_ft=40,
        plot_width_ft=30,
        rooms=rooms,
        road_facing_side="north",
        output_dir=tmp_path,
    )

    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    dim_texts = [e.dxf.text for e in msp if e.dxftype() == "TEXT" and e.dxf.layer == "DIMENSIONS"]

    assert "40' total" in dim_texts
    assert any("20" in t for t in dim_texts)


def test_site_elements_produce_distinct_dxf_entities(tmp_path):
    from backend.construction_dxf import generate_plot_dxf
    import ezdxf

    site_elements = [
        {"type": "tree", "x": 2, "y": 2, "length": 6, "width": 6, "color": "#22c55e"},
        {"type": "gazebo", "x": 15, "y": 2, "length": 10, "width": 10, "color": None},
        {"type": "pool", "x": 2, "y": 15, "length": 16, "width": 8, "color": None},
        {"type": "line", "x": 0, "y": 25, "x2": 40, "y2": 25, "color": None},
        {"type": "dotted_line", "x": 0, "y": 28, "x2": 40, "y2": 28, "color": None},
    ]
    path = generate_plot_dxf(
        design_id="site_elements_pytest",
        plot_length_ft=40, plot_width_ft=30,
        rooms=[], site_elements=site_elements, road_facing_side="north",
        output_dir=tmp_path,
    )
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    entities = [e for e in msp if e.dxf.layer == "SITE_ELEMENTS"]

    assert any(e.dxftype() == "CIRCLE" for e in entities)
    assert any(e.dxftype() == "LWPOLYLINE" and len(e.get_points()) == 7 for e in entities)  # gazebo hexagon
    assert any(e.dxftype() == "LINE" and e.dxf.linetype == "DASHED" for e in entities)
    assert any(e.dxftype() == "LINE" and e.dxf.linetype != "DASHED" for e in entities)


def test_generate_plot_dxf_backward_compatible_without_site_elements(tmp_path):
    from backend.construction_dxf import generate_plot_dxf

    # Existing callers that don't pass site_elements at all must still work.
    path = generate_plot_dxf(
        design_id="no_site_elements_pytest",
        plot_length_ft=40, plot_width_ft=30,
        rooms=[{"name": "Kitchen", "x": 2, "y": 2, "length": 8, "width": 6, "color": None}],
        road_facing_side="north",
        output_dir=tmp_path,
    )
    assert path.exists()


def test_rotate_point_90_degrees_lands_on_axis():
    from backend.construction_dxf import _rotate_point
    x, y = _rotate_point(10, 0, 0, 0, 90)
    assert abs(x) < 0.001


def test_rotate_point_full_circle_is_identity():
    from backend.construction_dxf import _rotate_point
    x, y = _rotate_point(10, 5, 2, 3, 360)
    assert abs(x - 10) < 0.001
    assert abs(y - 5) < 0.001


def test_rotated_element_produces_genuinely_rotated_dxf_geometry(tmp_path):
    from backend.construction_dxf import generate_plot_dxf
    import ezdxf

    site_elements = [
        {"type": "pool", "x": 0, "y": 0, "length": 16, "width": 8, "color": None, "rotation": 45},
    ]
    path = generate_plot_dxf(
        design_id="rotate_pytest", plot_length_ft=40, plot_width_ft=30,
        rooms=[], site_elements=site_elements, road_facing_side="north",
        output_dir=tmp_path,
    )
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    poly = [e for e in msp if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "SITE_ELEMENTS"][0]
    points = list(poly.get_points())

    # Pivot corner (x, y) stays put; an unrotated rect's second corner
    # would still sit on the x-axis (y=0) — after a genuine 45deg rotation
    # it must not.
    assert abs(points[0][0]) < 0.01 and abs(points[0][1]) < 0.01
    assert abs(points[1][1]) > 0.01


def test_tree_symbol_has_layered_canopy_not_a_single_circle(tmp_path):
    from backend.construction_dxf import generate_plot_dxf
    import ezdxf

    site_elements = [{"type": "tree", "x": 2, "y": 2, "length": 6, "width": 6, "color": "#22c55e"}]
    path = generate_plot_dxf(
        design_id="tree_art_pytest", plot_length_ft=40, plot_width_ft=30,
        rooms=[], site_elements=site_elements, road_facing_side="north",
        output_dir=tmp_path,
    )
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    circles = [e for e in msp if e.dxftype() == "CIRCLE" and e.dxf.layer == "SITE_ELEMENTS"]
    assert len(circles) == 4  # main canopy + 2 offset lobes + trunk mark


def test_car_symbol_has_wheels_and_windshield(tmp_path):
    from backend.construction_dxf import generate_plot_dxf
    import ezdxf

    site_elements = [{"type": "car", "x": 5, "y": 5, "length": 15, "width": 7, "color": None, "rotation": 30}]
    path = generate_plot_dxf(
        design_id="car_art_pytest", plot_length_ft=40, plot_width_ft=30,
        rooms=[], site_elements=site_elements, road_facing_side="north",
        output_dir=tmp_path,
    )
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    circles = [e for e in msp if e.dxftype() == "CIRCLE" and e.dxf.layer == "SITE_ELEMENTS"]
    lines = [e for e in msp if e.dxftype() == "LINE" and e.dxf.layer == "SITE_ELEMENTS"]
    assert len(circles) == 4
    assert len(lines) == 1


def test_new_material_categories_load_and_price_correctly():
    from backend.construction_studio import get_catalog, estimate_cost

    catalog = get_catalog("india")
    new_categories = {
        "cement", "steel", "bricks", "aggregate", "sand",
        "painting", "kitchen_work", "sanitary_fittings", "waterproofing",
    }
    for cat_id in new_categories:
        assert cat_id in catalog, f"missing category: {cat_id}"
        assert len(catalog[cat_id]["options"]) >= 2

    result = estimate_cost(
        plot_size_sqft=1000,
        selections={"cement": "opc_43", "steel": "tmt_fe415"},
        region="india",
        currency="USD",
    )
    assert len(result["line_items"]) == 2
    assert result["grand_total_converted"] > 0


def test_labor_categories_load_and_no_double_counting():
    from backend.construction_studio import get_labor_catalog, estimate_cost

    labor_cat = get_labor_catalog("india")
    assert set(labor_cat.keys()) == {"rcc_work", "brickwork", "plasterwork"}
    for cat in labor_cat.values():
        assert len(cat["options"]) == 3

    # Labor categories are India-only — should be empty for other regions.
    assert get_labor_catalog("usa") == {}
    assert get_labor_catalog("global") == {}

    result = estimate_cost(
        plot_size_sqft=1200,
        selections={"cement": "opc_53"},
        labor_selections={"rcc_work": "rcc_standard_labor"},
        region="india", currency="INR",
    )
    # Itemized labor + reduced blanket residual must land in a realistic
    # total-labor range (~350-600 INR/sqft per researched norms), not
    # double-count by stacking the OLD full blanket rate on top.
    labor_per_sqft_inr = result["labor_cost_usd"] * 83.5 / 1200
    assert 100 < labor_per_sqft_inr < 700, f"labor/sqft out of realistic range: {labor_per_sqft_inr}"

    kinds = {li["kind"] for li in result["line_items"]}
    assert kinds == {"material", "labor"}


def test_estimate_backward_compatible_without_labor_selections():
    from backend.construction_studio import estimate_cost

    # Existing callers that never pass labor_selections must still work.
    result = estimate_cost(plot_size_sqft=1000, selections={"cement": "opc_43"}, region="india", currency="USD")
    assert result["itemized_labor_subtotal_usd"] == 0
    assert result["grand_total_usd"] > 0


def test_doors_and_windows_are_separate_categories_with_distinct_pricing():
    from backend.construction_studio import get_catalog

    catalog = get_catalog("india")
    assert "doors_windows" not in catalog
    assert "doors" in catalog and "windows" in catalog

    door_names = {o["name"] for o in catalog["doors"]["options"]}
    window_names = {o["name"] for o in catalog["windows"]["options"]}
    assert "Flush Door (Basic, Hollow Core)" in door_names
    assert "UPVC Frames" in window_names
    # Doors and windows must have genuinely distinct pricing conventions
    # (door-type pricing vs frame-material pricing), not the same options
    # just relabeled.
    assert door_names.isdisjoint(window_names)


def test_doors_windows_price_by_opening_area_not_full_plot():
    from backend.construction_studio import estimate_cost

    result = estimate_cost(
        plot_size_sqft=1200,
        selections={"windows": "upvc", "doors": "laminate_door"},
        region="india", currency="USD",
    )
    window_li = next(li for li in result["line_items"] if li["category"] == "windows")
    door_li = next(li for li in result["line_items"] if li["category"] == "doors")

    # Must price against a FRACTION of plot area, not the full 1200 sqft —
    # this was a real pre-existing bug (confirmed unchanged from the
    # original catalog) that made a $14/sqft window price look like it
    # covered the entire plot.
    assert window_li["priced_area_sqft"] == 1200 * 0.12
    assert door_li["priced_area_sqft"] == 1200 * 0.12
    assert window_li["priced_area_sqft"] < 1200
    assert door_li["priced_area_sqft"] < 1200


def test_categories_without_opening_fraction_still_use_full_plot_area():
    from backend.construction_studio import estimate_cost

    result = estimate_cost(
        plot_size_sqft=1200,
        selections={"flooring": "vitrified_tile"},
        region="india", currency="USD",
    )
    li = result["line_items"][0]
    assert li["priced_area_sqft"] == 1200
