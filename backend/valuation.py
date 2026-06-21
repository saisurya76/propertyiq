from dataclasses import dataclass


@dataclass
class ValuationResult:
    quoted_price: float
    unit_area: float
    monthly_rent: float

    price_per_unit: float
    annual_rent: float
    rental_yield: float

    fair_value_low: float
    fair_value_high: float

    overpricing_percent: float


def calculate_valuation(
    quoted_price: float,
    unit_area: float,
    monthly_rent: float
) -> ValuationResult:

    price_per_unit = quoted_price / unit_area

    annual_rent = monthly_rent * 12

    rental_yield = (
        annual_rent / quoted_price
    ) * 100

    fair_value_low = quoted_price * 0.90

    fair_value_high = quoted_price * 1.10

    overpricing_percent = (
        (quoted_price - fair_value_high)
        / fair_value_high
    ) * 100

    if overpricing_percent < 0:
        overpricing_percent = 0

    return ValuationResult(
        quoted_price=quoted_price,
        unit_area=unit_area,
        monthly_rent=monthly_rent,
        price_per_unit=round(price_per_unit, 2),
        annual_rent=round(annual_rent, 2),
        rental_yield=round(rental_yield, 2),
        fair_value_low=round(fair_value_low, 2),
        fair_value_high=round(fair_value_high, 2),
        overpricing_percent=round(overpricing_percent, 2)
    )