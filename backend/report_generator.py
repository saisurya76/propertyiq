from dataclasses import dataclass


@dataclass
class PropertyReport:
    property_name: str
    developer_name: str

    quoted_price: float

    fair_value: float

    overpricing_percent: float

    inventory_risk: str

    developer_rating: str

    buyer_protection_score: float

    buyer_protection_rating: str

    recommendation: str


def generate_report(
    property_name: str,
    developer_name: str,
    quoted_price: float,
    fair_value: float,
    overpricing_percent: float,
    inventory_risk: str,
    developer_rating: str,
    buyer_protection_score: float,
    buyer_protection_rating: str,
    recommendation: str
) -> PropertyReport:

    return PropertyReport(
        property_name=property_name,
        developer_name=developer_name,
        quoted_price=quoted_price,
        fair_value=fair_value,
        overpricing_percent=overpricing_percent,
        inventory_risk=inventory_risk,
        developer_rating=developer_rating,
        buyer_protection_score=buyer_protection_score,
        buyer_protection_rating=buyer_protection_rating,
        recommendation=recommendation
    )