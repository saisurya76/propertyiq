def calculate_overpricing_percent(
    quoted_price: float,
    fair_value: float
) -> float:

    if fair_value <= 0:
        raise ValueError(
            "Fair value must be greater than zero."
        )

    return round(
        (
            (quoted_price - fair_value)
            / fair_value
        ) * 100,
        2
    )


def get_recommendation(
    overpricing_percent: float
) -> str:

    if overpricing_percent <= 5:
        return "BUY"

    if overpricing_percent <= 15:
        return "BUY AFTER NEGOTIATION"

    if overpricing_percent <= 25:
        return "WAIT"

    return "AVOID"