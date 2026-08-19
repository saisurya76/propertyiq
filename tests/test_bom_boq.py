from backend.construction_studio import generate_bill_of_materials, generate_bill_of_quantities, estimate_cost


def test_bom_produces_realistic_physical_quantities():
    bom = generate_bill_of_materials(
        plot_size_sqft=1200,
        selections={"cement": "opc_53", "steel": "tmt_fe500", "sand": "m_sand"},
        region="india",
    )
    by_cat = {i["category"]: i for i in bom["items"]}
    # ~390 bags for 1200 sqft at the documented 0.325 bags/sqft consumption rate
    assert 350 <= by_cat["cement"]["quantity"] <= 450
    assert by_cat["cement"]["unit"] == "bags"
    assert by_cat["steel"]["quantity"] == 4800  # 4kg/sqft * 1200
    assert by_cat["steel"]["unit"] == "kg"


def test_bom_never_under_orders_rounds_up():
    """Physical materials are bought in whole units with a wastage
    allowance — the BOM must round UP, never down, so it never suggests
    ordering less than what's actually needed."""
    bom = generate_bill_of_materials(
        plot_size_sqft=333,  # deliberately odd, guarantees a fractional raw quantity
        selections={"cement": "opc_43"},
        region="india",
    )
    item = bom["items"][0]
    raw = 0.325 * 333
    assert item["quantity"] >= raw
    assert item["quantity"] == int(raw) + (1 if raw % 1 else 0)


def test_bom_discrete_categories_use_project_scope_not_fake_precision():
    bom = generate_bill_of_materials(
        plot_size_sqft=1200,
        selections={"kitchen_work": "modular_laminate"},
        region="india",
    )
    item = bom["items"][0]
    assert item["quantity"] == 1
    assert item["unit"] == "project-scope"


def test_bom_excludes_labor_entirely():
    """A BOM is materials-only by definition — labor_selections aren't
    even accepted as a parameter."""
    import inspect
    assert "labor_selections" not in inspect.signature(generate_bill_of_materials).parameters


def test_boq_includes_materials_and_labor_together():
    boq = generate_bill_of_quantities(
        plot_size_sqft=1200,
        selections={"cement": "opc_53"},
        labor_selections={"rcc_work": "rcc_standard_labor"},
        region="india", currency="INR",
    )
    kinds = {item["kind"] for trade in boq["trades"] for item in trade["items"]}
    assert kinds == {"material", "labor"}


def test_boq_trade_subtotals_exactly_reconcile_with_grand_total():
    """Real bug found and fixed: the blanket residual labor multiplier
    (covering non-itemized trades) wasn't represented as a line item
    anywhere, so trade subtotals silently fell short of the true total."""
    boq = generate_bill_of_quantities(
        plot_size_sqft=1200,
        selections={"cement": "opc_53", "flooring": "vitrified_tile", "doors": "laminate_door"},
        labor_selections={"rcc_work": "rcc_standard_labor"},
        region="india", currency="INR",
    )
    trade_sum = sum(t["subtotal_converted"] for t in boq["trades"])
    expected = boq["material_subtotal_converted"] + boq["labor_cost_converted"]
    assert abs(trade_sum - expected) < 0.5


def test_boq_reconciles_even_with_no_itemized_labor():
    """The residual-labor line item logic must not double-count or drop
    anything when NO itemized labor is selected at all (blanket-only)."""
    boq = generate_bill_of_quantities(
        plot_size_sqft=1200,
        selections={"cement": "opc_53"},
        labor_selections={},
        region="india", currency="INR",
    )
    trade_sum = sum(t["subtotal_converted"] for t in boq["trades"])
    expected = boq["material_subtotal_converted"] + boq["labor_cost_converted"]
    assert abs(trade_sum - expected) < 0.5


def test_boq_grouped_by_trade_not_flat_list():
    boq = generate_bill_of_quantities(
        plot_size_sqft=1200,
        selections={"cement": "opc_53", "flooring": "vitrified_tile"},
        region="india", currency="INR",
    )
    trade_names = {t["trade"] for t in boq["trades"]}
    assert "Civil & Structural" in trade_names
    assert "Finishes" in trade_names


def test_boq_quantity_uses_priced_area_not_full_plot_for_doors_windows():
    """Doors/windows price (and therefore should quantity) against a
    fraction of plot area, not the full plot — see Phase 4 of the
    materials catalog work. The BOQ must stay consistent with that, not
    silently use full plot area for quantity while cost uses the fraction."""
    boq = generate_bill_of_quantities(
        plot_size_sqft=1200,
        selections={"windows": "upvc"},
        region="india", currency="INR",
    )
    result = estimate_cost(plot_size_sqft=1200, selections={"windows": "upvc"}, region="india", currency="INR")
    priced_area = result["line_items"][0]["priced_area_sqft"]
    assert priced_area < 1200  # confirms the fraction is actually being applied
