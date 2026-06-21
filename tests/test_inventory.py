from backend.inventory import (
    assess_inventory_risk
)


def test_low_inventory_risk():

    result = assess_inventory_risk(
        total_units=1000,
        unsold_units=50
    )

    assert result.risk_level == "LOW"


def test_moderate_inventory_risk():

    result = assess_inventory_risk(
        total_units=1000,
        unsold_units=150
    )

    assert result.risk_level == "MODERATE"


def test_high_inventory_risk():

    result = assess_inventory_risk(
        total_units=1000,
        unsold_units=300
    )

    assert result.risk_level == "HIGH"


def test_severe_inventory_risk():

    result = assess_inventory_risk(
        total_units=1000,
        unsold_units=500
    )

    assert result.risk_level == "SEVERE"