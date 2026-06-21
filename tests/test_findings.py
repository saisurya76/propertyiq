from backend.findings import (
    generate_findings
)


def test_generate_findings():

    result = generate_findings(
        overpricing_percent=13.64,
        inventory_risk="HIGH",
        developer_rating="EXCELLENT",
        recommendation="BUY AFTER NEGOTIATION"
    )

    assert (
        "13.64%"
        in result.pricing_finding
    )

    assert (
        result.overall_finding
        == "PropertyIQ recommendation: BUY AFTER NEGOTIATION."
    )