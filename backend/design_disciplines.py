"""Organizes Construction Studio's flat cost-estimate line items into
real construction disciplines (Structural, Plumbing, Electrical, etc)
for the Generate Design output — previously one undifferentiated list
mixing every material category together with no way to see "what's my
plumbing going to cost" separately from "what's my flooring going to
cost."

CATEGORY_DISCIPLINES is the single source of truth for this grouping —
every real material/labor category in construction_materials.json must
appear here exactly once. group_by_discipline() is a pure function over
estimate_cost()'s existing line_items output; it doesn't change what
estimate_cost() computes or its own top-level response shape, so nothing
that already reads cost_estimate directly is affected — this is a new,
additive view over the same real numbers, not a replacement calculation.
"""

from typing import Any

DISCIPLINE_LABELS = {
    "structural": "Structural",
    "plumbing": "Plumbing",
    "electrical": "Electrical",
    "finishes": "Finishes & Interior",
    "roofing": "Roofing",
    "waterproofing": "Waterproofing",
    "hvac": "HVAC & Ventilation",
    "fire_safety": "Fire Safety",
}

# Every real category id from construction_materials.json's "categories"
# and "labor_categories" sections must be mapped here exactly once — see
# test_design_disciplines.py's own guard test for this.
CATEGORY_DISCIPLINES = {
    # Structural: the plot's actual frame/shell, and the raw materials
    # + contractor labor that build it.
    "structure": "structural",
    "cement": "structural",
    "steel": "structural",
    "bricks": "structural",
    "aggregate": "structural",
    "sand": "structural",
    "rcc_work": "structural",
    "brickwork": "structural",
    "plasterwork": "structural",
    # Plumbing: water supply/drainage plus the fixtures it feeds.
    "plumbing": "plumbing",
    "sanitary_fittings": "plumbing",
    # Electrical: wiring, fixtures, panels.
    "electrical": "electrical",
    # Finishes & Interior: what a room actually looks/feels like day to
    # day — floor, paint, openings, kitchen.
    "flooring": "finishes",
    "painting": "finishes",
    "doors": "finishes",
    "windows": "finishes",
    "kitchen_work": "finishes",
    # Roofing and Waterproofing are real, distinct trades in Indian
    # residential construction, not "finishes" — kept as their own
    # sections rather than folded into structural or finishes.
    "roofing": "roofing",
    "waterproofing": "waterproofing",
    # HVAC/Ventilation and Fire Safety: genuine catalog gaps identified
    # during the design-output audit — see construction_materials.json's
    # own comment on these categories for the honest scaling methodology
    # (typical-home equipment cost divided by representative sqft,
    # since these are discrete equipment purchases, not a true
    # per-sqft market rate the way flooring/painting genuinely are).
    "hvac_ventilation": "hvac",
    "fire_safety": "fire_safety",
}


def group_by_discipline(line_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Groups estimate_cost()'s line_items by discipline, computing a
    real subtotal per section from the same converted-currency figures
    already on each line item (never recomputed/re-derived — this is
    strictly a regrouping of numbers estimate_cost() already produced).
    A category with no real assignment in CATEGORY_DISCIPLINES lands in
    an honestly-labeled "Other" section rather than silently being
    dropped from the output."""
    sections: dict[str, dict[str, Any]] = {}

    for item in line_items:
        discipline = CATEGORY_DISCIPLINES.get(item["category"], "other")
        if discipline not in sections:
            sections[discipline] = {
                "discipline": discipline,
                "label": DISCIPLINE_LABELS.get(discipline, "Other"),
                "line_items": [],
                "subtotal_usd": 0.0,
                "subtotal_converted": 0.0,
            }
        sections[discipline]["line_items"].append(item)
        sections[discipline]["subtotal_usd"] += item["line_total_usd"]
        sections[discipline]["subtotal_converted"] += item["line_total_converted"]

    for section in sections.values():
        section["subtotal_usd"] = round(section["subtotal_usd"], 2)
        section["subtotal_converted"] = round(section["subtotal_converted"], 2)

    # Stable, meaningful order rather than whatever order dict insertion
    # happened to produce (which depends on selection order, not
    # anything a reader would find predictable).
    order = ["structural", "plumbing", "electrical", "hvac", "fire_safety", "finishes", "roofing", "waterproofing", "other"]
    return [sections[d] for d in order if d in sections]
