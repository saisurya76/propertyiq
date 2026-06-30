from dataclasses import dataclass

from backend.government_data_provider import (
    get_government_rate
)

@dataclass
class GovernmentIntelligence:

    government_rate_per_unit: float

    government_property_value: float

    reference_name: str

    buyer_observation: str

    confidence: str

    disclaimer: str

def assess_government_intelligence(
    country: str,
    state_province: str,
    city: str,
    property_type: str,
    unit_area: float
) -> GovernmentIntelligence:

    government_rate = get_government_rate(
        country,
        state_province,
        city,
        property_type
    )

    government_value = (
        government_rate * unit_area
    )

    return GovernmentIntelligence(

        government_rate_per_unit=
            government_rate,

        government_property_value=
            government_value,

        reference_name=
            "Government Guideline Value",

        buyer_observation=
            "The quoted price should be compared against the government guidance value for registration purposes. Government guidance values are not market values.",

        confidence=
            "HIGH",

        disclaimer=
            "Government guidance values are primarily used for taxation and property registration and may differ from prevailing market prices."
    )    