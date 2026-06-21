def negotiation_guidance(
    quoted_price: float,
    fair_value: float
):

    difference = quoted_price - fair_value

    if difference <= 0:
        return (
            "Quoted price is already at or below estimated fair value."
        )

    return (
        f"Consider negotiating approximately "
        f"{round(difference, 0):,.0f} "
        f"from the quoted price."
    )