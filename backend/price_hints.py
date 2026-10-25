"""Suggested values for the report form's "Government Guidance Value" and
"Market Average" boxes.

Honest scope: we only have city-level market data (comparables.py, plus a
live feed for some Indian cities) and one built-in government rate
(data/government). Nothing here is street or locality level. Where we have
no number we say so and point the visitor to the official source instead of
guessing. Rates are returned per the unit the visitor chose on the form."""
from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote_plus

from backend.comparables import get_comparables
from backend.government_data_provider import get_government_rate

UNIT_FACTORS = {"sqft": 1.0, "sq yard": 9.0, "sq meter": 10.7639, "acre": 43560.0, "hectare": 107639.0}

CURRENCY = {"india": "INR", "thailand": "THB", "philippines": "PHP", "vietnam": "VND", "indonesia": "IDR"}

# What the official figure is called, and who publishes it, per country, and
# for the Indian states whose name we are sure of.
COUNTRY_SOURCE = {
    "india": ("circle rate / ready reckoner / guidance value", "the Sub-Registrar's office or your state registration department"),
    "thailand": ("government appraised value", "the Treasury Department / Land Department"),
    "philippines": ("BIR zonal value", "the Bureau of Internal Revenue (Revenue District Office)"),
    "vietnam": ("government land price list (bảng giá đất)", "your provincial People's Committee"),
    "indonesia": ("NJOP (Nilai Jual Objek Pajak)", "your local tax office (PBB), shown on the PBB bill"),
}
INDIA_STATE_TERM = {
    "maharashtra": "Ready Reckoner rate (IGR Maharashtra)",
    "karnataka": "Guidance value (Kaveri, Dept of Stamps & Registration)",
    "tamil nadu": "Guideline value (TNREGINET)",
    "delhi": "Circle rate (Delhi Revenue Department)",
    "gujarat": "Jantri rate",
    "uttar pradesh": "Circle rate (Stamp & Registration Dept)",
    "kerala": "Fair value of land (Registration Dept)",
    "rajasthan": "DLC rate (Sub-Registrar)",
    "haryana": "Collector rate",
    "telangana": "Market value guidelines (Registration & Stamps)",
    "goa": "Zonal / guideline value (Dept of Registration)",
}


def _round(v: float) -> float:
    if v >= 1000:
        return float(round(v, -1))
    return float(round(v, 2))


def _per_unit(rate_per_sqft: float, unit: str) -> float:
    return _round(rate_per_sqft * UNIT_FACTORS[unit])


def get_hints(country: str, state: str, city: str, property_type: str, area_unit: str, locality: str = "") -> dict[str, Any]:
    ckey = (country or "").strip().lower()
    unit = (area_unit or "sqft").strip().lower()
    if unit not in UNIT_FACTORS:
        unit = "sqft"
    out: dict[str, Any] = {
        "currency": CURRENCY.get(ckey, ""),
        "area_unit": unit,
        "market": {"available": False},
        "government": {"available": False},
        "locality_note": "These are city-level figures. Your exact locality can differ a lot, so treat them as a starting point.",
    }

    if city and property_type:
        comps = get_comparables(city, property_type)
        prices = [c.price_per_sqft for c in comps if c.price_per_sqft and c.price_per_sqft > 0]
        if prices:
            avg = sum(prices) / len(prices)
            live = any("Live" in c.project_name for c in comps)
            out["market"] = {
                "available": True,
                "value": _per_unit(avg, unit),
                "low": _per_unit(min(prices), unit),
                "high": _per_unit(max(prices), unit),
                "count": len(prices),
                "source": f"{'Live asking prices' if live else 'Our market data'} for {property_type.lower()} in {city}",
                "live": live,
            }

    try:
        rate = get_government_rate(country, state, city, property_type)
        out["government"] = {
            "available": True,
            "value": _per_unit(float(rate), unit),
            "source": f"Built-in {city} reference rate",
        }
    except (KeyError, FileNotFoundError, ValueError, TypeError):
        pass

    if not out["government"]["available"]:
        term, publisher = COUNTRY_SOURCE.get(ckey, ("official government property value", "your local land or tax office"))
        if ckey == "india":
            term = INDIA_STATE_TERM.get((state or "").strip().lower(), term)
        where = ", ".join(p for p in [(locality or "").strip(), city, state] if p)
        out["government"]["how_to"] = {
            "name": term,
            "publisher": publisher,
            "search_url": "https://www.google.com/search?q=" + quote_plus(f"{term} {where} {country}".strip()),
        }
    return out
