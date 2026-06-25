from dataclasses import dataclass


@dataclass
class BuyerAdvantage:
    score: float
    rating: str
    reason: str


def assess_buyer_advantage(
    overpricing_percent: float,
    inventory_risk: str,
    negotiation_position: str,
    buyer_protection_score: float
):

    score = 0

    # Pricing Advantage

    if overpricing_percent >= 15:
        score += 40

    elif overpricing_percent >= 10:
        score += 30

    elif overpricing_percent >= 5:
        score += 20

    else:
        score += 10

    # Inventory Advantage

    if inventory_risk == "SEVERE":
        score += 30

    elif inventory_risk == "HIGH":
        score += 20

    elif inventory_risk == "MEDIUM":
        score += 10

    # Negotiation Advantage

    if negotiation_position == "STRONG":
        score += 20

    elif negotiation_position == "FAIR":
        score += 10

    # Buyer Protection Bonus

    if buyer_protection_score >= 80:
        score += 10

    elif buyer_protection_score >= 70:
        score += 5

    score = min(score, 100)

    if score >= 90:

        rating = "EXCEPTIONAL BUYER OPPORTUNITY"

        reason = (
            "Pricing, inventory conditions, and negotiation "
            "leverage strongly favor the buyer."
        )

    elif score >= 75:

        rating = "STRONG BUYER ADVANTAGE"

        reason = (
            "Current market conditions provide meaningful "
            "buyer leverage and negotiation opportunities."
        )

    elif score >= 60:

        rating = "MODERATE BUYER ADVANTAGE"

        reason = (
            "Some buyer leverage exists, though market "
            "conditions remain relatively balanced."
        )

    elif score >= 40:

        rating = "BALANCED MARKET"

        reason = (
            "Neither buyers nor sellers currently possess "
            "significant negotiating advantage."
        )

    elif score >= 20:

        rating = "SELLER ADVANTAGE"

        reason = (
            "Market conditions generally favor the seller, "
            "limiting buyer leverage."
        )

    else:

        rating = "STRONG SELLER ADVANTAGE"

        reason = (
            "Strong seller demand and limited negotiation "
            "opportunities favor the seller."
        )

    return BuyerAdvantage(
        score=score,
        rating=rating,
        reason=reason
    )