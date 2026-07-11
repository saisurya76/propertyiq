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

    if monthly_rent <= 0:
        return 0.0

    annual_rent = monthly_rent * 12

    fair_value = (
        annual_rent /
        (target_yield_percent / 100)
    )

    return round(
        fair_value,
        2
    )

def replacement_cost_value(
    land_share_cost: float,
    construction_cost: float,
    approval_cost: float,
    developer_margin_percent: float
) -> float:

    base_cost = (
        land_share_cost
        + construction_cost
        + approval_cost
    )

    developer_margin = (
        base_cost
        * developer_margin_percent
        / 100
    )

    fair_value = (
        base_cost
        + developer_margin
    )

    return round(
        fair_value,
        2
    )

def calculate_fair_value(
    comparable_value: float,
    rental_value: float = 0.0,
    replacement_value: float = 0.0
) -> float:

    values = []

    if comparable_value > 0:
        values.append(comparable_value)

    if rental_value > 0:
        values.append(rental_value)

    if replacement_value > 0:
        values.append(replacement_value)

    if not values:
        raise ValueError(
            "No valuation models available."
        )

    return round(
        sum(values) / len(values),
        2
    )