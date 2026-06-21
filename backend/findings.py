from dataclasses import dataclass


@dataclass
class FindingsResult:
    pricing_finding: str
    inventory_finding: str
    developer_finding: str
    overall_finding: str


def generate_findings(
    overpricing_percent: float,
    inventory_risk: str,
    developer_rating: str,
    recommendation: str
) -> FindingsResult:

    # Pricing

    if overpricing_percent <= 5:
        pricing = (
            "The quoted price is broadly aligned "
            "with PropertyIQ's estimated fair value."
        )

    elif overpricing_percent <= 15:
        pricing = (
            f"The quoted price is approximately "
            f"{overpricing_percent}% above "
            "PropertyIQ's estimated fair value."
        )

    else:
        pricing = (
            f"The quoted price appears materially "
            f"elevated at approximately "
            f"{overpricing_percent}% above "
            "estimated fair value."
        )

    # Inventory

    inventory_map = {
        "LOW":
            "Inventory levels appear healthy with limited supply risk.",

        "MODERATE":
            "Inventory levels indicate moderate supply risk.",

        "HIGH":
            "Inventory levels indicate elevated supply risk and may impact short-term appreciation.",

        "SEVERE":
            "Inventory levels indicate significant oversupply risk."
    }

    inventory = inventory_map.get(
        inventory_risk.upper(),
        "Inventory information unavailable."
    )

    # Developer

    developer_map = {
        "EXCELLENT":
            "The developer demonstrates a strong delivery track record and favorable operating history.",

        "GOOD":
            "The developer demonstrates generally positive execution performance.",

        "AVERAGE":
            "The developer demonstrates mixed historical performance.",

        "WEAK":
            "The developer presents elevated execution risk."
    }

    developer = developer_map.get(
        developer_rating.upper(),
        "Developer information unavailable."
    )

    overall = (
        f"PropertyIQ recommendation: {recommendation}."
    )

    return FindingsResult(
        pricing_finding=pricing,
        inventory_finding=inventory,
        developer_finding=developer,
        overall_finding=overall
    )