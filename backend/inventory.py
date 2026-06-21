from dataclasses import dataclass


@dataclass
class InventoryResult:
    total_units: int
    unsold_units: int

    unsold_percent: float

    risk_level: str


def assess_inventory_risk(
    total_units: int,
    unsold_units: int
) -> InventoryResult:

    if total_units <= 0:
        raise ValueError(
            "Total units must be greater than zero."
        )

    unsold_percent = (
        unsold_units / total_units
    ) * 100

    if unsold_percent < 10:
        risk_level = "LOW"

    elif unsold_percent < 20:
        risk_level = "MODERATE"

    elif unsold_percent < 35:
        risk_level = "HIGH"

    else:
        risk_level = "SEVERE"

    return InventoryResult(
        total_units=total_units,
        unsold_units=unsold_units,
        unsold_percent=round(
            unsold_percent,
            2
        ),
        risk_level=risk_level
    )