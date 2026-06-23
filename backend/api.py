from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from pydantic import BaseModel

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

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PropertyRequest(BaseModel):
    country: str
    city: str

    propertyName: str
    developerName: str

    quotedPrice: float

    unitArea: float
    areaUnit: str = "sqft"

    monthlyRent: float = 0

    totalUnits: int = 100
    unsoldUnits: int = 20

    projectsCompleted: int = 10
    projectsDelayed: int = 1

    yearsInBusiness: int = 15
    regulatoryViolations: int = 0


def build_property_input(data: PropertyRequest):

    return PropertyInput(
        country=data.country,
        state_province="Unknown",
        city=data.city,
        locality="Unknown",

        property_type="Apartment",

        property_name=data.propertyName,
        developer_name=data.developerName,

        quoted_price=data.quotedPrice,
        currency="INR",

        unit_area=data.unitArea,
        area_unit=data.areaUnit,

        monthly_rent=data.monthlyRent,

        total_units=data.totalUnits,
        unsold_units=data.unsoldUnits,

        projects_completed=data.projectsCompleted,
        projects_delayed=data.projectsDelayed,

        years_in_business=data.yearsInBusiness,
        rera_violations=data.regulatoryViolations
    )


@app.post("/assess")
def assess(data: PropertyRequest):

    property_input = build_property_input(data)

    assessment = run_assessment(
        property_input
    )

    return {
        "score": round(
            assessment.buyer_protection_score,
            2
        ),

        "rating":
            assessment.buyer_protection_rating,

        "fairValue":
            round(
                assessment.fair_value,
                2
            ),

        "inventoryRisk":
            assessment.inventory_risk,

        "developerRating":
            assessment.developer_rating,

        "recommendation":
            assessment.recommendation,

        "findings": {
            "pricing":
                assessment.findings.pricing_finding,

            "inventory":
                assessment.findings.inventory_finding,

            "developer":
                assessment.findings.developer_finding,

            "overall":
                assessment.findings.overall_finding
        }
    }


@app.post("/generate-report")
def generate_report(data: PropertyRequest):

    property_input = build_property_input(data)

    assessment = run_assessment(
        property_input
    )

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

    output_file = (
        "outputs/pdfs/propertyiq_report.pdf"
    )

    generate_pdf(
        assessment=assessment,
        risks=risks,
        negotiation_text=guidance,
        executive_summary=summary,
        output_file=output_file
    )

    return FileResponse(
        path=output_file,
        media_type="application/pdf",
        filename="PropertyIQ_Report.pdf"
    )