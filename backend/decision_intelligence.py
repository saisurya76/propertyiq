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

    elif developer_rating == "AVERAGE":
        property_quality = "AVERAGE PROJECT"

    elif developer_rating == "WEAK":
        property_quality = "HIGH RISK PROJECT"

    else:
        property_quality = "PROJECT QUALITY NOT ASSESSED"

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

    elif developer_rating == "AVERAGE":

        parts.append(
            "The developer demonstrates mixed historical performance and warrants additional due diligence."
        )

    elif developer_rating == "WEAK":

        parts.append(
            "The developer profile introduces meaningful execution risk and warrants careful due diligence."
        )

    else:

        parts.append(
            "Developer assessment could not be completed because developer performance information was not provided."
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

    elif inventory_risk == "HIGH":

        parts.append(
            "Elevated inventory levels increase buyer negotiating leverage."
        )

    elif inventory_risk == "SEVERE":

        parts.append(
            "High unsold inventory creates meaningful buyer negotiating leverage."
        )

    else:

        parts.append(
            "Inventory assessment could not be completed because project inventory data was not provided."
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

    if property_quality == "PROJECT QUALITY NOT ASSESSED":

        summary = (
            "Overall, PropertyIQ could not assess project quality because sufficient developer information was not provided. "
        )

    else:

        summary = (
            f"Overall, PropertyIQ considers this to be a {property_quality.lower()}. "
        )

    if overpricing_percent <= 5:

        pricing_summary = (
            "The current asking price is broadly aligned with "
            "PropertyIQ's estimated fair value. "
        )

    else:

        pricing_summary = (
            "However, the current asking price is above "
            "PropertyIQ's estimated fair value. "
        )

    summary += (
        pricing_summary +
        advice
    )

    parts.append(summary)

    narrative = " ".join(parts)

    return DecisionResult(
        property_quality=property_quality,
        deal_quality=deal_quality,
        category=category,
        action=recommendation,
        narrative=narrative
    )