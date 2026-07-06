def negotiation_guidance(
    quoted_price: float,
    fair_value: float
):

    difference = quoted_price - fair_value

    if difference <= 0:

        return (
            "The quoted price is already at or below PropertyIQ's estimated fair value. There may be limited scope for further price negotiation."
        )

    return (
        f"Consider negotiating approximately "
        f"{round(difference, 0):,.0f} "
        f"from the quoted price."
    )