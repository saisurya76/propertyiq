def calculate_overpricing_percent(
    quoted_price: float,
    fair_value: float
) -> float:

    if fair_value <= 0:
        raise ValueError(
            "Fair value must be greater than zero."
        )

    return round(
        (
            (quoted_price - fair_value)
            / fair_value
        ) * 100,
        2
    )


def get_recommendation(
    overpricing_percent: float,
    inventory_risk: str,
    developer_rating: str,
    buyer_protection_score: float
) -> str:

    # Hard Risk Overrides

    if (
        developer_rating == "WEAK"
        and inventory_risk == "SEVERE"
    ):
        return "AVOID"

    if buyer_protection_score < 60:
        return "AVOID"

    if buyer_protection_score < 70:
        return "PROCEED WITH EXTREME CAUTION"

    if buyer_protection_score < 80:
        return "BUY AFTER NEGOTIATION"

    # Strong Projects

    if overpricing_percent <= 5:
        return "BUY"

    if overpricing_percent <= 15:
        return "BUY AFTER NEGOTIATION"

    if overpricing_percent <= 25:
        return "WAIT"

    return "AVOID"


def get_recommendation_reasons(
    overpricing_percent: float,
    inventory_risk: str,
    developer_rating: str,
    buyer_protection_score: float
) -> list[str]:

    reasons = []

    # Valuation

    if overpricing_percent < -5:

        reasons.append(
            f"Property is {abs(overpricing_percent)}% below estimated fair value."
        )

    elif overpricing_percent <= 5:

        reasons.append(
            "Property pricing is broadly aligned with estimated fair value."
        )

    else:

        reasons.append(
            f"Property is {overpricing_percent}% above estimated fair value."
        )

    # Inventory

    reasons.append(
        f"Inventory Risk: {inventory_risk}"
    )

    # Developer

    reasons.append(
        f"Developer Rating: {developer_rating}"
    )

    # Buyer Protection

    reasons.append(
        f"Buyer Protection Score: {buyer_protection_score}"
    )

    return reasons