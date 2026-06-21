from backend.valuation import calculate_valuation


def test_basic_valuation():

    result = calculate_valuation(
        quoted_price=18000000,
        unit_area=1800,
        monthly_rent=45000
    )

    assert result.price_per_unit == 10000.0