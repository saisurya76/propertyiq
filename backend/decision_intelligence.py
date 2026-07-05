from dataclasses import dataclass


@dataclass
class DecisionResult:
    property_quality: str
    deal_quality: str

    category: str
    action: str

    narrative: str


def generate_decision(
    recommendation: str,
    buyer_protection_score: float,
    overpricing_percent: float,
    developer_rating: str,
    inventory_risk: str,
    negotiation_position: str
) -> DecisionResult:

    # -----------------------------------
    # Decision Category
    # -----------------------------------

    if recommendation == "BUY":
        category = "GOOD DEAL"

    elif recommendation == "BUY AFTER NEGOTIATION":
        category = "NEGOTIATE AGGRESSIVELY"

    elif recommendation == "PROCEED WITH EXTREME CAUTION":
        category = "HIGH RISK PURCHASE"

    elif recommendation == "WAIT":
        category = "WAIT FOR BETTER OPPORTUNITY"

    else:
        category = "WALK AWAY"

    # -----------------------------------
    # Property Quality
    # -----------------------------------

    if developer_rating == "EXCELLENT":

        property_quality = "GOOD PROJECT"

    elif developer_rating == "GOOD":

        property_quality = "REASONABLE PROJECT"

    else:

        property_quality = "HIGH RISK PROJECT"

    # -----------------------------------
    # Deal Quality
    # -----------------------------------

    if overpricing_percent <= 5:

        deal_quality = "GOOD DEAL"

    elif overpricing_percent <= 15:

        deal_quality = "FAIR DEAL"

    elif overpricing_percent <= 30:

        deal_quality = "POOR VALUE"

    else:

        deal_quality = "NOT ATTRACTIVE AT CURRENT PRICE"

    # -----------------------------------
    # Narrative
    # -----------------------------------

    parts = []

    # Project Fundamentals

    if developer_rating == "EXCELLENT":

        parts.append(
            "The project is backed by an excellent developer with a strong delivery track record, reducing execution-related risk."
        )

    elif developer_rating == "GOOD":

        parts.append(
            "The developer has a generally positive delivery history, though some execution risks remain."
        )

    else:

        parts.append(
            "The developer profile introduces meaningful execution risk and warrants careful due diligence."
        )

    # Inventory

    if inventory_risk == "LOW":

        parts.append(
            "Current inventory levels indicate healthy market demand."
        )

    elif inventory_risk == "MODERATE":

        parts.append(
            "Inventory levels remain balanced and provide some flexibility during negotiations."
        )

    else:

        parts.append(
            "Elevated inventory levels increase buyer negotiating leverage."
        )

    # Pricing

    if overpricing_percent <= 5:

        parts.append(
            "The asking price is broadly aligned with PropertyIQ's estimated fair value."
        )

    elif overpricing_percent <= 15:

        parts.append(
            f"The property is priced approximately {overpricing_percent:.2f}% above PropertyIQ's estimated fair value, suggesting scope for negotiation."
        )

    elif overpricing_percent <= 30:

        parts.append(
            f"The current asking price is materially higher ({overpricing_percent:.2f}% above fair value), reducing buyer value at the quoted price."
        )

    else:

        parts.append(
            f"The asking price is significantly above PropertyIQ's estimated fair value ({overpricing_percent:.2f}% above fair value), requiring careful justification before proceeding."
        )

    
    # -----------------------------------
    # Final Advice
    # -----------------------------------

    if recommendation == "BUY":

        advice = (
            "The current asking price appears reasonable for proceeding."
        )

    elif recommendation == "BUY AFTER NEGOTIATION":

        advice = (
            "PropertyIQ recommends negotiating towards the estimated fair value before proceeding."
        )

    elif recommendation == "PROCEED WITH EXTREME CAUTION":

        advice = (
            "Proceed only after comprehensive due diligence and substantial price negotiation."
        )

    elif recommendation == "WAIT":

        advice = (
            "Waiting for improved pricing or changing market conditions may produce a better buying opportunity."
        )

    else:

        advice = (
            "PropertyIQ does not recommend proceeding with this purchase at the current asking price."
        )

    parts.append(
        f"Overall, PropertyIQ considers this to be a "
        f"{property_quality.lower()}. "
        f"However, the current asking price is above "
        f"PropertyIQ's estimated fair value. "
        f"{advice}"
    )

    narrative = " ".join(parts)

    return DecisionResult(
        property_quality=property_quality,
        deal_quality=deal_quality,
        category=category,
        action=recommendation,
        narrative=narrative
    )