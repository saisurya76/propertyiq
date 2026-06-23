from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.assessment_pipeline import (
    PropertyInput,
    run_assessment
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

    monthlyRent: float = 0


@app.post("/assess")
def assess(data: PropertyRequest):

    property_input = PropertyInput(
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
        area_unit="sqft",

        monthly_rent=data.monthlyRent,

        total_units=100,
        unsold_units=20,

        projects_completed=10,
        projects_delayed=1,
        years_in_business=15,
        rera_violations=0
    )

    assessment = run_assessment(
        property_input
    )

    return {
    "score": round(
        assessment.buyer_protection_score,
        2
    ),
    "rating": assessment.buyer_protection_rating,

    "fairValue": round(
        assessment.fair_value,
        2
    ),

    "inventoryRisk":
        assessment.inventory_risk,

    "developerRating":
        assessment.developer_rating,

    "recommendation":
        assessment.recommendation
}