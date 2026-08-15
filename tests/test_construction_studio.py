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
