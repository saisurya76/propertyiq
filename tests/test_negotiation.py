from backend.negotiation import (
    negotiation_guidance
)


def test_negotiation_guidance():

    result = negotiation_guidance(
        quoted_price=18000000,
        fair_value=15840000
    )

    assert "2,160,000" in result