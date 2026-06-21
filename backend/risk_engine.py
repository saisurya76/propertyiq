def identify_risks(
    overpricing_percent: float,
    inventory_risk: str,
    developer_rating: str
):

    risks = []

    if overpricing_percent > 15:
        risks.append(
            "Property appears materially overpriced."
        )

    if inventory_risk in [
        "HIGH",
        "SEVERE"
    ]:
        risks.append(
            "Elevated inventory levels may impact appreciation and resale."
        )

    if developer_rating in [
        "AVERAGE",
        "WEAK"
    ]:
        risks.append(
            "Developer execution history warrants additional diligence."
        )

    if not risks:
        risks.append(
            "No major risks identified based on available inputs."
        )

    return risks