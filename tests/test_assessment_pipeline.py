from backend.assessment_pipeline import (
    PropertyInput,
    run_assessment
)


def test_pipeline():

    data = PropertyInput(
        country="India",
        state_province="Telangana",
        city="Hyderabad",
        locality="Tellapur",

        property_type="Apartment",

        property_name="Aparna Sarovar Zenith",
        developer_name="Aparna",

        quoted_price=18000000,
        currency="INR",

        unit_area=1800,
        area_unit="sqft",

        monthly_rent=45000,

        total_units=1000,
        unsold_units=300,

        projects_completed=20,
        projects_delayed=1,
        years_in_business=20,
        rera_violations=0
    )

    assessment = run_assessment(data)

    assert assessment.property_name == "Aparna Sarovar Zenith"

    assert assessment.recommendation is not None