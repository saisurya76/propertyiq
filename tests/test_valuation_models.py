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