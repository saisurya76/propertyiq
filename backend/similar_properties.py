from dataclasses import asdict
from typing import Any, Optional

from backend.comparables import get_comparables, average_price_per_sqft


def get_similar_properties(
    *,
    city: str,
    property_type: str,
    subject_price_per_sqft: float,
    max_results: int = 5,
) -> dict[str, Any]:
    """Similar property suggestions with vital params, ranked by closeness
    to the subject property's price/sqft.

    Vital params returned per suggestion: price_per_sqft, price_diff_percent
    (vs the subject property, signed — negative means cheaper), developer,
    property_type, city.

    Currently only returns real data for regions with a comparables dataset
    (Hyderabad today, per backend/comparables.py) — returns an explicit
    "coverage": "unsupported" result for anything else rather than
    fabricating data, so the caller can show an honest "not available yet"
    state instead of an empty list that looks like "no matches found".
    """

    comparables = get_comparables(city, property_type)

    if not comparables:
        return {
            "city": city,
            "property_type": property_type,
            "coverage": "unsupported",
            "suggestions": [],
            "market_average_price_per_sqft": 0,
        }

    market_avg = average_price_per_sqft(comparables)

    suggestions = []
    for comp in comparables:
        diff_percent = 0.0
        if subject_price_per_sqft > 0:
            diff_percent = round(
                ((comp.price_per_sqft - subject_price_per_sqft) / subject_price_per_sqft) * 100,
                2,
            )
        suggestions.append({
            **asdict(comp),
            "price_diff_percent": diff_percent,
            "closeness_rank": abs(comp.price_per_sqft - subject_price_per_sqft),
        })

    suggestions.sort(key=lambda s: s["closeness_rank"])
    for s in suggestions:
        del s["closeness_rank"]

    return {
        "city": city,
        "property_type": property_type,
        "coverage": "supported",
        "suggestions": suggestions[:max_results],
        "market_average_price_per_sqft": market_avg,
    }
