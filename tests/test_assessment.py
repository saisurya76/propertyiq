from backend.assessment import (
    create_assessment
)

from backend.findings import (
    generate_findings
)


def test_create_assessment():

    findings = generate_findings(
        overpricing_percent=13.64,
        inventory_risk="HIGH",
        developer_rating="EXCELLENT",
        recommendation="BUY AFTER NEGOTIATION"
    )

    assessment = create_assessment(
        property_name="Aparna Sarovar Zenith",
        developer_name="Aparna",
        quoted_price=18000000,
        fair_value=15840000,
        overpricing_percent=13.64,
        inventory_risk="HIGH",
        developer_rating="EXCELLENT",
        buyer_protection_score=79.4,
        buyer_protection_rating="FAIR",
        recommendation="BUY AFTER NEGOTIATION",
        findings=findings
    )

    assert assessment.property_name == "Aparna Sarovar Zenith"

    assert assessment.recommendation == "BUY AFTER NEGOTIATION"