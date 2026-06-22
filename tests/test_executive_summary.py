from backend.executive_summary import (
    generate_executive_summary
)


def test_executive_summary():

    summary = generate_executive_summary(
        property_name="Aparna Sarovar Zenith",
        quoted_price=18000000,
        fair_value=15840000,
        buyer_protection_score=79.4,
        buyer_protection_rating="FAIR",
        recommendation="BUY AFTER NEGOTIATION",
        inventory_risk="HIGH",
        developer_rating="EXCELLENT"
    )

    assert "Aparna Sarovar Zenith" in summary

    assert "BUY AFTER NEGOTIATION" in summary