"""PropertyIQ "Hidden Deal" — a curiosity-driven, staged-reveal feature.
Rather than immediately showing a full report, surfaces 3 real findings
about the property one at a time, funneling toward the full assessment.

Deliberately reuses compute_instant_score internally rather than
re-implementing the same price-vs-comparables logic — so this feature and
Instant Property Score can never silently disagree about the same
property's market position. Same honesty standard: every finding is
derived from real data (the actual comparables dataset) or is an honest
statement about what this quick check does NOT cover — never a fabricated
or generic-sounding "insight" with nothing real behind it.
"""

from typing import Any

from backend.instant_score import compute_instant_score

# This finding never depends on comparables data — it's an honest
# statement about the real, fixed scope gap between this quick check and
# the full assessment, true regardless of which city/property type is
# checked. Kept as a named constant since it's reused in both the
# "supported" and "unsupported" comparables-coverage cases below.
_MISSING_INFO_FINDING = {
    "icon": "⚠️",
    "title": "Risk / Missing Information",
    "detail": (
        "This quick check doesn't cover the developer's track record, government "
        "guidance value comparison, or regulatory violation history — the full "
        "PropertyIQ assessment checks all of these independently."
    ),
}


def find_hidden_deal_insights(
    *,
    price: float,
    city: str,
    property_type: str,
    area_value: float,
    area_unit: str = "sqft",
) -> dict[str, Any]:
    """Returns up to 3 real findings about the property, meant to be
    revealed to the user one at a time by the frontend (this function
    itself just returns the full, real result — staging the reveal is a
    presentation concern, not something to fake server-side). Raises the
    same ValueError as compute_instant_score for invalid input."""
    score_result = compute_instant_score(
        price=price, city=city, property_type=property_type,
        area_value=area_value, area_unit=area_unit,
    )

    if score_result["coverage"] == "unsupported":
        # Honest, not fabricated: without real comparable data, there's
        # no basis for a pricing-anomaly or negotiation finding — only
        # the one finding that's true regardless of data coverage.
        return {
            "coverage": "unsupported",
            "findings": [_MISSING_INFO_FINDING],
            "reason": score_result["reason"],
        }

    pct_diff = round(
        ((score_result["price_per_sqft"] - score_result["market_average_price_per_sqft"])
         / score_result["market_average_price_per_sqft"]) * 100
    ) if score_result["market_average_price_per_sqft"] else 0

    if pct_diff > 5:
        pricing_finding = {
            "icon": "💰",
            "title": "Pricing Anomaly",
            "detail": f"This property is priced {pct_diff}% above comparable {property_type.lower()} properties in {city}.",
        }
        negotiation_finding = {
            "icon": "💡",
            "title": "Potential Negotiation Opportunity",
            "detail": (
                f"Given the {pct_diff}% premium over comparable pricing, there may be room to "
                f"negotiate toward the market average before committing."
            ),
        }
    elif pct_diff < -5:
        pricing_finding = {
            "icon": "💰",
            "title": "Pricing Anomaly",
            "detail": f"This property is priced {abs(pct_diff)}% below comparable {property_type.lower()} properties in {city} — worth understanding why.",
        }
        negotiation_finding = {
            "icon": "💡",
            "title": "Potential Negotiation Opportunity",
            "detail": (
                "The price is already below comparable listings — negotiation room may be limited, "
                "and a genuinely good deal like this can move quickly."
            ),
        }
    else:
        pricing_finding = {
            "icon": "💰",
            "title": "Pricing Anomaly",
            "detail": f"This property is priced close to the market average for comparable {property_type.lower()} properties in {city} — no unusual pricing signal either way.",
        }
        negotiation_finding = {
            "icon": "💡",
            "title": "Potential Negotiation Opportunity",
            "detail": "Pricing is already in line with the market, so there's likely limited room to negotiate purely on price.",
        }

    return {
        "coverage": "supported",
        "findings": [pricing_finding, _MISSING_INFO_FINDING, negotiation_finding],
        "score": score_result["score"],
        "label": score_result["label"],
    }
