from backend.report_generator import (
    generate_report
)


def test_report_generation():

    report = generate_report(
        property_name="Aparna Sarovar Zenith",
        developer_name="Aparna",
        quoted_price=18000000,
        fair_value=15840000,
        overpricing_percent=13.64,
        inventory_risk="HIGH",
        developer_rating="EXCELLENT",
        buyer_protection_score=79.4,
        buyer_protection_rating="FAIR",
        recommendation="BUY AFTER NEGOTIATION"
    )

    assert (
        report.property_name
        == "Aparna Sarovar Zenith"
    )

    assert (
        report.recommendation
        == "BUY AFTER NEGOTIATION"
    )