from dataclasses import dataclass

from backend.findings import FindingsResult


@dataclass
class PropertyAssessment:
    property_name: str
    developer_name: str

    quoted_price: float
    fair_value: float

    unit_area: float
    area_unit: str

    overpricing_percent: float

    inventory_risk: str

    developer_rating: str

    valuation_score: float
    inventory_score: float
    developer_score: float

    buyer_protection_score: float
    buyer_protection_rating: str

    recommendation: str

    findings: FindingsResult


def create_assessment(
    property_name: str,
    developer_name: str,

    quoted_price: float,
    fair_value: float,

    unit_area: float,
    area_unit: str,

    overpricing_percent: float,

    inventory_risk: str,

    developer_rating: str,

    valuation_score: float,
    inventory_score: float,
    developer_score: float,

    buyer_protection_score: float,
    buyer_protection_rating: str,

    recommendation: str,

    findings: FindingsResult
) -> PropertyAssessment:

    return PropertyAssessment(
        property_name=property_name,
        developer_name=developer_name,

        quoted_price=quoted_price,
        fair_value=fair_value,

        unit_area=unit_area,
        area_unit=area_unit,

        overpricing_percent=overpricing_percent,

        inventory_risk=inventory_risk,

        developer_rating=developer_rating,

        valuation_score=valuation_score,
        inventory_score=inventory_score,
        developer_score=developer_score,

        buyer_protection_score=buyer_protection_score,
        buyer_protection_rating=buyer_protection_rating,

        recommendation=recommendation,

        findings=findings
    )