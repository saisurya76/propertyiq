def valuation_score(
    overpricing_percent: float
) -> float:

    if overpricing_percent <= 0:
        return 100

    if overpricing_percent >= 50:
        return 50

    return round(
        100 - overpricing_percent,
        2
    )


def inventory_score(
    risk_level: str
) -> float:

    mapping = {
        "LOW": 100,
        "MODERATE": 80,
        "HIGH": 60,
        "SEVERE": 40
    }

    return mapping.get(
        risk_level.upper(),
        40
    )