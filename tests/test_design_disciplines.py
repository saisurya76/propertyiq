import json

import pytest

from backend.design_disciplines import group_by_discipline, CATEGORY_DISCIPLINES, DISCIPLINE_LABELS
from backend.construction_studio import estimate_cost, _CATALOG


def test_every_real_category_is_mapped_to_a_discipline():
    """The real, important guard: every material AND labor category
    that actually exists in the catalog must be explicitly mapped —
    an unmapped category would silently fall into 'Other' rather than
    genuinely failing, so this test is the only thing that catches a
    newly-added catalog category (e.g. a future material subtype) not
    yet assigned a discipline."""
    all_real_categories = set(_CATALOG["categories"].keys()) | set(_CATALOG.get("labor_categories", {}).keys())
    unmapped = all_real_categories - set(CATEGORY_DISCIPLINES.keys())
    assert unmapped == set(), f"These real categories have no discipline assigned: {unmapped}"


def test_grouping_preserves_the_real_total_cost():
    """The regrouping must never lose or duplicate money -- summing
    every section's subtotal must equal the original material subtotal
    (within float rounding) from the same real estimate_cost() call."""
    result = estimate_cost(
        plot_size_sqft=1200,
        selections={"structure": "rcc_frame", "flooring": "vitrified_tile", "roofing": "rcc_slab"},
        region="india", currency="INR",
    )
    sections = group_by_discipline(result["line_items"])
    total_from_sections = sum(s["subtotal_converted"] for s in sections)
    assert total_from_sections == pytest.approx(result["material_subtotal_converted"], abs=0.05)


def test_selected_categories_land_in_the_correct_real_sections():
    result = estimate_cost(
        plot_size_sqft=1200,
        selections={"structure": "rcc_frame", "flooring": "vitrified_tile", "roofing": "rcc_slab",
                    "painting": "interior_emulsion", "doors": "flush_door_basic"},
        region="india", currency="INR",
    )
    sections = group_by_discipline(result["line_items"])
    by_discipline = {s["discipline"]: s for s in sections}

    assert "structural" in by_discipline
    assert any(i["category"] == "structure" for i in by_discipline["structural"]["line_items"])

    assert "roofing" in by_discipline
    assert any(i["category"] == "roofing" for i in by_discipline["roofing"]["line_items"])

    assert "finishes" in by_discipline
    finishes_categories = {i["category"] for i in by_discipline["finishes"]["line_items"]}
    assert finishes_categories == {"flooring", "painting", "doors"}


def test_labor_selections_land_in_structural_section():
    result = estimate_cost(
        plot_size_sqft=1200,
        selections={"structure": "rcc_frame"},
        labor_selections={"rcc_work": next(iter(_CATALOG["labor_categories"]["rcc_work"]["options"]))["id"]},
        region="india", currency="INR",
    )
    sections = group_by_discipline(result["line_items"])
    structural = next(s for s in sections if s["discipline"] == "structural")
    labor_items = [i for i in structural["line_items"] if i["kind"] == "labor"]
    assert len(labor_items) == 1
    assert labor_items[0]["category"] == "rcc_work"


def test_sections_appear_in_a_stable_meaningful_order_not_insertion_order():
    """Sections must not depend on dict insertion order (which would
    vary with the order selections happen to be passed in) -- confirms
    the fixed, meaningful order regardless of selection order."""
    result = estimate_cost(
        plot_size_sqft=1200,
        # Deliberately out of "natural" order
        selections={"waterproofing": next(iter(_CATALOG["categories"]["waterproofing"]["options"]))["id"],
                    "structure": "rcc_frame", "electrical": next(iter(_CATALOG["categories"]["electrical"]["options"]))["id"]},
        region="india", currency="INR",
    )
    sections = group_by_discipline(result["line_items"])
    disciplines_in_order = [s["discipline"] for s in sections]
    assert disciplines_in_order == ["structural", "electrical", "waterproofing"]


def test_empty_line_items_returns_empty_sections():
    assert group_by_discipline([]) == []


def test_discipline_labels_are_all_real_human_readable_strings():
    for discipline, label in DISCIPLINE_LABELS.items():
        assert isinstance(label, str) and len(label) > 0


def test_hvac_and_fire_safety_categories_are_real_and_correctly_grouped():
    """The two genuine catalog gaps identified during the design-output
    audit -- confirms they're now real, selectable categories that land
    in their own honestly-labeled sections, not folded into an
    unrelated discipline."""
    from backend.construction_studio import get_catalog

    catalog = get_catalog("india")
    assert "hvac_ventilation" in catalog
    assert "fire_safety" in catalog
    hvac_ids = {o["id"] for o in catalog["hvac_ventilation"]["options"]}
    fire_ids = {o["id"] for o in catalog["fire_safety"]["options"]}
    assert "basic_ventilation_ac_prep" in hvac_ids
    assert "basic_fire_safety" in fire_ids

    result = estimate_cost(
        plot_size_sqft=1200,
        selections={"hvac_ventilation": "premium_hvac_prep", "fire_safety": "enhanced_fire_safety"},
        region="india", currency="INR",
    )
    sections = group_by_discipline(result["line_items"])
    by_discipline = {s["discipline"]: s for s in sections}

    assert "hvac" in by_discipline
    assert by_discipline["hvac"]["label"] == "HVAC & Ventilation"
    assert by_discipline["hvac"]["line_items"][0]["category"] == "hvac_ventilation"

    assert "fire_safety" in by_discipline
    assert by_discipline["fire_safety"]["label"] == "Fire Safety"
    assert by_discipline["fire_safety"]["line_items"][0]["category"] == "fire_safety"


def test_hvac_and_fire_safety_appear_in_the_correct_section_order():
    result = estimate_cost(
        plot_size_sqft=1200,
        selections={"structure": "rcc_frame", "hvac_ventilation": "basic_ventilation_ac_prep",
                    "fire_safety": "basic_fire_safety", "flooring": "vitrified_tile"},
        region="india", currency="INR",
    )
    sections = group_by_discipline(result["line_items"])
    disciplines_in_order = [s["discipline"] for s in sections]
    assert disciplines_in_order == ["structural", "hvac", "fire_safety", "finishes"]
