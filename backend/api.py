from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from typing import Optional
from pydantic import BaseModel

import os
import uuid

from dodopayments import DodoPayments

from backend.payment_store import (
    initialize_payment_store,
    create_order,
    attach_checkout_session,
)

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

from backend.recommendation import (
    get_recommendation_reasons
)

from backend.renderers.pdf_renderer import (
    generate_pdf
)

app = FastAPI()

initialize_payment_store()

DODO_ENVIRONMENT = os.getenv("DODO_PAYMENTS_ENVIRONMENT", "test_mode")
DODO_PRODUCT_ID = os.getenv("DODO_REPORT_PRODUCT_ID", "")
FRONTEND_URL = os.getenv("PROPERTYIQ_FRONTEND_URL", "https://app.propertyiqweb.com")
DODO_API_KEY = os.getenv("DODO_PAYMENTS_API_KEY", "")


def get_dodo_client():
    if not DODO_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Dodo Payments is not configured. Set DODO_PAYMENTS_API_KEY."
        )
    if not DODO_PRODUCT_ID:
        raise HTTPException(
            status_code=503,
            detail="Dodo Payments is not configured. Set DODO_REPORT_PRODUCT_ID."
        )

    return DodoPayments(
        bearer_token=DODO_API_KEY,
        environment=DODO_ENVIRONMENT,
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PropertyRequest(BaseModel):
    country: str
    stateProvince: str
    city: str
    location: str
    propertyType: str

    propertyName: str
    developerName: str

    quotedPrice: float
    governmentGuidance: float
    marketAverage: float
    unitArea: float

    monthlyRent: float = 0

    totalUnits: Optional[int] = None
    unsoldUnits: Optional[int] = None

    projectsCompleted: Optional[int] = None
    projectsDelayed: Optional[int] = None

    yearsInBusiness: Optional[int] = None
    regulatoryViolations: Optional[int] = None

    areaUnit: str = "sqft"


class ReportCheckoutRequest(PropertyRequest):
    termsAccepted: bool
    termsVersion: str = "PropertyIQ Report Terms v1.0"


def build_property_input(data: PropertyRequest):

    return PropertyInput(
        country=data.country,
        state_province=data.stateProvince,
        city=data.city,
        locality=data.location,

        property_type=data.propertyType,

        property_name=data.propertyName,
        developer_name=data.developerName,

        quoted_price=data.quotedPrice,
        currency="INR",

        government_guidance=data.governmentGuidance,
        market_average=data.marketAverage,

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


def build_assessment(data: PropertyRequest):

    property_input = build_property_input(data)

    return run_assessment(property_input)

@app.post("/assess")
def assess(data: PropertyRequest):

    assessment = build_assessment(data)

    recommendation_reasons = (
        get_recommendation_reasons(
            overpricing_percent=
                assessment.overpricing_percent,

            inventory_risk=
                assessment.inventory_risk,

            developer_rating=
                assessment.developer_rating,

            buyer_protection_score=
                assessment.buyer_protection_score
        )
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

        "quotedPricePerSqft":
            round(
                assessment.quoted_price_per_sqft,
                2
            ),

        "fairValuePerSqft":
            round(
                assessment.fair_value_per_sqft,
                2
            ),

        "governmentRatePerUnit":
            assessment.government_intelligence.government_rate_per_unit,    

        "governmentPropertyValue":
            assessment.government_intelligence.government_property_value,

        "governmentReference":
            assessment.government_intelligence.reference_name,

        "governmentConfidence":
            assessment.government_intelligence.confidence,

        "governmentBuyerObservation":
            assessment.government_intelligence.buyer_observation,    

        "fraudIntelligence": {

            "status":
                assessment.fraud_intelligence.status.status,

            "reportId":
                assessment.fraud_intelligence.status.report_id,

            "generatedAt":
                assessment.fraud_intelligence.status.generated_at,

            "evidenceLastSynced":
                assessment.fraud_intelligence.status.evidence_last_synced,

            #
            # CITY
            #

            "city": [

                {
                    "id":
                        item.fraud_type.id,

                    "displayName":
                        item.fraud_type.display_name,

                    "description":
                        item.fraud_type.description,

                    "riskLevel":
                        item.risk_level,

                    "color":
                        item.color,

                    "evidenceCount":
                        item.evidence_count,

                    "applicable":
                        item.applicable
                }

                for item in
                assessment.fraud_intelligence.city
            ],

            "cityHeatmap":
                assessment.fraud_intelligence.city_heatmap,

            #
            # COUNTRY
            #

            "country": [

                {
                    "id":
                        item.fraud_type.id,

                    "displayName":
                        item.fraud_type.display_name,

                    "description":
                        item.fraud_type.description,

                    "riskLevel":
                        item.risk_level,

                    "color":
                        item.color,

                    "evidenceCount":
                        item.evidence_count,

                    "applicable":
                        item.applicable
                }

                for item in
                assessment.fraud_intelligence.country
            ],

            "countryHeatmap":
                assessment.fraud_intelligence.country_heatmap,

            #
            # GLOBAL
            #

            "globalTaxonomy": [

                {
                    "id":
                        item.fraud_type.id,

                    "displayName":
                        item.fraud_type.display_name,

                    "description":
                        item.fraud_type.description,

                    "riskLevel":
                        item.risk_level,

                    "color":
                        item.color,

                    "evidenceCount":
                        item.evidence_count,

                    "applicable":
                        item.applicable
                }

                for item in
                assessment.fraud_intelligence.global_taxonomy
            ],

            "globalHeatmap":
                assessment.fraud_intelligence.global_heatmap,

            #
            # GLOBAL MATRIX
            #

            "globalMatrix": (

                None

                if assessment.fraud_intelligence.global_matrix is None

                else {

                    "countries":
                        assessment.fraud_intelligence
                        .global_matrix
                        .countries,

                    "fraudTypes": [

                        {
                            "id":
                                fraud.id,

                            "displayName":
                                fraud.display_name,

                            "description":
                                fraud.description
                        }

                        for fraud in
                        assessment.fraud_intelligence
                        .global_matrix
                        .fraud_types
                    ],

                    "cells": [

                        {
                            "country":
                                cell.country,

                            "fraudTypeId":
                                cell.fraud_type_id,

                            "riskLevel":
                                cell.risk_level,

                            "color":
                                cell.color
                        }

                        for cell in
                        assessment.fraud_intelligence
                        .global_matrix
                        .cells
                    ]
                }

            ),

            #
            # Evidence
            #

            "evidence": [

                {
                    "evidenceId":
                        evidence.evidence_id,

                    "fraudTypeId":
                        evidence.fraud_type_id,

                    "country":
                        evidence.country,

                    "state":
                        evidence.state,

                    "city":
                        evidence.city,

                    "locality":
                        evidence.locality,

                    "sourceType":
                        evidence.source_type,

                    "sourceName":
                        evidence.source_name,

                    "publishedDate":
                        evidence.published_date,

                    "retrievedDate":
                        evidence.retrieved_date,

                    "confidence":
                        evidence.confidence,

                    "citation":
                        evidence.citation,

                    "url":
                        evidence.url,

                    "summary":
                        evidence.summary
                }

                for evidence in
                assessment.fraud_intelligence.evidence
            ],

            "citations":
                assessment.fraud_intelligence.citations
        },    

        "inventoryRisk":
            assessment.inventory_risk,

        "developerRating":
            assessment.developer_rating,

        "recommendation":
            assessment.recommendation,

        "dealQuality":
            assessment.deal_quality,

        "dealQualityReason":
            assessment.deal_quality_reason,

        "negotiationPosition":
            assessment.negotiation_position,

        "negotiationReason":
            assessment.negotiation_reason,

        "targetPrice":
            round(
                assessment.target_price,
                0
            ),

        "lowOffer":
            round(
                assessment.low_offer,
                0
            ),

        "highOffer":
            round(
                assessment.high_offer,
                0
            ),

        "potentialSavings":
            round(
                assessment.potential_savings,
                0
            ),    

        "buyerAdvantageScore":
            assessment.buyer_advantage_score,

        "buyerAdvantageRating":
            assessment.buyer_advantage_rating,

        "buyerAdvantageReason":
            assessment.buyer_advantage_reason,

        "recommendationConfidenceScore":
            assessment.recommendation_confidence_score,

        "recommendationConfidenceRating":
            assessment.recommendation_confidence_rating,

        "recommendationConfidenceReason":
            assessment.recommendation_confidence_reason,    
            
        "recommendationReasons":
            recommendation_reasons,

        "valuationScore":
            assessment.valuation_score,

        "inventoryScore":
            assessment.inventory_score,

        "developerScore":
            assessment.developer_score,
        
        "marketAveragePricePerSqft":
            assessment.market_average_price_per_sqft,

        "normalizedArea":
            assessment.normalized_area,

        "comparables": [
            {
                "projectName":
                    c.project_name,

                "developer":
                    c.developer,

                "pricePerSqft":
                    c.price_per_sqft
            }
            for c in assessment.comparables
        ],

        "findings": {
            "pricing":
                assessment.findings.pricing_finding,

            "inventory":
                assessment.findings.inventory_finding,

            "developer":
                assessment.findings.developer_finding,

            "overall":
                assessment.findings.overall_finding
        },

        "decision": {

            "propertyQuality":
                assessment.decision.property_quality,

            "dealQuality":
                assessment.decision.deal_quality,

            "category":
                assessment.decision.category,

            "action":
                assessment.decision.action,

            "narrative":
                assessment.decision.narrative
        },
    }


@app.post("/create-checkout")
def create_checkout(data: ReportCheckoutRequest):
    if data.country.strip().lower() != "india":
        raise HTTPException(
            status_code=400,
            detail="Paid PropertyIQ reports are currently available only in India."
        )

    if not data.termsAccepted:
        raise HTTPException(
            status_code=400,
            detail="PropertyIQ Report Terms & Conditions must be accepted before purchase."
        )

    order_id = f"PIQ-{uuid.uuid4().hex}"
    payload = data.model_dump(exclude={"termsAccepted", "termsVersion"})

    create_order(
        order_id=order_id,
        property_payload=payload,
        terms_version=data.termsVersion,
    )

    client = get_dodo_client()

    try:
        session = client.checkout_sessions.create(
            product_cart=[
                {
                    "product_id": DODO_PRODUCT_ID,
                    "quantity": 1,
                }
            ],
            metadata={
                "order_id": order_id,
                "terms_version": data.termsVersion,
                "product": "propertyiq_report",
                "country": "IN",
                "currency": "INR",
            },
            return_url=f"{FRONTEND_URL.rstrip('/')}/?payment=return&order_id={order_id}",
            cancel_url=f"{FRONTEND_URL.rstrip('/')}/?payment=cancelled&order_id={order_id}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail="Unable to create Dodo Payments checkout session."
        ) from exc
    finally:
        client.close()

    attach_checkout_session(order_id, session.session_id)

    return {
        "orderId": order_id,
        "checkoutUrl": session.checkout_url,
        "checkoutSessionId": session.session_id,
        "currency": "INR",
        "country": "IN",
        "termsVersion": data.termsVersion,
    }


@app.post("/generate-report")
def generate_report(data: PropertyRequest):
    
    assessment = build_assessment(data)

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

@app.get("/")
def health():
    return {
        "service": "PropertyIQ API",
        "version": "1.0.0-beta",
        "status": "healthy"
    }    