def to_sqft(
    area_value: float,
    area_unit: str
) -> float:

    unit = area_unit.strip().lower()

    conversion_factors = {
        "sqft": 1.0,
        "sq yard": 9.0,
        "sq meter": 10.7639,
        "acre": 43560.0,
        "hectare": 107639.0
    }

    factor = conversion_factors.get(unit)

    if factor is None:
        raise ValueError(
            f"Unsupported area unit: {area_unit}"
        )

    return round(
        area_value * factor,
        2
    )