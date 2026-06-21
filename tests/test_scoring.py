from backend.scoring import (
    valuation_score,
    inventory_score
)


def test_valuation_score():

    score = valuation_score(
        overpricing_percent=10
    )

    assert score == 90


def test_valuation_score_zero():

    score = valuation_score(
        overpricing_percent=0
    )

    assert score == 100


def test_inventory_low():

    score = inventory_score(
        "LOW"
    )

    assert score == 100


def test_inventory_high():

    score = inventory_score(
        "HIGH"
    )

    assert score == 60