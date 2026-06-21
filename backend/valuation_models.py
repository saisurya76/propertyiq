from statistics import mean


def comparable_sales_value(
    unit_area: float,
    comparable_price_per_unit: list[float]
) -> float:

    if not comparable_price_per_unit:
        raise ValueError(
            "At least one comparable price is required."
        )

    avg_price = mean(
        comparable_price_per_unit
    )

    return round(
        unit_area * avg_price,
        2
    )


def rental_yield_value(
    monthly_rent: float,
    target_yield_percent: float
) -> float:

    if target_yield_percent <= 0:
        raise ValueError(
            "Target yield must be greater than zero."
        )

    annual_rent = monthly_rent * 12

    fair_value = (
        annual_rent /
        (target_yield_percent / 100)
    )

    return round(
        fair_value,
        2
    )