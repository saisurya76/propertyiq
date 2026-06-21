from statistics import mean


def comparable_sales_value(
    unit_area: float,
    comparable_price_per_unit: list[float]
) -> float:
    """
    Calculate fair value using comparable sales.

    Example:
        unit_area = 1800

        comparables =
        [9500, 10200, 9800]

    Returns:
        Fair Value
    """

    if not comparable_price_per_unit:
        raise ValueError(
            "At least one comparable price is required."
        )

    avg_price = mean(comparable_price_per_unit)

    return round(
        unit_area * avg_price,
        2
    )