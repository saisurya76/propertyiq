from backend.recommendation import (
    calculate_overpricing_percent,
    get_recommendation
)


def test_buy():

    recommendation = get_recommendation(4)

    assert recommendation == "BUY"


def test_buy_after_negotiation():

    recommendation = get_recommendation(10)

    assert recommendation == "BUY AFTER NEGOTIATION"


def test_wait():

    recommendation = get_recommendation(20)

    assert recommendation == "WAIT"


def test_avoid():

    recommendation = get_recommendation(30)

    assert recommendation == "AVOID"


def test_overpricing():

    result = calculate_overpricing_percent(
        quoted_price=18000000,
        fair_value=15840000
    )

    assert round(result, 2) == 13.64