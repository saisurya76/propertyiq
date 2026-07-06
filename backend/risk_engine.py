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

    if inventory_risk == "NOT_ASSESSED":

        risks.append(
            "Inventory risk could not be assessed because project inventory data was not provided."
        )

    elif inventory_risk in [
        "HIGH",
        "SEVERE"
    ]:

        risks.append(
            "Elevated inventory levels may impact appreciation and resale."
        )

    if developer_rating == "NOT_ASSESSED":

        risks.append(
            "Developer risk could not be assessed because developer information was not provided."
        )

    elif developer_rating in [
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