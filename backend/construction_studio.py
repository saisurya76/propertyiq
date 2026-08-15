import json
from pathlib import Path
from typing import Any, Optional

_DATA_PATH = Path(__file__).parent / "data" / "construction_materials.json"

with open(_DATA_PATH, "r", encoding="utf-8") as _f:
    _CATALOG = json.load(_f)


def get_catalog(region: str = "global") -> dict[str, Any]:
    """Return material categories/options available for a region, with base
    costs still in USD (currency conversion happens in estimate_cost)."""

    region = (region or "global").strip().lower()
    categories_out = {}

    for cat_id, cat in _CATALOG["categories"].items():
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


def _find_option(category: str, option_id: str) -> Optional[dict[str, Any]]:
    cat = _CATALOG["categories"].get(category)
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
    region: str = "global",
    currency: str = "USD",
) -> dict[str, Any]:
    """Compute a running cost estimate given plot size and one selected
    material option per category. selections = {category_id: option_id}.
    Returns a line-item breakdown plus grand total, converted to `currency`.
    """

    region = (region or "global").strip().lower()
    labor_index = _CATALOG["labor_cost_index"].get(region, _CATALOG["labor_cost_index"]["global"])
    fx_rates = _CATALOG["fx_rates_usd_base"]
    fx_rate = fx_rates.get(currency.upper(), 1.0)

    line_items = []
    material_subtotal_usd = 0.0

    for category, option_id in selections.items():
        opt = _find_option(category, option_id)
        if not opt:
            continue

        line_cost_usd = round(opt["base_cost_usd_per_sqft"] * plot_size_sqft, 2)
        material_subtotal_usd += line_cost_usd

        line_items.append({
            "category": category,
            "option_id": option_id,
            "name": opt["name"],
            "unit_cost_usd": opt["base_cost_usd_per_sqft"],
            "line_total_usd": line_cost_usd,
            "line_total_converted": round(line_cost_usd * fx_rate, 2),
        })

    labor_cost_usd = round(material_subtotal_usd * labor_index, 2)
    grand_total_usd = round(material_subtotal_usd + labor_cost_usd, 2)

    return {
        "currency": currency.upper(),
        "fx_rate_usd_to_currency": fx_rate,
        "region": region,
        "plot_size_sqft": plot_size_sqft,
        "line_items": line_items,
        "material_subtotal_usd": round(material_subtotal_usd, 2),
        "material_subtotal_converted": round(material_subtotal_usd * fx_rate, 2),
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
