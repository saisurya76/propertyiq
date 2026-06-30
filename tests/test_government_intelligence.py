from backend.government_intelligence import (
    assess_government_intelligence
)


def test_government_intelligence():

    result = assess_government_intelligence(
        country="India",
        state_province="Telangana",
        city="Hyderabad",
        property_type="Apartment",
        unit_area=1200
    )

    assert (
        result.government_rate_per_unit > 0
    )

    assert (
        result.government_property_value > 0
    )

    assert (
        result.reference_name != ""
    )

    assert (
        result.confidence != ""
    )

    assert (
        result.disclaimer != ""
    )