import json
import math
from pathlib import Path
from typing import Any, Optional

_DATA_PATH = Path(__file__).parent / "data" / "construction_materials.json"

with open(_DATA_PATH, "r", encoding="utf-8") as _f:
    _CATALOG = json.load(_f)


def get_fx_rates() -> dict[str, float]:
    """USD-based FX table used for both Construction Studio cost estimates
    and Studio tier pricing display — one shared source of truth."""
    return dict(_CATALOG["fx_rates_usd_base"])


def _build_catalog(source: dict[str, Any], region: str = "global", global_is_catchall: bool = True) -> dict[str, Any]:
    """Shared catalog-building logic for both materials (_CATALOG["categories"])
    and labor/contractor items (_CATALOG["labor_categories"]) — same option
    shape, same region-filtering rules, just a different source section.

    global_is_catchall controls whether requesting region="global" shows
    EVERY region's options (appropriate for materials — a generic/other
    user seeing a broad catalog is reasonable) or shows nothing beyond
    options explicitly tagged "global" (appropriate for labor — India-
    specific labor/contractor conventions genuinely don't generalize to
    an arbitrary "global/other" user the way raw material options do)."""

    region = (region or "global").strip().lower()
    categories_out = {}

    for cat_id, cat in source.items():
        options = [
            {
                "id": opt["id"],
                "name": opt["name"],
                "unit": opt["unit"],
                "base_cost_usd": opt["base_cost_usd_per_sqft"],
                "suppliers": [
                    s["name"] for s in opt["suppliers"]
                    if s["region"] == region or s["region"] == "global"
                ] or [s["name"] for s in opt["suppliers"]],
            }
            for opt in cat["options"]
            if region in opt["regions"] or (region == "global" and global_is_catchall)
        ]
        if options:
            categories_out[cat_id] = {
                "label": cat["label"],
                "options": options,
                "opening_area_fraction": cat.get("opening_area_fraction"),
            }

    return categories_out


def get_catalog(region: str = "global") -> dict[str, Any]:
    """Return material categories/options available for a region, with base
    costs still in USD (currency conversion happens in estimate_cost)."""
    return _build_catalog(_CATALOG["categories"], region)


def get_labor_catalog(region: str = "global") -> dict[str, Any]:
    """Return contractor/labor categories (RCC work, brickwork, plasterwork)
    available for a region — separate from materials, matching how these
    are actually quoted in Indian residential construction (a distinct
    civil-contractor cost bucket, not a material line item). India-only
    for now — the researched rates and regional convention are India-
    specific; other regions simply see no labor_categories entries.
    Deliberately global_is_catchall=False: unlike materials, a "global/
    other" user shouldn't see India-specific labor/contractor conventions
    as a default fallback — that's a real, meaningful distinction, not an
    oversight (confirmed by an existing test asserting exactly this)."""
    return _build_catalog(_CATALOG.get("labor_categories", {}), region, global_is_catchall=False)


def _find_option(category: str, option_id: str, source: dict[str, Any] = None) -> Optional[dict[str, Any]]:
    source = _CATALOG["categories"] if source is None else source
    cat = source.get(category)
    if not cat:
        return None
    for opt in cat["options"]:
        if opt["id"] == option_id:
            return opt
    return None


def estimate_cost(
    *,
    plot_size_sqft: float,
    selections: dict[str, str],
    labor_selections: Optional[dict[str, str]] = None,
    region: str = "global",
    currency: str = "USD",
) -> dict[str, Any]:
    """Compute a running cost estimate given plot size, one selected
    material option per category, and (optionally) one selected labor/
    contractor option per trade (RCC work, brickwork, plasterwork).
    selections/labor_selections = {category_id: option_id}.
    Returns a line-item breakdown (each tagged "kind": "material" or
    "labor") plus grand total, converted to `currency`.

    The blanket regional labor_cost_index (a flat % of material cost)
    already accounts for ALL labor by default — but for India, it was
    deliberately reduced (0.35 -> 0.13) specifically because RCC/brickwork/
    plasterwork are now itemized here instead; adding both without that
    reduction would double-count the single largest chunk of labor cost.
    The remaining 0.13 covers electrical/plumbing/painting labor and
    supervision overhead, which stay un-itemized.
    """

    region = (region or "global").strip().lower()
    labor_index = _CATALOG["labor_cost_index"].get(region, _CATALOG["labor_cost_index"]["global"])
    fx_rates = _CATALOG["fx_rates_usd_base"]
    fx_rate = fx_rates.get(currency.upper(), 1.0)

    line_items = []
    material_subtotal_usd = 0.0

    for category, option_id in selections.items():
        opt = _find_option(category, option_id, _CATALOG["categories"])
        if not opt:
            continue

        # Most categories price per sqft of the WHOLE plot (flooring, roofing,
        # etc. — these genuinely scale with plot area). Categories with an
        # `opening_area_fraction` (doors, windows) instead price per sqft of
        # actual OPENING area, estimated as that fraction of the plot —
        # window fraction (0.12) is sourced from NBC 2016's 10% minimum
        # window-to-floor-area rule, leaning toward Telangana/Hyderabad's
        # humid-climate recommendation (15-20%); door fraction (0.04) is a
        # rougher estimate from typical door-schedule norms. Without this,
        # a $14/sqft window price applied to the FULL plot produces a wildly
        # unrealistic total, as if the entire plot were glazed.
        opening_fraction = _CATALOG["categories"][category].get("opening_area_fraction")
        priced_area_sqft = plot_size_sqft * opening_fraction if opening_fraction else plot_size_sqft

        line_cost_usd = round(opt["base_cost_usd_per_sqft"] * priced_area_sqft, 2)
        material_subtotal_usd += line_cost_usd

        line_items.append({
            "kind": "material",
            "category": category,
            "option_id": option_id,
            "name": opt["name"],
            "unit_cost_usd": opt["base_cost_usd_per_sqft"],
            "priced_area_sqft": round(priced_area_sqft, 1),
            "line_total_usd": line_cost_usd,
            "line_total_converted": round(line_cost_usd * fx_rate, 2),
        })

    itemized_labor_subtotal_usd = 0.0
    for category, option_id in (labor_selections or {}).items():
        opt = _find_option(category, option_id, _CATALOG.get("labor_categories", {}))
        if not opt:
            continue

        line_cost_usd = round(opt["base_cost_usd_per_sqft"] * plot_size_sqft, 2)
        itemized_labor_subtotal_usd += line_cost_usd

        line_items.append({
            "kind": "labor",
            "category": category,
            "option_id": option_id,
            "name": opt["name"],
            "unit_cost_usd": opt["base_cost_usd_per_sqft"],
            "line_total_usd": line_cost_usd,
            "line_total_converted": round(line_cost_usd * fx_rate, 2),
        })

    blanket_labor_cost_usd = round(material_subtotal_usd * labor_index, 2)
    labor_cost_usd = round(blanket_labor_cost_usd + itemized_labor_subtotal_usd, 2)
    grand_total_usd = round(material_subtotal_usd + labor_cost_usd, 2)

    return {
        "currency": currency.upper(),
        "fx_rate_usd_to_currency": fx_rate,
        "region": region,
        "plot_size_sqft": plot_size_sqft,
        "line_items": line_items,
        "material_subtotal_usd": round(material_subtotal_usd, 2),
        "material_subtotal_converted": round(material_subtotal_usd * fx_rate, 2),
        "itemized_labor_subtotal_usd": round(itemized_labor_subtotal_usd, 2),
        "itemized_labor_subtotal_converted": round(itemized_labor_subtotal_usd * fx_rate, 2),
        "labor_cost_usd": labor_cost_usd,
        "labor_cost_converted": round(labor_cost_usd * fx_rate, 2),
        "grand_total_usd": grand_total_usd,
        "grand_total_converted": round(grand_total_usd * fx_rate, 2),
    }


VASTU_FAVORABLE_ENTRANCES = {"north", "east", "north-east"}
VASTU_UNFAVORABLE_SLOPES = {"south", "west", "south-west"}


def check_vastu_basics(
    *,
    entrance_direction: str,
    road_facing_side: str,
    slope_direction: Optional[str] = None,
) -> dict[str, Any]:
    """Lightweight Vastu directional check (entrance/road/slope alignment
    only). This is a basic pass, NOT the full multi-rule Vastu engine
    (room placement, kitchen/toilet zones, plot shape) — that is a
    separate, larger phase. Flagged clearly so this isn't mistaken for
    a complete compliance audit.
    """

    notes = []
    compliant = True

    entrance = (entrance_direction or "").strip().lower()
    road = (road_facing_side or "").strip().lower()
    slope = (slope_direction or "").strip().lower() if slope_direction else None

    if entrance not in VASTU_FAVORABLE_ENTRANCES:
        compliant = False
        notes.append(
            f"Entrance facing '{entrance_direction}' is considered less favorable in classical Vastu; "
            "North, East, or North-East entrances are generally preferred."
        )
    else:
        notes.append(f"Entrance facing '{entrance_direction}' aligns with favorable Vastu directions.")

    if road and entrance and road != entrance:
        notes.append(
            f"Note: entrance direction ('{entrance_direction}') differs from the road-facing side ('{road_facing_side}'). "
            "Confirm this is intentional in your plot layout."
        )

    if slope:
        if slope in VASTU_UNFAVORABLE_SLOPES:
            compliant = False
            notes.append(
                f"Slope toward '{slope_direction}' is traditionally considered unfavorable; "
                "a slope toward North or East is generally preferred for water drainage."
            )
        else:
            notes.append(f"Slope toward '{slope_direction}' is generally acceptable in classical Vastu.")

    return {
        "compliant": compliant,
        "notes": notes,
        "scope": "basic_directional_check_only",
    }


def identify_construction_risks(
    *,
    region: str,
    grand_total_usd: float,
    currency: str,
    has_imported_materials: bool = False,
) -> list[str]:
    """Construction-specific risk section, following the same plain-language
    pattern as backend/risk_engine.py used for valuation reports."""

    risks = []

    risks.append(
        "Material and labor prices are estimates based on current regional averages and can fluctuate "
        "with market conditions, seasonal demand, and supplier availability."
    )

    if currency.upper() != "USD":
        risks.append(
            f"This estimate is converted from USD to {currency.upper()} at a reference exchange rate; "
            "actual costs may vary with currency fluctuations between now and time of purchase."
        )

    if has_imported_materials:
        risks.append(
            "Selected materials sourced outside the local region may be subject to import duties, "
            "shipping delays, and additional currency exposure."
        )

    if grand_total_usd > 150000:
        risks.append(
            "Large-scale builds are more exposed to extended timelines, which can compound cost "
            "overruns from inflation and supplier price changes over the construction period."
        )

    risks.append(
        "Supplier and material availability listed here reflect a curated regional dataset and should "
        "be independently verified with local vendors before finalizing a build budget."
    )

    return risks


def generate_bill_of_materials(
    *,
    plot_size_sqft: float,
    selections: dict[str, str],
    region: str = "global",
) -> dict[str, Any]:
    """A Bill of Materials — a procurement list: WHAT to buy and HOW MUCH,
    for the selected material options only (no labor, no cost totals —
    that's what a BOQ is for; see generate_bill_of_quantities below). This
    is the genuine distinction between the two documents in real
    construction/procurement practice: a BOM answers "what do I order,"
    a BOQ answers "what does the whole job cost, trade by trade."

    Categories without a real per-sqft physical consumption rate on file
    (structure, roofing, electrical, plumbing, kitchen_work,
    sanitary_fittings — whole-system items that don't reduce to a clean
    per-sqft physical unit the way cement/bricks/sand do) are listed with
    quantity "1 (project-scope)" rather than a fabricated precise number.
    """

    region = (region or "global").strip().lower()
    items = []

    for category, option_id in selections.items():
        opt = _find_option(category, option_id, _CATALOG["categories"])
        if not opt:
            continue

        quantity_per_sqft = opt.get("quantity_per_sqft")
        quantity_unit = opt.get("quantity_unit")

        if quantity_per_sqft is not None:
            raw_quantity = quantity_per_sqft * plot_size_sqft
            # Physical materials are bought in whole units with a standard
            # wastage allowance — round up, not to the nearest whole
            # number, so the list never under-orders.
            quantity = math.ceil(raw_quantity)
            unit = quantity_unit
        else:
            quantity = 1
            unit = "project-scope"

        items.append({
            "category": category,
            "option_id": option_id,
            "name": opt["name"],
            "quantity": quantity,
            "unit": unit,
            "suppliers": [s["name"] for s in opt["suppliers"] if s["region"] == region or s["region"] == "global"]
            or [s["name"] for s in opt["suppliers"]],
        })

    return {
        "plot_size_sqft": plot_size_sqft,
        "region": region,
        "items": items,
    }


# Trade groupings for the BOQ's work-package structure — matches how a
# real Indian residential BOQ is conventionally organized (civil work
# first, then finishes, then services), not just an arbitrary alphabetical
# dump of categories.
BOQ_TRADE_GROUPS = [
    ("Civil & Structural", ["structure", "cement", "steel", "bricks", "aggregate", "sand", "rcc_work", "brickwork", "plasterwork"]),
    ("Roofing & Waterproofing", ["roofing", "waterproofing"]),
    ("Finishes", ["flooring", "painting", "doors", "windows"]),
    ("Kitchen & Sanitary", ["kitchen_work", "sanitary_fittings"]),
    ("Electrical & Plumbing", ["electrical", "plumbing"]),
]


def generate_bill_of_quantities(
    *,
    plot_size_sqft: float,
    selections: dict[str, str],
    labor_selections: Optional[dict[str, str]] = None,
    region: str = "global",
    currency: str = "USD",
) -> dict[str, Any]:
    """A Bill of Quantities — the broader, contract/tender-grade document:
    every work item (materials AND labor together), grouped by trade,
    with quantity, unit rate, and line total for each — matching the
    real-world distinction from a BOM (materials-only procurement list).
    Reuses the same per-item cost math as estimate_cost() so the BOQ's
    totals always reconcile exactly with the live running estimate shown
    elsewhere in the Studio, rather than risking two independently-
    maintained pricing paths drifting apart."""

    cost = estimate_cost(
        plot_size_sqft=plot_size_sqft,
        selections=selections,
        labor_selections=labor_selections or {},
        region=region,
        currency=currency,
    )
    line_items_by_category = {li["category"]: li for li in cost["line_items"]}
    quantity_lookup = {
        f"{li['category']}:{li['option_id']}": li for li in cost["line_items"]
    }

    catalog_options = {}
    for cat_id, cat in _CATALOG["categories"].items():
        for opt in cat["options"]:
            catalog_options[(cat_id, opt["id"])] = opt

    grouped = []
    categorized = set()

    for trade_label, category_ids in BOQ_TRADE_GROUPS:
        trade_items = []
        for category in category_ids:
            li = line_items_by_category.get(category)
            if not li:
                continue
            categorized.add(category)

            opt = catalog_options.get((category, li["option_id"]))
            quantity_per_sqft = opt.get("quantity_per_sqft") if opt else None
            if quantity_per_sqft is not None:
                # Use the SAME priced area estimate_cost() actually used for
                # this line (e.g. doors/windows price against a fraction of
                # plot area, not the full plot — see Phase 4 of the
                # materials catalog work) so quantity and cost stay
                # consistent with each other, not silently drifting apart.
                priced_area = li.get("priced_area_sqft", plot_size_sqft)
                quantity = round(quantity_per_sqft * priced_area, 1)
                unit = opt.get("quantity_unit")
            else:
                quantity = 1
                unit = "lot"

            trade_items.append({
                "category": category,
                "description": li["name"],
                "kind": li["kind"],
                "quantity": quantity,
                "unit": unit,
                "unit_rate_converted": li["line_total_converted"] / quantity if quantity else li["line_total_converted"],
                "line_total_converted": li["line_total_converted"],
            })

        if trade_items:
            grouped.append({
                "trade": trade_label,
                "items": trade_items,
                "subtotal_converted": round(sum(i["line_total_converted"] for i in trade_items), 2),
            })

    # Anything not covered by the fixed trade groupings above (e.g. a
    # future category that hasn't been slotted into one yet) still shows
    # up, rather than silently vanishing from the document.
    leftover = [li for cat, li in line_items_by_category.items() if cat not in categorized]

    # The blanket "residual" labor (electrical/plumbing/painting labor and
    # supervision overhead — the part of labor_cost_index NOT covered by
    # itemized RCC/Brickwork/Plasterwork selections, see Phase 2 of the
    # materials catalog work) is a real cost but was never represented as
    # its own line item anywhere — without it, the BOQ's trade subtotals
    # would silently NOT sum to the true grand total, which is a real
    # correctness bug for a document whose entire purpose is trustworthy
    # itemized accounting. Confirmed by direct test: trade subtotals came
    # up short of material+labor by exactly this residual amount.
    residual_labor_converted = round(cost["labor_cost_converted"] - sum(
        li["line_total_converted"] for li in cost["line_items"] if li["kind"] == "labor"
    ), 2)

    other_items = [{
        "category": li["category"], "description": li["name"], "kind": li["kind"],
        "quantity": 1, "unit": "lot",
        "unit_rate_converted": li["line_total_converted"], "line_total_converted": li["line_total_converted"],
    } for li in leftover]

    if residual_labor_converted > 0.01:
        other_items.append({
            "category": "_overhead_labor", "description": "General Labor & Supervision (electrical, plumbing, painting labor, site overhead)",
            "kind": "labor", "quantity": 1, "unit": "lot",
            "unit_rate_converted": residual_labor_converted, "line_total_converted": residual_labor_converted,
        })

    if other_items:
        grouped.append({
            "trade": "Other",
            "items": other_items,
            "subtotal_converted": round(sum(i["line_total_converted"] for i in other_items), 2),
        })

    return {
        "plot_size_sqft": plot_size_sqft,
        "region": region,
        "currency": cost["currency"],
        "trades": grouped,
        "material_subtotal_converted": cost["material_subtotal_converted"],
        "labor_cost_converted": cost["labor_cost_converted"],
        "grand_total_converted": cost["grand_total_converted"],
    }
