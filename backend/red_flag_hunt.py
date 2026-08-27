"""PropertyIQ "Red Flag Hunt" — an interactive "can you spot the red
flag?" quiz. User picks one category they think is suspicious about a
property; PropertyIQ tells them whether that's a genuine concern, a false
alarm, or — for categories this quick check has no real basis to judge —
honestly says so instead of pretending to verify something it can't.

Deliberately reuses compute_instant_score internally (same as
Hidden Deal) rather than re-implementing the price-vs-comparables math, so
none of these three quick-check features can ever disagree about the same
property's market position.

Same honesty standard throughout: with only price + city + property type +
area as input, "Price" and "Area" (mathematically linked via
price-per-sqft) are the only categories this feature has any real basis to
judge. Builder, Location, Amenities, and "Other claim" get an honest
"this quick check can't verify that — the full assessment does" verdict,
never a fabricated correct/false-alarm judgment about something with zero
actual data behind it.
"""

from typing import Any, Optional

from backend.instant_score import compute_instant_score

VALID_CATEGORIES = ["Price", "Area", "Builder", "Location", "Amenities", "Other"]

_NO_BASIS_VERDICTS = {
    "Builder": "This quick check only looks at price versus comparable listings — it has no real "
               "data on this developer's track record. The full PropertyIQ assessment checks projects "
               "completed, delayed, and regulatory violations directly.",
    "Location": "This quick check doesn't independently verify location claims — the full assessment "
                "looks at this more closely.",
    "Amenities": "This quick check has no data on amenities at all — it's purely a price comparison. "
                 "Amenity claims need their own verification.",
    "Other": "This quick check can't evaluate a claim like that with just price, city, type, and area — "
             "the full assessment covers a much wider range of verification.",
}


def evaluate_red_flag_guess(
    *,
    price: float,
    city: str,
    property_type: str,
    area_value: float,
    area_unit: str,
    guessed_category: str,
    location: Optional[str] = None,
) -> dict[str, Any]:
    """Returns a verdict for the user's guessed category, plus up to 2
    additional findings (from the same real logic Hidden Deal uses) they
    should investigate — genuinely computed, not fabricated to hit a
    round number of "findings".

    `location` is passed straight through to compute_instant_score for
    context/display only — see that function's own docstring for why it
    doesn't (yet) change the underlying verdict, which is city-level."""
    if guessed_category not in VALID_CATEGORIES:
        raise ValueError(f"guessed_category must be one of {VALID_CATEGORIES}")

    score_result = compute_instant_score(
        price=price, city=city, property_type=property_type,
        area_value=area_value, area_unit=area_unit, location=location,
    )

    if score_result["coverage"] == "unsupported":
        return {
            "coverage": "unsupported",
            "location": location,
            "guessed_category": guessed_category,
            "verdict": "unknown",
            "verdict_detail": score_result["reason"],
            "additional_findings": [],
        }

    pct_diff = round(
        ((score_result["price_per_sqft"] - score_result["market_average_price_per_sqft"])
         / score_result["market_average_price_per_sqft"]) * 100
    ) if score_result["market_average_price_per_sqft"] else 0

    is_genuine_price_concern = abs(pct_diff) > 10

    if guessed_category in ("Price", "Area"):
        if is_genuine_price_concern:
            verdict = "correct"
            direction = "above" if pct_diff > 0 else "below"
            verdict_detail = (
                f"Good catch — this property is priced {abs(pct_diff)}% {direction} comparable "
                f"{property_type.lower()} properties in {city}, a genuine signal worth investigating."
            )
        else:
            verdict = "false_alarm"
            verdict_detail = (
                f"Actually not a concern here — at {abs(pct_diff)}% from the comparable average, "
                f"this property's pricing is within a normal range for {city}."
            )
    else:
        verdict = "unknown"
        verdict_detail = _NO_BASIS_VERDICTS[guessed_category]

    # The additional findings the user should still investigate — the
    # genuine price signal (if they didn't already guess it and it's real)
    # plus the fixed, honest scope-gap finding. Never pads to a fixed
    # count with anything fabricated.
    additional_findings = []
    if guessed_category not in ("Price", "Area") and is_genuine_price_concern:
        direction = "above" if pct_diff > 0 else "below"
        additional_findings.append({
            "icon": "💰",
            "title": "Pricing Anomaly",
            "detail": f"This property is priced {abs(pct_diff)}% {direction} comparable {property_type.lower()} properties in {city}.",
        })
    additional_findings.append({
        "icon": "⚠️",
        "title": "Risk / Missing Information",
        "detail": (
            "This quick check doesn't cover the developer's track record, government guidance value "
            "comparison, or regulatory violation history — the full PropertyIQ assessment does."
        ),
    })

    return {
        "coverage": "supported",
        "location": location,
        "guessed_category": guessed_category,
        "verdict": verdict,
        "verdict_detail": verdict_detail,
        "additional_findings": additional_findings,
    }
