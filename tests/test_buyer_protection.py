from backend.buyer_protection import (
    calculate_buyer_protection_score
)


def test_buyer_protection_score():

    result = calculate_buyer_protection_score(
        valuation_score=86,
        inventory_score=60,
        developer_score=92
    )

    assert result.rating == "FAIR"

    assert round(result.score, 1) == 79.4