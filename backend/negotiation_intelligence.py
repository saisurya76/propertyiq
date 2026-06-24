from dataclasses import dataclass


@dataclass
class NegotiationIntelligence:
    position: str
    reason: str

    target_price: float
    low_offer: float
    high_offer: float

    potential_savings: float


def assess_negotiation_position(
    quoted_price: float,
    fair_value: float,
    inventory_risk: str
):

    overpricing = (
        (quoted_price - fair_value)
        / fair_value
    ) * 100

    if (
        overpricing > 10
        or inventory_risk in [
            "HIGH",
            "SEVERE"
        ]
    ):

        position = "STRONG"

        reason = (
            "Property is priced above estimated fair value "
            "and inventory levels are elevated, creating "
            "favorable negotiation leverage for buyers."
        )

    elif overpricing > 5:

        position = "FAIR"

        reason = (
            "Property shows moderate pricing pressure. "
            "Negotiation opportunities may exist but "
            "buyer leverage appears balanced."
        )

    else:

        position = "WEAK"

        reason = (
            "Property appears reasonably priced relative "
            "to estimated fair value, limiting negotiation leverage."
        )

    target_price = fair_value

    low_offer = fair_value * 0.95
    high_offer = fair_value * 1.02

    potential_savings = max(
        0,
        quoted_price - target_price
    )

    return NegotiationIntelligence(
        position=position,
        reason=reason,

        target_price=target_price,
        low_offer=low_offer,
        high_offer=high_offer,

        potential_savings=potential_savings
    )