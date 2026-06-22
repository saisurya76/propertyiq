def generate_executive_summary(
    property_name: str,
    quoted_price: float,
    fair_value: float,
    buyer_protection_score: float,
    buyer_protection_rating: str,
    recommendation: str,
    inventory_risk: str,
    developer_rating: str
):

    price_gap = round(
        ((quoted_price - fair_value) / fair_value) * 100,
        2
    )

    summary = f"""
Property: {property_name}

Quoted Price: {quoted_price:,.0f}

Estimated Fair Value: {fair_value:,.0f}

Price Premium: {price_gap}%

Buyer Protection Score:
{buyer_protection_score}/100
({buyer_protection_rating})

Developer Rating:
{developer_rating}

Inventory Risk:
{inventory_risk}

Recommended Action:
{recommendation}
"""

    return summary.strip()