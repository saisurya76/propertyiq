from backend.assessment_pipeline import (
    PropertyInput,
    run_assessment
)

from backend.risk_engine import (
    identify_risks
)

from backend.negotiation import (
    negotiation_guidance
)

from backend.renderers.html_renderer import (
    render_html
)


def main():

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

    output_file = (
        "outputs/reports/"
        "PropertyIQ_Buyer_Protection_Report.html"
    )

    with open(
        output_file,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(html)

    print(
        f"Report generated: {output_file}"
    )


if __name__ == "__main__":
    main()