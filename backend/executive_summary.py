def format_currency(value):

    if value >= 10000000:
        return f"₹{value / 10000000:.2f} Cr"

    if value >= 100000:
        return f"₹{value / 100000:.2f} L"

    return f"₹{value:,.0f}"

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

    if price_gap >= 0:
        price_position = (
            f"{price_gap}% Above Fair Value"
        )
    else:
        price_position = (
            f"{abs(price_gap)}% Below Fair Value"
        )

    summary = f"""
Property: {property_name}

Quoted Price: {format_currency(quoted_price)}

Estimated Fair Value: {format_currency(fair_value)}

Price Position: {price_position}

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