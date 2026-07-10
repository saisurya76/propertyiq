from backend.assessment_pipeline import (
    PropertyInput,
    run_assessment
)

from backend.renderers.html_renderer import (
    render_html
)

from backend.risk_engine import (
    identify_risks
)

from backend.negotiation import (
    negotiation_guidance
)


def test_html_renderer():

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

        government_guidance=6500,
        market_average=10125,

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

    risks = identify_risks(
        assessment.overpricing_percent,
        assessment.inventory_risk,
        assessment.developer_rating
    )

    guidance = negotiation_guidance(
        assessment.quoted_price,
        assessment.fair_value
    )

    html = render_html(
        assessment,
        risks,
        guidance
    )

    assert "<html>" in html
    assert "Buyer Protection Score" in html
    assert "Aparna Sarovar Zenith" in html