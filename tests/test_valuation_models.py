from backend.valuation_models import (
    comparable_sales_value
)


def test_comparable_sales_value():

    value = comparable_sales_value(
        unit_area=1800,
        comparable_price_per_unit=[
            9500,
            10200,
            9800
        ]
    )

    assert value == 17700000.0

from backend.valuation_models import (
    rental_yield_value
)

def test_rental_yield_value():

    value = rental_yield_value(
        monthly_rent=45000,
        target_yield_percent=4
    )

    assert value == 13500000.0


from backend.valuation_models import (
    replacement_cost_value
)


def test_replacement_cost_value():

    value = replacement_cost_value(
        land_share_cost=5000000,
        construction_cost=7000000,
        approval_cost=500000,
        developer_margin_percent=20
    )

    assert value == 15000000.0

from backend.valuation_models import (
    weighted_fair_value
)


def test_weighted_fair_value():

    value = weighted_fair_value(
        comparable_value=17700000,
        rental_value=13500000,
        replacement_value=15000000
    )

    assert value == 15840000.0