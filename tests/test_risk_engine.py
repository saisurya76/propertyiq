from backend.risk_engine import (
    identify_risks
)


def test_risks():

    risks = identify_risks(
        overpricing_percent=20,
        inventory_risk="HIGH",
        developer_rating="AVERAGE"
    )

    assert len(risks) == 3