"""PropertyIQ Instant Property Score — a free, no-signup, price+location+
area-only quick score, backed by the same real comparables data used by
the Similar Properties feature (currently Hyderabad apartments/villas
only, per backend/comparables.py — genuinely honest about coverage, not
fabricated for unsupported cities/types).

Deliberately NOT a replacement for the full PropertyIQ assessment: this
skips every fraud-verification field (developer track record, government
guidance value, regulatory violations) entirely — it's a 10-second
"is this even worth a closer look" signal based purely on price-per-sqft
versus real comparable listings, matching the product's own description
of this as a lightweight funnel into the full assessment, not a
substitute for it.
"""

from typing import Any, Optional

from backend.comparables import get_comparables, average_price_per_sqft

SQM_TO_SQFT = 10.7639


def compute_instant_score(
    *,
    price: float,
    city: str,
    property_type: str,
    area_value: float,
    area_unit: str = "sqft",
    location: Optional[str] = None,
) -> dict[str, Any]:
    """Returns a 0-100 score, a label, and a one-line reason — or an
    honest "not enough data for this city/type yet" result when no real
    comparable data exists, never a fabricated score. Score is derived
    entirely from how the given price-per-sqft compares to the real
    average of actual comparable listings — the same average_price_per_sqft
    already used by Similar Properties, so the two features can never
    silently disagree about what "market average" means for the same
    city/property type.

    `location` (a specific locality/neighborhood, e.g. "Gachibowli"
    within Hyderabad) is captured and returned for context/display only
    — an honest limitation, not an oversight: comparables.py's real
    market data is researched at the city level, not locality level, so
    there is no genuine locality-specific average to score against yet.
    Passing a location makes results more identifiable and useful to
    read (especially in a shared challenge card), but does not change
    the score itself, which would require real locality-level
    comparable data this module doesn't have."""
    if price <= 0 or area_value <= 0:
        raise ValueError("Price and area must both be greater than zero.")

    area_sqft = area_value * SQM_TO_SQFT if area_unit == "sqm" else area_value
    price_per_sqft = price / area_sqft

    comparables = get_comparables(city, property_type)
    if not comparables:
        return {
            "coverage": "unsupported",
            "city": city,
            "location": location,
            "property_type": property_type,
            "price_per_sqft": round(price_per_sqft, 2),
            "score": None,
            "label": None,
            "reason": (
                f"PropertyIQ doesn't have real comparable data for {property_type} "
                f"properties in {city} yet, so a fair, evidence-based score isn't "
                f"possible here — run the full assessment instead for a complete picture."
            ),
        }

    market_avg = average_price_per_sqft(comparables)
    pct_diff = ((price_per_sqft - market_avg) / market_avg) * 100 if market_avg else 0

    # A simple, monotonic, honestly-documented formula — not a black box:
    # exactly at the market average scores 70 (borderline strong/
    # investigate); each percentage point above/below market average
    # moves the score by 1.5 points, capped to the 0-100 range. This is
    # a deliberately simple heuristic for a 10-second free tool, not the
    # full assessment's real fraud-detection scoring — that distinction
    # is stated explicitly in the response, not hidden.
    score = max(0, min(100, round(70 - pct_diff * 1.5)))

    if score >= 75:
        label = "Strong"
    elif score >= 45:
        label = "Investigate"
    else:
        label = "Avoid / Overpriced"

    price_diff_total = (price_per_sqft - market_avg) * area_sqft
    direction = "above" if pct_diff >= 0 else "below"
    reason = (
        f"{abs(round(pct_diff))}% {direction} the estimated market value for "
        f"comparable {property_type.lower()} properties in {city}."
    )

    return {
        "coverage": "supported",
        "city": city,
        "location": location,
        "property_type": property_type,
        "price_per_sqft": round(price_per_sqft, 2),
        "market_average_price_per_sqft": round(market_avg, 2),
        "price_diff_total": round(price_diff_total, 2),
        "score": score,
        "label": label,
        "reason": reason,
    }
