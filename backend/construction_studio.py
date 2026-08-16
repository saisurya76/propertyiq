import json
from pathlib import Path
from typing import Any, Optional

_DATA_PATH = Path(__file__).parent / "data" / "construction_materials.json"

with open(_DATA_PATH, "r", encoding="utf-8") as _f:
    _CATALOG = json.load(_f)


def get_fx_rates() -> dict[str, float]:
    """USD-based FX table used for both Construction Studio cost estimates
    and Studio tier pricing display — one shared source of truth."""
    return dict(_CATALOG["fx_rates_usd_base"])


def _build_catalog(source: dict[str, Any], region: str = "global") -> dict[str, Any]:
    """Shared catalog-building logic for both materials (_CATALOG["categories"])
    and labor/contractor items (_CATALOG["labor_categories"]) — same option
    shape, same region-filtering rules, just a different source section."""

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
            if region in opt["regions"] or "global" in opt["regions"]
        ]
        if options:
            categories_out[cat_id] = {"label": cat["label"], "options": options}

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
    specific; other regions simply see no labor_categories entries."""
    return _build_catalog(_CATALOG.get("labor_categories", {}), region)


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

        line_cost_usd = round(opt["base_cost_usd_per_sqft"] * plot_size_sqft, 2)
        material_subtotal_usd += line_cost_usd

        line_items.append({
            "kind": "material",
            "category": category,
            "option_id": option_id,
            "name": opt["name"],
            "unit_cost_usd": opt["base_cost_usd_per_sqft"],
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

    favorable_entrances = {"north", "east", "north-east"}
    notes = []
    compliant = True

    entrance = (entrance_direction or "").strip().lower()
    road = (road_facing_side or "").strip().lower()
    slope = (slope_direction or "").strip().lower() if slope_direction else None

    if entrance not in favorable_entrances:
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
        if slope in {"south", "west", "south-west"}:
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
