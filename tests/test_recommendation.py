from backend.recommendation import (
    calculate_overpricing_percent,
    get_recommendation
)


def test_buy():

    recommendation = get_recommendation(
        overpricing_percent=4,
        inventory_risk="LOW",
        developer_rating="EXCELLENT",
        buyer_protection_score=90
    )

    assert recommendation == "BUY"


def test_buy_after_negotiation():

    recommendation = get_recommendation(
        overpricing_percent=10,
        inventory_risk="MEDIUM",
        developer_rating="GOOD",
        buyer_protection_score=82
    )

    assert recommendation == "BUY AFTER NEGOTIATION"


def test_wait():

    recommendation = get_recommendation(
        overpricing_percent=20,
        inventory_risk="LOW",
        developer_rating="EXCELLENT",
        buyer_protection_score=90
    )

    assert recommendation == "WAIT"


def test_avoid():

    recommendation = get_recommendation(
        overpricing_percent=30,
        inventory_risk="SEVERE",
        developer_rating="WEAK",
        buyer_protection_score=50
    )

    assert recommendation == "AVOID"


def test_overpricing():

    result = calculate_overpricing_percent(
        quoted_price=18000000,
        fair_value=15840000
    )

    assert round(result, 2) == 13.64