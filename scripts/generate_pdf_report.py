from backend.assessment_pipeline import (
    PropertyInput,
    run_assessment
)

from backend.executive_summary import (
    generate_executive_summary
)

from backend.risk_engine import (
    identify_risks
)

from backend.negotiation import (
    negotiation_guidance
)

from backend.renderers.pdf_renderer import (
    generate_pdf
)


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

summary = generate_executive_summary(
    property_name=assessment.property_name,
    quoted_price=assessment.quoted_price,
    fair_value=assessment.fair_value,
    buyer_protection_score=assessment.buyer_protection_score,
    buyer_protection_rating=assessment.buyer_protection_rating,
    recommendation=assessment.recommendation,
    inventory_risk=assessment.inventory_risk,
    developer_rating=assessment.developer_rating
)

risks = identify_risks(
    assessment.overpricing_percent,
    assessment.inventory_risk,
    assessment.developer_rating
)

guidance = negotiation_guidance(
    assessment.quoted_price,
    assessment.fair_value
)

generate_pdf(
    assessment=assessment,
    risks=risks,
    negotiation_text=guidance,
    executive_summary=summary,
    output_file="outputs/pdfs/aparna_assessment.pdf"
)

print(
    "PDF generated: outputs/pdfs/aparna_assessment.pdf"
)