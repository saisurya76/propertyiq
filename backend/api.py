from fastapi import FastAPI, HTTPException, Depends, Request
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

from backend.construction_store import (
    initialize_construction_store,
    save_design,
    get_design,
    count_designs_this_month,
)

from backend.construction_studio import (
    get_catalog,
    get_fx_rates,
    estimate_cost,
    check_vastu_basics,
    identify_construction_risks,
)

from backend.vastu_engine import (
    check_vastu_full,
)

from backend.construction_dxf import (
    generate_plot_dxf,
)

from backend.auth_store import (
    initialize_auth_store,
    create_otp,
    verify_otp,
    create_session,
)

from backend.auth import (
    send_otp_email,
    get_current_user_email,
)

from backend.config_store import (
    initialize_config_store,
    get_tier_config,
    set_tier_config,
    get_tier,
)

from backend.subscription_store import (
    initialize_subscription_store,
    upsert_subscription,
    get_subscription,
    set_status_by_dodo_id,
    get_active_tier,
    list_all_subscriptions,
)

from backend.insight_store import (
    initialize_insight_store,
    grant_insight_access,
    has_insight_access,
    list_all_grants,
)

from backend.similar_properties import (
    get_similar_properties,
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
initialize_construction_store()
initialize_auth_store()
initialize_config_store()
initialize_subscription_store()
initialize_insight_store()

DODO_ENVIRONMENT = os.getenv("DODO_PAYMENTS_ENVIRONMENT", "test_mode")
DODO_PRODUCT_ID = os.getenv("DODO_REPORT_PRODUCT_ID", "")
FRONTEND_URL = os.getenv("PROPERTYIQ_FRONTEND_URL", "https://app.propertyiqweb.com")
DODO_API_KEY = os.getenv("DODO_PAYMENTS_API_KEY", "")
# Matches AccidentIQ's env var naming convention. Falls back to the old
# PROPERTYIQ_ADMIN_PASSWORD name if ADMIN_DASHBOARD_PASSWORD isn't set yet,
# so this doesn't break the moment it deploys — rename the Render env var
# to ADMIN_DASHBOARD_PASSWORD when convenient, then the fallback can be
# removed later.
PROPERTYIQ_ADMIN_PASSWORD = os.getenv("ADMIN_DASHBOARD_PASSWORD", "") or os.getenv("PROPERTYIQ_ADMIN_PASSWORD", "")

# BETA ONLY — skips the real Dodo checkout call and immediately activates
# whatever tier the user selected, so the full auth -> tier -> Construction
# Studio flow can be tested end-to-end before Dodo envs are wired up.
# Defaults OFF. Must be explicitly set to the exact string "true" to engage —
# unset/anything else behaves exactly as before (real Dodo checkout).
PROPERTYIQ_BETA_BYPASS_PAYMENTS = os.getenv("PROPERTYIQ_BETA_BYPASS_PAYMENTS", "false").lower() == "true"

# Per-tier Dodo product IDs — each must be created as a recurring/subscription
# product in the Dodo dashboard first.
TIER_DODO_PRODUCT_IDS = {
    "studio_starter": os.getenv("DODO_PRODUCT_ID_STUDIO_STARTER", ""),
    "studio_pro": os.getenv("DODO_PRODUCT_ID_STUDIO_PRO", ""),
    "studio_unlimited": os.getenv("DODO_PRODUCT_ID_STUDIO_UNLIMITED", ""),
}


def get_dodo_webhook_client():
    """Separate from get_dodo_client() since webhook verification needs
    webhook_key, which checkout-flow calls don't use."""
    return DodoPayments(
        bearer_token=DODO_API_KEY,
        environment=DODO_ENVIRONMENT,
        webhook_key=os.getenv("DODO_PAYMENTS_WEBHOOK_KEY", ""),
    )


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

class RequestOtpRequest(BaseModel):
    email: str


class VerifyOtpRequest(BaseModel):
    email: str
    code: str


class AdminTierConfigRequest(BaseModel):
    password: str
    tier_config: dict


class AdminAuthRequest(BaseModel):
    password: str


def _require_admin_password(password: str) -> None:
    if not PROPERTYIQ_ADMIN_PASSWORD or password != PROPERTYIQ_ADMIN_PASSWORD:
        raise HTTPException(status_code=403, detail="Invalid admin password")


class SubscribeCheckoutRequest(BaseModel):
    tier_id: str


class InsightCheckoutRequest(BaseModel):
    report_id: str


@app.post("/api/auth/request-otp")
def request_otp(request: RequestOtpRequest):
    """Step 1 of email registration/login: sends a 6-digit code valid for
    10 minutes. Calling this again before the code is used invalidates the
    previous one."""
    code = create_otp(request.email)
    send_otp_email(request.email, code)
    return {"status": "sent"}


@app.post("/api/auth/verify-otp")
def verify_otp_endpoint(request: VerifyOtpRequest):
    """Step 2: verifying the code registers/logs in the user and returns a
    bearer session token (30-day expiry) to use as
    'Authorization: Bearer <token>' on subsequent calls."""
    if not verify_otp(request.email, request.code):
        raise HTTPException(status_code=401, detail="Invalid or expired code")

    token = create_session(request.email)
    return {"session_token": token}


@app.get("/api/tiers")
def list_tiers():
    """Public tier/pricing config for the pricing page. Base prices are USD;
    convert client-side for display using the same fx table Construction
    Studio uses."""
    return get_tier_config()


@app.get("/api/fx-rates")
def fx_rates():
    """USD-based FX table for converting displayed prices (tier pricing,
    Construction Studio estimates) to the visitor's local currency."""
    return get_fx_rates()


@app.post("/api/admin/tiers")
def update_tiers(request: AdminTierConfigRequest):
    """Admin-only: overwrite the tier config (features/prices/quotas).
    Password-gated via ADMIN_DASHBOARD_PASSWORD."""
    _require_admin_password(request.password)

    set_tier_config(request.tier_config)
    return {"status": "updated", "tier_config": request.tier_config}


@app.post("/api/admin/overview")
def admin_overview(request: AdminAuthRequest):
    """Admin-only: current tier config plus all subscriptions and Insight
    Add-on grants, for the admin panel's overview view. Password-gated via
    ADMIN_DASHBOARD_PASSWORD — same check as /api/admin/tiers."""
    _require_admin_password(request.password)

    return {
        "tier_config": get_tier_config(),
        "subscriptions": list_all_subscriptions(),
        "insight_grants": list_all_grants(),
    }


@app.post("/api/subscribe/checkout")
def subscribe_checkout(request: SubscribeCheckoutRequest, user_email: str = Depends(get_current_user_email)):
    """Creates a Dodo checkout session for a subscription tier. The Dodo
    product behind DODO_TIER_PRODUCT_IDS[tier_id] must be configured as a
    recurring/subscription product in the Dodo dashboard.

    BETA: if PROPERTYIQ_BETA_BYPASS_PAYMENTS=true, skips Dodo entirely and
    activates the tier immediately — no real payment, no checkout_url."""

    tier = get_tier(request.tier_id)
    if tier is None:
        raise HTTPException(status_code=404, detail=f"Unknown tier: {request.tier_id}")
    if tier["billing"] != "subscription":
        raise HTTPException(status_code=400, detail=f"Tier '{request.tier_id}' is not a subscription tier")

    if PROPERTYIQ_BETA_BYPASS_PAYMENTS:
        dummy_subscription_id = f"beta_dummy_{uuid.uuid4()}"
        upsert_subscription(
            email=user_email,
            tier_id=request.tier_id,
            status="active",
            dodo_subscription_id=dummy_subscription_id,
        )
        return {
            "checkout_url": None,
            "beta_bypass": True,
            "status": "active",
            "tier_id": request.tier_id,
            "note": "Payment bypassed in beta — tier activated immediately. Replace with real Dodo "
                    "checkout once DODO_PRODUCT_ID_* envs are set and PROPERTYIQ_BETA_BYPASS_PAYMENTS is unset.",
        }

    product_id = TIER_DODO_PRODUCT_IDS.get(request.tier_id)
    if not product_id:
        raise HTTPException(
            status_code=503,
            detail=f"No Dodo product configured for tier '{request.tier_id}'. "
                   f"Set env var DODO_PRODUCT_ID_{request.tier_id.upper()}."
        )

    client = get_dodo_client()
    session = client.checkout_sessions.create(
        product_cart=[{"product_id": product_id, "quantity": 1}],
        customer={"email": user_email},
        metadata={"tier_id": request.tier_id, "user_email": user_email},
        return_url=f"{FRONTEND_URL}/studio?subscribed=1",
    )

    upsert_subscription(
        email=user_email,
        tier_id=request.tier_id,
        status="pending_payment",
        dodo_checkout_session_id=session.id if hasattr(session, "id") else None,
    )

    return {"checkout_url": session.checkout_url if hasattr(session, "checkout_url") else session}


@app.post("/api/insight/checkout")
def insight_checkout(request: InsightCheckoutRequest, user_email: str = Depends(get_current_user_email)):
    """One-time checkout for the Insight Add-on (similar property
    suggestions), tied to a specific report_id.

    BETA: if PROPERTYIQ_BETA_BYPASS_PAYMENTS=true, skips Dodo entirely and
    returns immediate access — no real payment, no checkout_url."""

    if PROPERTYIQ_BETA_BYPASS_PAYMENTS:
        grant_insight_access(request.report_id, user_email)
        return {
            "checkout_url": None,
            "beta_bypass": True,
            "status": "granted",
            "report_id": request.report_id,
            "note": "Payment bypassed in beta. Replace with real Dodo checkout once "
                    "DODO_PRODUCT_ID_INSIGHT_ADDON is set and PROPERTYIQ_BETA_BYPASS_PAYMENTS is unset.",
        }

    product_id = os.getenv("DODO_PRODUCT_ID_INSIGHT_ADDON", "")
    if not product_id:
        raise HTTPException(
            status_code=503,
            detail="Insight add-on is not configured. Set DODO_PRODUCT_ID_INSIGHT_ADDON."
        )

    client = get_dodo_client()
    session = client.checkout_sessions.create(
        product_cart=[{"product_id": product_id, "quantity": 1}],
        customer={"email": user_email},
        metadata={"tier_id": "insight_addon", "report_id": request.report_id, "user_email": user_email},
        return_url=f"{FRONTEND_URL}/report/{request.report_id}?insight=1",
    )

    return {"checkout_url": session.checkout_url if hasattr(session, "checkout_url") else session}


@app.post("/api/webhooks/dodo")
async def dodo_webhook(request: Request):
    """Handles subscription lifecycle + one-time Insight add-on payments.
    Verifies the Standard Webhooks signature via Dodo's SDK before trusting
    any payload, per https://docs.dodopayments.com/developer-resources/webhooks"""

    webhook_client = get_dodo_webhook_client()
    raw_body = await request.body()

    try:
        event = webhook_client.webhooks.unwrap(
            raw_body,
            headers={
                "webhook-id": request.headers.get("webhook-id", ""),
                "webhook-signature": request.headers.get("webhook-signature", ""),
                "webhook-timestamp": request.headers.get("webhook-timestamp", ""),
            },
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event_type = getattr(event, "type", None) or event.get("type")
    data = getattr(event, "data", None) or event.get("data", {})
    metadata = getattr(data, "metadata", None) or (data.get("metadata") if isinstance(data, dict) else {}) or {}

    tier_id = metadata.get("tier_id")
    user_email = metadata.get("user_email")
    dodo_subscription_id = getattr(data, "subscription_id", None) or (
        data.get("subscription_id") if isinstance(data, dict) else None
    )

    if event_type in ("subscription.active", "subscription.renewed") and tier_id and user_email:
        upsert_subscription(
            email=user_email,
            tier_id=tier_id,
            status="active",
            dodo_subscription_id=dodo_subscription_id,
        )
    elif event_type == "subscription.cancelled" and dodo_subscription_id:
        set_status_by_dodo_id(dodo_subscription_id, "cancelled")
    elif event_type == "subscription.failed" and dodo_subscription_id:
        set_status_by_dodo_id(dodo_subscription_id, "payment_failed")
    elif event_type == "payment.succeeded" and tier_id == "insight_addon" and metadata.get("report_id") and user_email:
        grant_insight_access(metadata["report_id"], user_email)

    return {"received": True}


@app.get("/api/subscribe/status")
def subscribe_status(user_email: str = Depends(get_current_user_email)):
    """Current subscription tier + design quota remaining this month."""
    sub = get_subscription(user_email)
    tier_id = get_active_tier(user_email)

    if not tier_id:
        return {"tier_id": None, "status": sub["status"] if sub else "none", "design_quota_per_month": 0, "designs_used_this_month": 0}

    tier = get_tier(tier_id)
    quota = tier["design_quota_per_month"] if tier else 0
    used = count_designs_this_month(user_email)

    return {
        "tier_id": tier_id,
        "status": "active",
        "design_quota_per_month": quota,
        "designs_used_this_month": used,
        "designs_remaining": None if quota is None else max(0, quota - used),
    }


def _has_similar_properties_access(user_email: str, report_id: str) -> bool:
    """Access via either the one-time Insight Add-on grant for this specific
    report, or an active subscription tier whose features include it."""
    if has_insight_access(report_id, user_email):
        return True

    tier_id = get_active_tier(user_email)
    if tier_id:
        tier = get_tier(tier_id)
        if tier and "similar_property_suggestions" in tier.get("features", []):
            return True

    return False


@app.get("/api/similar-properties/{report_id}")
def similar_properties(
    report_id: str,
    city: str,
    property_type: str,
    subject_price_per_sqft: float = 0,
    user_email: str = Depends(get_current_user_email),
):
    """Similar property suggestions with vital params (price/sqft, price
    delta vs subject, developer). Requires either a purchased Insight
    Add-on grant for this report_id, or an active Studio subscription."""

    if not _has_similar_properties_access(user_email, report_id):
        raise HTTPException(
            status_code=403,
            detail="Similar property suggestions require the Insight Add-on for this report "
                   "(POST /api/insight/checkout) or an active Studio subscription."
        )

    return get_similar_properties(
        city=city,
        property_type=property_type,
        subject_price_per_sqft=subject_price_per_sqft,
    )


class ConstructionEstimateRequest(BaseModel):
    plot_size_sqft: float
    selections: dict[str, str]
    region: str = "global"
    currency: str = "USD"


class RoomSpec(BaseModel):
    name: str
    x: float
    y: float
    length: float
    width: float
    color: Optional[str] = None  # "#rrggbb" — carried through to the real DXF export


class ConstructionDesignRequest(BaseModel):
    plot_size_sqft: float
    plot_length_ft: float
    plot_width_ft: float
    selections: dict[str, str]
    region: str = "global"
    currency: str = "USD"
    entrance_direction: str
    road_facing_side: str
    slope_direction: Optional[str] = None
    rooms: list[RoomSpec] = []
    has_imported_materials: bool = False


@app.get("/api/construction-studio/materials")
def construction_materials(region: str = "global"):
    """Available material/supplier options for a region. Base costs are in
    USD; convert client-side or via /estimate for a specific currency."""
    return {"region": region, "categories": get_catalog(region)}


@app.post("/api/construction-studio/estimate")
def construction_estimate(request: ConstructionEstimateRequest):
    """Live running cost total as the user picks materials — call this on
    every selection change to update the on-screen total."""
    if request.plot_size_sqft <= 0:
        raise HTTPException(status_code=400, detail="plot_size_sqft must be greater than 0")

    return estimate_cost(
        plot_size_sqft=request.plot_size_sqft,
        selections=request.selections,
        region=request.region,
        currency=request.currency,
    )


@app.post("/api/construction-studio/design")
def construction_design(request: ConstructionDesignRequest, user_email: str = Depends(get_current_user_email)):
    """Finalize a Construction Studio design: computes final cost estimate,
    runs the basic Vastu directional check, generates the risk section, and
    exports a real, portable DXF file of the plot layout.

    Requires an active Studio subscription and enforces that tier's monthly
    design quota (None quota = unlimited)."""

    tier_id = get_active_tier(user_email)
    if not tier_id:
        raise HTTPException(
            status_code=403,
            detail="Construction Studio requires an active Studio subscription. "
                   "Subscribe via POST /api/subscribe/checkout first."
        )

    tier = get_tier(tier_id)
    quota = tier["design_quota_per_month"] if tier else 0
    if quota is not None:
        used = count_designs_this_month(user_email)
        if used >= quota:
            raise HTTPException(
                status_code=403,
                detail=f"Monthly design quota reached ({used}/{quota}) for the {tier['label']} tier. "
                       f"Upgrade your plan or wait until next month."
            )

    if request.plot_size_sqft <= 0:
        raise HTTPException(status_code=400, detail="plot_size_sqft must be greater than 0")

    cost_estimate = estimate_cost(
        plot_size_sqft=request.plot_size_sqft,
        selections=request.selections,
        region=request.region,
        currency=request.currency,
    )

    if request.rooms:
        vastu_result = check_vastu_full(
            plot_length_ft=request.plot_length_ft,
            plot_width_ft=request.plot_width_ft,
            rooms=[r.model_dump() for r in request.rooms],
            entrance_direction=request.entrance_direction,
            road_facing_side=request.road_facing_side,
            slope_direction=request.slope_direction,
        )
    else:
        # No room layout yet — fall back to the entrance/road/slope-only check.
        vastu_result = check_vastu_basics(
            entrance_direction=request.entrance_direction,
            road_facing_side=request.road_facing_side,
            slope_direction=request.slope_direction,
        )

    risks = identify_construction_risks(
        region=request.region,
        grand_total_usd=cost_estimate["grand_total_usd"],
        currency=request.currency,
        has_imported_materials=request.has_imported_materials,
    )

    design_id = str(uuid.uuid4())

    dxf_path = None
    if request.rooms:
        generated_path = generate_plot_dxf(
            design_id=design_id,
            plot_length_ft=request.plot_length_ft,
            plot_width_ft=request.plot_width_ft,
            rooms=[r.model_dump() for r in request.rooms],
            road_facing_side=request.road_facing_side,
        )
        dxf_path = str(generated_path)

    plot_spec = {
        "plot_size_sqft": request.plot_size_sqft,
        "plot_length_ft": request.plot_length_ft,
        "plot_width_ft": request.plot_width_ft,
        "entrance_direction": request.entrance_direction,
        "road_facing_side": request.road_facing_side,
        "slope_direction": request.slope_direction,
        "rooms": [r.model_dump() for r in request.rooms],
    }

    save_design(
        design_id=design_id,
        user_email=user_email,
        region=request.region,
        currency=request.currency,
        plot_spec=plot_spec,
        selections=request.selections,
        cost_estimate=cost_estimate,
        vastu_result=vastu_result,
        risks=risks,
        dxf_path=dxf_path,
    )

    return {
        "design_id": design_id,
        "cost_estimate": cost_estimate,
        "vastu_result": vastu_result,
        "risks": risks,
        "dxf_available": dxf_path is not None,
    }


@app.get("/api/construction-studio/design/{design_id}")
def get_construction_design(design_id: str):
    design = get_design(design_id)
    if design is None:
        raise HTTPException(status_code=404, detail="Design not found")
    return design


@app.get("/api/construction-studio/design/{design_id}/dxf")
def download_construction_dxf(design_id: str):
    design = get_design(design_id)
    if design is None:
        raise HTTPException(status_code=404, detail="Design not found")
    if not design.get("dxf_path"):
        raise HTTPException(status_code=404, detail="No DXF file was generated for this design (no rooms provided)")

    return FileResponse(
        path=design["dxf_path"],
        media_type="application/dxf",
        filename=f"PropertyIQ_ConstructionStudio_{design_id}.dxf",
    )


@app.get("/")
def health():
    return {
        "service": "PropertyIQ API",
        "version": "1.0.0-beta",
        "status": "healthy"
    }    