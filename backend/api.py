from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from typing import Any, Optional
from pydantic import BaseModel

import os
import json
import uuid
import asyncio
from datetime import datetime, timezone
from contextlib import asynccontextmanager
import requests

from dodopayments import DodoPayments

from backend.payment_store import (
    initialize_payment_store,
    create_order,
    attach_checkout_session,
    get_order,
    mark_order_paid,
    mark_order_failed,
)

from backend.construction_store import (
    initialize_construction_store,
    save_design,
    get_design,
    count_designs_this_month,
)

from backend.property_store import (
    initialize_property_store,
    create_property,
    list_properties_for_user,
    get_property,
    update_property,
    upsert_floor,
    delete_floor,
    sync_property,
    set_locked,
    delete_property,
    count_saved_properties,
    set_shared_with_emails,
    list_properties_shared_with_user,
)

from backend.construction_studio import (
    get_catalog,
    get_labor_catalog,
    get_fx_rates,
    estimate_cost,
    check_vastu_basics,
    identify_construction_risks,
    generate_bill_of_materials,
    generate_bill_of_quantities,
)

from backend.vastu_engine import (
    check_vastu_full,
)

from backend.thai_traditional_engine import (
    check_thai_traditional_full,
    check_thai_orientation,
)

from backend.compliance_rules import get_vastu_rules, get_thai_rules
from backend.design_disciplines import group_by_discipline
from backend.discipline_overlays import compute_structural_overlay, compute_plumbing_overlay, compute_electrical_overlay
from backend.comparables import get_comparables, average_price_per_sqft
from backend.neighborhood_infrastructure import get_infrastructure_summary
from backend.construction_report import generate_construction_report_pdf

from backend.adjacency_engine import (
    evaluate_adjacency,
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
    get_all_tiers_merged,
    has_feature,
    ALL_FEATURES,
    set_app_setting,
    get_app_setting,
)

from backend.subscription_store import (
    initialize_subscription_store,
    upsert_subscription,
    get_subscription,
    set_status_by_dodo_id,
    get_active_tier,
    list_all_subscriptions,
)

from backend.property_url_extract import extract_property_data, get_gemini_api_key

from backend.insight_store import (
    initialize_insight_store,
    grant_insight_access,
    has_insight_access,
    list_all_grants,
)

from backend.similar_properties import (
    get_similar_properties,
)

from backend.instant_score import compute_instant_score

from backend.hidden_deal import find_hidden_deal_insights

from backend.red_flag_hunt import evaluate_red_flag_guess, VALID_CATEGORIES

from backend.challenge_store import (
    initialize_challenge_store,
    create_challenge,
    get_challenge,
    reveal_challenge_guess,
)

from backend.price_watch_store import (
    initialize_price_watch_store,
    create_price_watch,
    get_price_watch,
    update_watch_price,
    count_active_watches_for_email,
)
from backend.price_watch_scheduler import price_watch_check_loop

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

_price_watch_task = None


@asynccontextmanager
async def _lifespan(app: FastAPI):
    """Starts the periodic price-watch re-checker as a background
    asyncio task within this same process on startup, cancels it
    cleanly on shutdown — see backend/price_watch_scheduler.py's own
    docstring for why this approach (rather than a separate cron
    service) is the real, working choice given Render's standard
    web-service tier."""
    global _price_watch_task
    _price_watch_task = asyncio.create_task(price_watch_check_loop())
    yield
    if _price_watch_task is not None:
        _price_watch_task.cancel()


app = FastAPI(lifespan=_lifespan)


initialize_payment_store()
initialize_construction_store()
initialize_property_store()
initialize_auth_store()
initialize_config_store()
initialize_subscription_store()
initialize_insight_store()
initialize_challenge_store()
initialize_price_watch_store()

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
# product in the Dodo dashboard first. insight_addon is included here too
# (even though it's one-time, not subscription) since both this mapping and
# the price-overlay logic below need a single, complete lookup covering
# every tier, not just the 3 subscription ones.
TIER_DODO_PRODUCT_IDS = {
    "insight_addon": os.getenv("DODO_PRODUCT_ID_INSIGHT_ADDON", ""),
    "studio_starter": os.getenv("DODO_PRODUCT_ID_STUDIO_STARTER", ""),
    "studio_pro": os.getenv("DODO_PRODUCT_ID_STUDIO_PRO", ""),
    "studio_unlimited": os.getenv("DODO_PRODUCT_ID_STUDIO_UNLIMITED", ""),
}


def get_dodo_product_price(product_id: str) -> Optional[dict[str, Any]]:
    """Fetches a product's real, current price directly from Dodo's own
    API — the actual source of truth for what a customer is charged.
    Cached 1 hour (via the same _get_cached_json/_set_cached_json
    helpers the neighborhood-insights endpoints use) since prices don't
    change minute-to-minute and this would otherwise be called on every
    single pricing-page load.

    This exists because of a real, confirmed gap: PropertyIQ's own
    stored `price_usd` per tier was never actually sent to Dodo at
    checkout at all — checkout only ever passes a product_id, and Dodo
    itself determines the real charge from that product's own
    configured price. `price_usd` was purely a locally-editable display
    value with no connection to what a customer is actually charged,
    meaning an admin editing it in the dashboard could easily, silently
    create a mismatch between the displayed and the real price. Reading
    the real price directly from Dodo closes that gap.

    Returns {"price_usd": float, "currency": str, "is_recurring": bool}
    or None if the product isn't configured, Dodo is unreachable, or
    the key isn't set — callers should fall back to the locally-stored
    price in that case rather than breaking the whole pricing page over
    a transient Dodo outage."""
    if not product_id or not DODO_API_KEY:
        return None

    cache_key = f"dodo_product_price_{product_id}"
    cached = _get_cached_json(cache_key, ttl_hours=1)
    if cached is not None:
        return cached

    try:
        client = DodoPayments(bearer_token=DODO_API_KEY, environment=DODO_ENVIRONMENT)
        product = client.products.retrieve(product_id)
        price = product.price
        # price.price is in the smallest currency denomination (cents
        # for USD) per Dodo's own real API shape — confirmed directly
        # against the installed SDK's actual Price type, not assumed.
        result = {
            "price_usd": round(price.price / 100, 2),
            "currency": price.currency,
            "is_recurring": price.type == "recurring_price",
        }
    except Exception:
        return None

    _set_cached_json(cache_key, result)
    return result


def overlay_dodo_prices(tiers: dict[str, Any]) -> dict[str, Any]:
    """Returns a copy of `tiers` with price_usd/currency replaced by the
    real, current Dodo price wherever a product is configured and
    reachable — the locally-stored value is kept as an honest fallback
    (with price_source explicitly marked) for a tier whose product_id
    isn't set yet or when Dodo is temporarily unreachable, rather than
    breaking the pricing page entirely over a transient outage.
    price_source lets the admin panel distinguish a real, live Dodo
    price from a stale local fallback, rather than showing both
    identically as if they were equally trustworthy."""
    result = {}
    for tier_id, tier in tiers.items():
        tier_copy = dict(tier)
        product_id = TIER_DODO_PRODUCT_IDS.get(tier_id)
        dodo_price = get_dodo_product_price(product_id) if product_id else None
        if dodo_price:
            tier_copy["price_usd"] = dodo_price["price_usd"]
            tier_copy["price_source"] = "dodo"
        else:
            tier_copy["price_source"] = "local_fallback"
        result[tier_id] = tier_copy
    return result


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


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Defense-in-depth: without this, an unhandled exception's default
    error response skips CORSMiddleware entirely — a confirmed Starlette
    architecture gotcha (ServerErrorMiddleware sits OUTSIDE CORSMiddleware
    in the stack, so even a registered exception_handler's response never
    passes back through it — see Starlette #2876, FastAPI discussions
    #7847/#13398/#14313). The browser then reports it as "blocked by CORS
    policy" / "Failed to fetch", hiding that a genuine server-side 500
    occurred — confirmed as the actual root cause of exactly that report
    here (traced to a KeyError from stale persisted tier config missing a
    newer field). The documented, community-confirmed fix is to set the
    CORS headers manually on this response, matching what CORSMiddleware
    itself would have set (echoing the specific request Origin, since
    allow_credentials=True makes a literal "*" invalid) — verified
    directly: this exact scenario reproduced the missing header with only
    the handler registered, and setting these manually is what actually
    fixed it, not just registering the handler."""
    import traceback
    traceback.print_exc()

    headers = {}
    origin = request.headers.get("origin")
    if origin:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"

    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on our end. Please try again in a moment."},
        headers=headers,
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


@app.get("/api/orders/{order_id}/status")
def get_order_status(order_id: str):
    """Lets the frontend confirm what happened to a report-unlock
    payment after the user is redirected back from Dodo's checkout — a
    real, confirmed gap this closes: the frontend had no way at all to
    check this before (no code even handled the ?payment=return
    redirect), and the webhook alone isn't something a browser can wait
    on synchronously, so a poll-able status endpoint is the correct
    complement to it, not a replacement. Deliberately unauthenticated —
    the order_id itself is the capability (a random UUID a
    non-logged-in visitor's checkout redirect carries), matching how
    this entire one-time-report flow was designed to not require an
    account."""
    order = get_order(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return {
        "order_id": order["order_id"],
        "status": order["status"],
        "updated_at": order["updated_at"],
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
    Studio uses. Prices are overlaid with the real, current value from
    Dodo's own API wherever a product is configured and reachable — see
    overlay_dodo_prices's own docstring for why the locally-stored
    price_usd alone was never actually reliable."""
    return overlay_dodo_prices(get_all_tiers_merged())


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
    ADMIN_DASHBOARD_PASSWORD — same check as /api/admin/tiers.

    Includes all_features (the canonical list of every feature the
    system actually enforces) so the admin panel can render a checkbox
    for each one against every tier, not just whatever happens to
    already be in that tier's saved features list — otherwise a newly
    added feature would have no way to ever get toggled on for a tier
    that doesn't already include it."""
    _require_admin_password(request.password)

    return {
        "tier_config": overlay_dodo_prices(get_all_tiers_merged()),
        "subscriptions": list_all_subscriptions(),
        "insight_grants": list_all_grants(),
        "all_features": ALL_FEATURES,
        # Never returns the actual key value, even to an authenticated
        # admin — just whether one is configured, matching how most
        # admin panels handle displaying secrets back. The panel shows
        # "configured"/"not set" and a field to overwrite it, not the
        # current value.
        "gemini_api_key_configured": bool(get_gemini_api_key()),
        # Current show/hide state for every Neighborhood Insights
        # section, so the admin panel can render the real, current
        # toggles rather than assuming everything defaults to visible.
        "ni_section_visibility": get_ni_section_visibility(),
    }


class AdminSettingsRequest(BaseModel):
    password: str
    gemini_api_key: Optional[str] = None
    ni_section_visibility: Optional[dict[str, bool]] = None


@app.post("/api/admin/settings")
def admin_settings(request: AdminSettingsRequest):
    """Admin-only: sets the Gemini API key used as the LLM fallback for
    property_url_import when the free structured-data extraction path
    isn't enough — a real, explicit request: making this admin-
    configurable at runtime rather than only an env var, so it can be
    changed without a redeploy. Only ever accepts a new value to set;
    never returns the current one back (see admin_overview's
    gemini_api_key_configured for the presence-only status check).

    Also accepts ni_section_visibility: a real, explicit request to
    make every Neighborhood Insights page section independently show/
    hide-able from here, without a code change or redeploy for what's
    fundamentally an operational decision, not a code one."""
    _require_admin_password(request.password)

    if request.gemini_api_key is not None:
        set_app_setting("gemini_api_key", request.gemini_api_key.strip())

    if request.ni_section_visibility is not None:
        # Merge onto the existing saved map rather than overwrite it
        # wholesale — the request may only include a subset of
        # sections (e.g. toggling just one), and any section already
        # correctly configured but not present in this particular
        # request must not silently reset to its default.
        current = get_ni_section_visibility()
        current.update(request.ni_section_visibility)
        set_app_setting(NI_VISIBILITY_SETTING_KEY, json.dumps(current))

    return {
        "gemini_api_key_configured": bool(get_gemini_api_key()),
        "ni_section_visibility": get_ni_section_visibility(),
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
    if tier.get("billing") != "subscription":
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
        return_url=f"{FRONTEND_URL}/?subscribed=1",
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

    insight_tier = get_tier("insight_addon")
    if insight_tier and insight_tier.get("mode") == "free":
        raise HTTPException(
            status_code=400,
            detail="Similar property suggestions are currently free for everyone — there's nothing to buy."
        )

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
        return_url=f"{FRONTEND_URL}/?insight=1&report_id={request.report_id}",
    )

    return {"checkout_url": session.checkout_url if hasattr(session, "checkout_url") else session}


@app.get("/api/insight/status/{report_id}")
def insight_status(report_id: str, user_email: str = Depends(get_current_user_email)):
    """Lets the frontend confirm the Insight Add-on payment actually went
    through after returning from Dodo's checkout — a real, confirmed gap
    this closes alongside the subscription and report-unlock flows: the
    return_url previously pointed at /report/{report_id}?insight=1, a
    path this SPA has no route for at all, and nothing on the frontend
    read the insight=1 query param either. Authenticated (unlike the
    report-unlock order-status endpoint) since insight access is tied to
    a specific logged-in account, not a bare capability token.

    Uses the same _has_similar_properties_access check the actual data
    endpoint uses (not a narrower has_insight_access-only check) — a
    real consistency gap this closes: this previously only checked for
    a specific per-report purchase grant, so it would have incorrectly
    reported "not unlocked" for a user with free-mode or subscription
    access, even though they could genuinely already see the data."""
    return {"report_id": report_id, "unlocked": _has_similar_properties_access(user_email, report_id)}


class PropertyUrlExtractRequest(BaseModel):
    url: str


@app.post("/api/property/extract-from-url")
def property_extract_from_url(request: PropertyUrlExtractRequest, user_email: str = Depends(get_current_user_email)):
    """Fetches a real-estate listing URL from any site and extracts
    whichever property-form fields are genuinely stated on the page,
    via Claude — the property_url_import tier feature. Gated by
    has_feature like every other tier feature; the same enforcement
    point admin-toggling already controls.

    Deliberately does NOT attempt to fill the fraud-verification fields
    (government guidance value, independently-researched market
    average, developer track record) — those are essentially never
    published on a listing page, and this endpoint would rather return
    null for a field than guess or hallucinate a value for something a
    real fraud-detection tool needs to independently verify, not trust
    from the same listing it's meant to be checking."""
    tier_id = get_active_tier(user_email)
    if not has_feature(tier_id, "property_url_import"):
        raise HTTPException(
            status_code=403,
            detail="Importing property details from a URL requires an active Studio "
                   "subscription that includes this feature."
        )

    if not request.url.strip().lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Please provide a valid http(s) URL.")

    try:
        extracted = extract_property_data(request.url.strip())
    except requests.Timeout as exc:
        raise HTTPException(
            status_code=422,
            detail="That site took too long to respond. Please try again, or fill in the form manually."
        ) from exc
    except requests.ConnectionError as exc:
        raise HTTPException(
            status_code=422,
            detail="Couldn't reach that site at all — please double-check the URL is correct and the "
                   "site is currently online."
        ) from exc
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else None
        if status in (403, 429):
            raise HTTPException(
                status_code=422,
                detail="This site is blocking automated access to this page (some listing sites use bot "
                       "protection that a simple fetch can't get past). Please copy the property details "
                       "into the form manually instead."
            ) from exc
        if status == 404:
            raise HTTPException(
                status_code=422,
                detail="That page doesn't exist (404) — please double-check the URL, or the listing may "
                       "have been taken down."
            ) from exc
        if status is not None and status >= 500:
            raise HTTPException(
                status_code=422,
                detail="That site is having problems on its own end right now — please try again in a "
                       "few minutes, or fill in the form manually."
            ) from exc
        raise HTTPException(status_code=502, detail=f"Couldn't fetch that URL: {exc}") from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Couldn't fetch that URL: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        # A genuine safety net, not expected to fire in normal operation:
        # without this, any exception type not explicitly anticipated
        # above (a real bug, an unexpected library error) would surface
        # to the user as FastAPI's bare, unhelpful default 500 response
        # instead of a clear, actionable message.
        raise HTTPException(
            status_code=500,
            detail="Something unexpected went wrong while importing from that URL. "
                   "Please try again, or fill in the form manually."
        ) from exc

    return {"extracted": extracted}


@app.post("/api/webhooks/dodo")
async def dodo_webhook(request: Request):
    """Handles subscription lifecycle + one-time Insight add-on payments.
    Verifies the Standard Webhooks signature via Dodo's SDK before trusting
    any payload, per https://docs.dodopayments.com/developer-resources/webhooks

    A real, confirmed gap this closes: checkout-session metadata
    (tier_id/user_email, passed when the checkout was first created) is
    not guaranteed to land directly on the subscription webhook's data
    object — a real, working Dodo integration example (retrieving the
    full subscription via the API inside the webhook handler, rather
    than trusting the webhook payload alone) confirmed this is a real
    risk, not a hypothetical one. This was the actual cause of a real
    reported failure: a test subscription payment succeeded on Dodo's
    side, but the tier never activated in PropertyIQ, because tier_id/
    user_email came back empty from the webhook payload's metadata.
    Falls back to fetching the full subscription object via the API and
    deriving both values from it (customer email directly; tier_id via
    a reverse lookup against TIER_DODO_PRODUCT_IDS using the
    subscription's product_id, which is guaranteed to be present on any
    subscription object regardless of whether metadata propagated)."""

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
    except Exception as exc:
        # Logged with the actual exception, not a bare 401 — a real,
        # important diagnostic gap: the specific reason this can fail
        # (wrong/malformed webhook secret, missing headers, a genuinely
        # invalid signature) all looked identical from the outside as
        # "401 Unauthorized" with no way to tell them apart from Render's
        # logs alone. This traces the real, installed dodopayments/
        # standardwebhooks library source directly (not guessed) to
        # confirm exactly what unwrap()/verify() can raise here, so this
        # log line will show the genuine cause on the next attempt.
        print(f"Dodo webhook signature verification failed: {type(exc).__name__}: {exc}")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event_type = getattr(event, "type", None) or event.get("type")
    data = getattr(event, "data", None) or event.get("data", {})
    metadata = getattr(data, "metadata", None) or (data.get("metadata") if isinstance(data, dict) else {}) or {}

    tier_id = metadata.get("tier_id")
    user_email = metadata.get("user_email")
    dodo_subscription_id = getattr(data, "subscription_id", None) or (
        data.get("subscription_id") if isinstance(data, dict) else None
    )
    dodo_payment_id = getattr(data, "payment_id", None) or (
        data.get("payment_id") if isinstance(data, dict) else None
    )

    if event_type in ("subscription.active", "subscription.renewed", "subscription.updated") and dodo_subscription_id and not (tier_id and user_email):
        try:
            subscription = webhook_client.subscriptions.retrieve(dodo_subscription_id)
            sub_metadata = getattr(subscription, "metadata", None) or {}
            if not tier_id:
                sub_product_id = getattr(subscription, "product_id", None)
                tier_id = sub_metadata.get("tier_id") or next(
                    (t for t, pid in TIER_DODO_PRODUCT_IDS.items() if pid and pid == sub_product_id), None
                )
            if not user_email:
                customer = getattr(subscription, "customer", None)
                user_email = sub_metadata.get("user_email") or (getattr(customer, "email", None) if customer else None)
        except Exception:
            pass  # tier_id/user_email stay whatever they were; the condition below simply won't match

    sub_status = getattr(data, "status", None) or (data.get("status") if isinstance(data, dict) else None)

    # A real, confirmed third root cause, found via an actual live
    # webhook payload the user pasted directly: Dodo sent
    # subscription.updated (not subscription.active/renewed at all) for
    # a genuinely successful, active subscription — with tier_id/
    # user_email correctly present in metadata the whole time (so the
    # earlier metadata-fallback fix, while a reasonable defensive
    # measure, was never the actual problem here). subscription.updated
    # fires on ANY field change, per Dodo's own docs, which recommend it
    # as the reliable way to track subscription state — so it can't be
    # treated as an automatic "activate" signal the way
    # subscription.active can; it must be interpreted using the
    # payload's own current status field instead.
    if event_type in ("subscription.active", "subscription.renewed") and tier_id and user_email:
        upsert_subscription(
            email=user_email,
            tier_id=tier_id,
            status="active",
            dodo_subscription_id=dodo_subscription_id,
        )
    elif event_type == "subscription.updated" and tier_id and user_email and sub_status == "active":
        upsert_subscription(
            email=user_email,
            tier_id=tier_id,
            status="active",
            dodo_subscription_id=dodo_subscription_id,
        )
    elif event_type == "subscription.updated" and dodo_subscription_id and sub_status in ("cancelled", "expired"):
        set_status_by_dodo_id(dodo_subscription_id, "cancelled")
    elif event_type == "subscription.updated" and dodo_subscription_id and sub_status == "on_hold":
        set_status_by_dodo_id(dodo_subscription_id, "payment_failed")
    elif event_type == "subscription.cancelled" and dodo_subscription_id:
        set_status_by_dodo_id(dodo_subscription_id, "cancelled")
    elif event_type == "subscription.failed" and dodo_subscription_id:
        set_status_by_dodo_id(dodo_subscription_id, "payment_failed")
    elif event_type == "payment.succeeded" and tier_id == "insight_addon" and metadata.get("report_id") and user_email:
        grant_insight_access(metadata["report_id"], user_email)
    elif event_type == "payment.succeeded" and metadata.get("product") == "propertyiq_report" and metadata.get("order_id"):
        # The one-time report-unlock payment — a real, confirmed gap this
        # closes: this branch never existed at all before, so a
        # successful payment for this specific product triggered zero
        # backend action (the order stayed "pending_payment" forever,
        # and nothing ever told the user their payment went through).
        mark_order_paid(metadata["order_id"], dodo_payment_id=dodo_payment_id)
    elif event_type == "payment.failed" and metadata.get("product") == "propertyiq_report" and metadata.get("order_id"):
        mark_order_failed(metadata["order_id"])

    return {"received": True}


@app.get("/api/subscribe/status")
def subscribe_status(user_email: str = Depends(get_current_user_email)):
    """Current subscription tier + design quota remaining this month."""
    sub = get_subscription(user_email)
    tier_id = get_active_tier(user_email)

    if not tier_id:
        return {"tier_id": None, "status": sub["status"] if sub else "none", "design_quota_per_month": 0, "designs_used_this_month": 0}

    tier = get_tier(tier_id)
    quota = tier.get("design_quota_per_month", 0) if tier else 0
    used = count_designs_this_month(user_email)

    return {
        "tier_id": tier_id,
        "status": "active",
        "design_quota_per_month": quota,
        "designs_used_this_month": used,
        "designs_remaining": None if quota is None else max(0, quota - used),
    }


def _has_similar_properties_access(user_email: str, report_id: str) -> bool:
    """Access via free mode (an admin-toggleable, product-wide setting —
    see insight_addon's "mode" field), the one-time Insight Add-on grant
    for this specific report, or an active subscription tier whose
    features include it."""
    insight_tier = get_tier("insight_addon")
    if insight_tier and insight_tier.get("mode") == "free":
        return True

    if has_insight_access(report_id, user_email):
        return True

    tier_id = get_active_tier(user_email)
    if tier_id:
        tier = get_tier(tier_id)
        if tier and "similar_property_suggestions" in tier.get("features", []):
            return True

    return False


class InstantScoreRequest(BaseModel):
    price: float
    city: str
    property_type: str
    area_value: float
    area_unit: str = "sqft"
    location: Optional[str] = None


class NeighborhoodResaleSignalResponse(BaseModel):
    has_data: bool
    comparable_count: int
    average_price_per_sqft: float
    currency: str
    data_source: str


# Same LocationIQ service AccidentIQ's own Travel Safety page uses for
# autocomplete/nearby-place search (confirmed directly from that page's
# real source, not assumed) — proxied through this backend rather than
# called directly from the browser for a real, necessary reason: a
# direct client-side fetch() to LocationIQ's API from this app's own
# domain gets blocked by LocationIQ's CORS policy (confirmed directly —
# the request reaches their server and gets a response, just without
# an Access-Control-Allow-Origin header covering this origin). A
# server-to-server request from this backend isn't subject to browser
# CORS at all, which is what actually fixes it. The key itself is read
# from an env var, never hardcoded here.
LOCATIONIQ_API_KEY = os.environ.get("LOCATIONIQ_API_KEY", "")
LOCATIONIQ_BASE = "https://us1.locationiq.com/v1"


def _get_cached_json(cache_key: str, ttl_hours: int) -> Optional[Any]:
    """Generic JSON cache read against the same get_app_setting/
    set_app_setting key-value store neighborhood_infrastructure.py and
    live_comparables.py already use for their own caching — a real,
    deliberate cost-reduction measure, not a nice-to-have, for any
    endpoint that would otherwise re-fetch identical external data on
    every single call."""
    raw = get_app_setting(cache_key)
    if not raw:
        return None
    try:
        cached = json.loads(raw)
        fetched_at = datetime.fromisoformat(cached["fetched_at"])
        age_hours = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
        if age_hours < ttl_hours:
            return cached["result"]
    except (json.JSONDecodeError, KeyError, ValueError):
        pass  # a corrupted/unexpected cache entry is treated as a cache miss, not an error
    return None


def _set_cached_json(cache_key: str, result: Any) -> None:
    set_app_setting(cache_key, json.dumps({"result": result, "fetched_at": datetime.now(timezone.utc).isoformat()}))


@app.get("/api/neighborhood-insights/autocomplete")
def neighborhood_autocomplete(q: str, country: str = "in"):
    """Proxies LocationIQ's /autocomplete endpoint for the Neighborhood
    Insights address field. Public (no auth) — same reasoning as the
    resale-signal endpoint just below: a free, no-signup entry point.

    `country` is a lowercase ISO 3166-1 alpha-2 code (LocationIQ's own
    countrycodes parameter format), defaulting to "in" so every
    existing call site (which never passed this) keeps working
    unchanged. Reuses the exact same country-code convention already
    established in the main app's own COUNTRY_CODE_MAP (frontend
    App.jsx) for Thailand/Philippines/Vietnam/Indonesia, rather than
    inventing a separate one for this page."""
    if not LOCATIONIQ_API_KEY:
        raise HTTPException(status_code=503, detail="Address lookup isn't configured yet — LOCATIONIQ_API_KEY is not set.")
    if not q or len(q.strip()) < 3:
        return []
    try:
        resp = requests.get(
            f"{LOCATIONIQ_BASE}/autocomplete",
            params={"key": LOCATIONIQ_API_KEY, "q": q, "limit": 6, "countrycodes": country.lower(), "format": "json"},
            timeout=6,
        )
        if resp.status_code != 200:
            return []
        return resp.json()
    except requests.RequestException:
        return []


@app.get("/api/neighborhood-insights/nearby")
def neighborhood_nearby(lat: float, lon: float, tag: str, radius: int = 2000):
    """Proxies LocationIQ's /nearby endpoint for the Neighborhood
    Insights POI map. `tag` is an OSM-style "key:value" string (e.g.
    "amenity:hospital"), same format LocationIQ's own API and
    AccidentIQ's real POI_CATEGORIES use. Public (no auth), same
    reasoning as autocomplete above.

    Cached by rounded coordinates for 7 days — a real, deliberate cost
    fix: this endpoint fires 7 times per single form submission (once
    per POI category, uncached before this), making it by far the
    dominant driver of LocationIQ usage at any real scale — verified
    directly against LocationIQ's own published pricing, where this one
    endpoint's call volume alone determines which paid tier is needed.
    Coordinates are rounded to 2 decimal places (~1.1km grid cells at
    this latitude range) before building the cache key, so two
    addresses within the same ~1km neighborhood share one cached
    result — a reasonable trade-off given the search radius itself is
    already 2km, meaning two points that close together would very
    likely see near-identical nearby amenities anyway. 7-day TTL (much
    longer than infrastructure's 24h) because real-world hospitals/
    schools/banks don't meaningfully change day to day the way news
    does."""
    if not LOCATIONIQ_API_KEY:
        raise HTTPException(status_code=503, detail="Nearby-places lookup isn't configured yet — LOCATIONIQ_API_KEY is not set.")

    cache_key = f"nearby_{round(lat, 2)}_{round(lon, 2)}_{tag}_{radius}"
    cached = _get_cached_json(cache_key, ttl_hours=168)
    if cached is not None:
        return cached

    try:
        resp = requests.get(
            f"{LOCATIONIQ_BASE}/nearby",
            params={"key": LOCATIONIQ_API_KEY, "lat": lat, "lon": lon, "tag": tag, "radius": radius, "format": "json"},
            timeout=6,
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        result = data if isinstance(data, list) else []
    except requests.RequestException:
        return []

    if result:
        # Only cache a genuine, non-empty result — caching an empty
        # list (a transient LocationIQ hiccup, a rate limit, etc) would
        # mean a real neighborhood incorrectly shows "nothing found"
        # for a full week.
        _set_cached_json(cache_key, result)
    return result


@app.get("/api/neighborhood-insights/infrastructure")
def neighborhood_infrastructure(city: str, country: str = "India"):
    """Search-grounded (real web search, not a plain guess) summary of
    upcoming infrastructure for the Neighborhood Insights page. Public
    (no auth), same reasoning as the other neighborhood-insights
    endpoints — a free, no-signup entry point. See
    neighborhood_infrastructure.py's own module docstring for the
    critical honesty boundary: city-level general news, not verified
    proximity to a specific address, always shown with real sources
    and an explicit disclaimer.

    `country` is the real, full country name (e.g. "Thailand"), used
    directly in the search query — defaults to "India" so every
    existing call site keeps working unchanged."""
    return get_infrastructure_summary(city, country)


NI_SECTIONS = ["map", "flood_risk", "infrastructure", "resale_signal", "checklist", "authority_contacts", "cross_sell", "share"]
NI_VISIBILITY_SETTING_KEY = "ni_section_visibility"


def get_ni_section_visibility() -> dict[str, bool]:
    """All sections default to visible until an admin explicitly hides
    one — a fresh install or a section added after this feature shipped
    must never silently disappear just because it isn't in the saved
    config yet."""
    raw = get_app_setting(NI_VISIBILITY_SETTING_KEY)
    saved = {}
    if raw:
        try:
            saved = json.loads(raw)
        except json.JSONDecodeError:
            saved = {}
    return {section: saved.get(section, True) for section in NI_SECTIONS}


@app.get("/api/neighborhood-insights/section-visibility")
def neighborhood_section_visibility():
    """Public: which Neighborhood Insights sections should currently
    render. Lets the whole page's section set be controlled from the
    admin panel without a redeploy — e.g. temporarily hiding
    Infrastructure while a quota issue is being sorted out, without
    needing a code change for something that's really an operational,
    not a code, decision."""
    return get_ni_section_visibility()


@app.get("/api/neighborhood-insights/resale-signal")
def neighborhood_resale_signal(city: str, property_type: str = "Apartment") -> NeighborhoodResaleSignalResponse:
    """Powers the Neighborhood Insights page's "resale liquidity" card —
    a genuinely real signal (how many comparable projects/listings exist
    for this city+property type, and their average price/sqft), reusing
    comparables.py's own existing data rather than fabricating anything
    new. Deliberately public (no auth), same reasoning as instant_score
    just below: a free, no-signup entry point, not a gated feature.

    Honestly reports has_data=False (rather than a fabricated zero or a
    misleading empty success) for any city/property-type combination
    comparables.py doesn't actually cover — this app has real data for
    a genuine subset of cities, not all of them, and the caller must be
    able to tell the difference."""
    comps = get_comparables(city, property_type)
    if not comps:
        return NeighborhoodResaleSignalResponse(
            has_data=False, comparable_count=0, average_price_per_sqft=0, currency="INR", data_source="none",
        )
    is_live = len(comps) == 1 and comps[0].developer == "Live market data"
    return NeighborhoodResaleSignalResponse(
        has_data=True,
        comparable_count=len(comps),
        average_price_per_sqft=average_price_per_sqft(comps),
        currency="INR",
        data_source="live" if is_live else "static_snapshot",
    )


@app.post("/api/instant-score")
def instant_score(request: InstantScoreRequest):
    """PropertyIQ Instant Property Score — a free, no-signup, price +
    location + area-only quick score. Deliberately public/unauthenticated
    (no Depends(get_current_user_email)) — unlike every other feature in
    this app, this one is explicitly meant to work with zero account
    needed, matching its role as a lightweight funnel into the full
    assessment, not a gated feature of its own.

    Honestly returns coverage="unsupported" (no fabricated score) for any
    city/property_type combination without real comparable data — see
    compute_instant_score's own docstring for why."""
    if request.price <= 0 or request.area_value <= 0:
        raise HTTPException(status_code=400, detail="Price and area must both be greater than zero.")
    if request.area_unit not in ("sqft", "sqm"):
        raise HTTPException(status_code=400, detail="area_unit must be 'sqft' or 'sqm'.")
    if not request.city or not request.city.strip():
        raise HTTPException(status_code=400, detail="City is required.")
    if not request.property_type or not request.property_type.strip():
        raise HTTPException(status_code=400, detail="Property type is required.")

    return compute_instant_score(
        price=request.price,
        city=request.city,
        property_type=request.property_type,
        area_value=request.area_value,
        area_unit=request.area_unit,
        location=request.location,
    )


@app.post("/api/hidden-deal")
def hidden_deal(request: InstantScoreRequest):
    """PropertyIQ "Hidden Deal" — reuses the exact same real, honest
    price-vs-comparables logic as Instant Property Score (via
    find_hidden_deal_insights, which calls compute_instant_score
    internally), so the two features can never disagree about the same
    property's market position. Also public/unauthenticated, matching
    Instant Property Score's own no-signup design. The staged, one-at-a-
    time reveal described in the feature spec is a frontend presentation
    concern — this endpoint returns the full, real result at once."""
    if request.price <= 0 or request.area_value <= 0:
        raise HTTPException(status_code=400, detail="Price and area must both be greater than zero.")
    if request.area_unit not in ("sqft", "sqm"):
        raise HTTPException(status_code=400, detail="area_unit must be 'sqft' or 'sqm'.")
    if not request.city or not request.city.strip():
        raise HTTPException(status_code=400, detail="City is required.")
    if not request.property_type or not request.property_type.strip():
        raise HTTPException(status_code=400, detail="Property type is required.")

    return find_hidden_deal_insights(
        price=request.price,
        city=request.city,
        property_type=request.property_type,
        area_value=request.area_value,
        area_unit=request.area_unit,
        location=request.location,
    )


class RedFlagGuessRequest(BaseModel):
    price: float
    city: str
    property_type: str
    area_value: float
    area_unit: str = "sqft"
    guessed_category: str
    location: Optional[str] = None


@app.post("/api/red-flag-hunt")
def red_flag_hunt(request: RedFlagGuessRequest):
    """PropertyIQ "Red Flag Hunt" — an interactive quiz: the user guesses
    which category (Price/Area/Builder/Location/Amenities/Other) is most
    suspicious about a property, and gets an honest verdict. Reuses the
    same real price-vs-comparables logic as Instant Property Score and
    Hidden Deal (via evaluate_red_flag_guess -> compute_instant_score) —
    Price/Area guesses are judged against real data; Builder/Location/
    Amenities/Other honestly get a "this quick check can't verify that"
    verdict rather than a fabricated judgment. Public/unauthenticated,
    matching the other two quick-check features."""
    if request.price <= 0 or request.area_value <= 0:
        raise HTTPException(status_code=400, detail="Price and area must both be greater than zero.")
    if request.area_unit not in ("sqft", "sqm"):
        raise HTTPException(status_code=400, detail="area_unit must be 'sqft' or 'sqm'.")
    if not request.city or not request.city.strip():
        raise HTTPException(status_code=400, detail="City is required.")
    if not request.property_type or not request.property_type.strip():
        raise HTTPException(status_code=400, detail="Property type is required.")
    if request.guessed_category not in VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"guessed_category must be one of {VALID_CATEGORIES}.")

    return evaluate_red_flag_guess(
        price=request.price,
        city=request.city,
        property_type=request.property_type,
        area_value=request.area_value,
        area_unit=request.area_unit,
        guessed_category=request.guessed_category,
        location=request.location,
    )


class CreateChallengeRequest(BaseModel):
    price: float
    city: str
    property_type: str
    area_value: float
    area_unit: str = "sqft"
    location: Optional[str] = None


class ChallengeGuessRequest(BaseModel):
    guessed_price: float


@app.post("/api/challenges")
def api_create_challenge(request: CreateChallengeRequest):
    """PropertyIQ "Should I Buy This?" Challenge — creates a shareable,
    persistent challenge. Genuinely new infrastructure compared to the
    other quick-check features: this one needs a real database record,
    since a challenge must stay viewable via a stable link long after
    creation, to however many different recipients open it. Public, no
    account required, matching the feature's own explicit design."""
    try:
        return create_challenge(
            price=request.price, city=request.city, property_type=request.property_type,
            area_value=request.area_value, area_unit=request.area_unit, location=request.location,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/challenges/{challenge_id}")
def api_get_challenge(challenge_id: str):
    """Public — anyone with the link can view a challenge's property
    details, no account needed, matching the feature's "no account
    required for the initial prediction" design."""
    challenge = get_challenge(challenge_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="This challenge doesn't exist or may have expired.")
    return challenge


@app.post("/api/challenges/{challenge_id}/guess")
def api_reveal_challenge_guess(challenge_id: str, request: ChallengeGuessRequest):
    """Reveals how a recipient's guess compares to PropertyIQ's real fair
    value — reuses the exact same comparables-backed logic as Instant
    Score and Hidden Deal (see reveal_challenge_guess's own docstring),
    so a challenge reveal can never disagree with what those other two
    features would say about the same property. Public, no account."""
    try:
        return reveal_challenge_guess(challenge_id, request.guessed_price)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "No challenge found" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc


class CreatePriceWatchRequest(BaseModel):
    target_price: float
    area_unit: str = "sqft"
    url: Optional[str] = None
    # Required only when url is not provided (manual entry mode) — when
    # a URL is given, the real current price/city/type/area are
    # extracted from the listing itself, not guessed by the frontend.
    price: Optional[float] = None
    city: Optional[str] = None
    property_type: Optional[str] = None
    area_value: Optional[float] = None
    # Context/display only, same as every other quick-check feature —
    # not (yet) fed into the comparables-based scoring, which is
    # city-level. In URL mode, if not given manually, this is extracted
    # from the listing itself (property_url_import already extracts
    # location alongside city/type/area) — same pattern as those fields.
    location: Optional[str] = None


class UpdateWatchPriceRequest(BaseModel):
    new_price: float


@app.post("/api/price-watches")
def api_create_price_watch(request: CreatePriceWatchRequest, user_email: str = Depends(get_current_user_email)):
    """PropertyIQ "Price Drop Alert" — creates a watch. Gated by
    has_feature (price_drop_alert) like every other tier feature, the
    same enforcement point admin-toggling already controls — a real,
    explicit shift from this feature's earlier public/no-account design,
    made necessary by the per-tier watch-count limit below, which can
    only be meaningful if a watch is tied to a real signed-in account
    rather than an arbitrary email string anyone could vary to bypass
    it. Notifications go to this same authenticated email, not a
    separate user-supplied one. Honest distinction the frontend must
    surface clearly: a watch created with a URL gets genuinely,
    automatically re-checked in the background every few hours (see
    price_watch_scheduler.py); one created from manual price entry has
    no source to re-fetch from, so its price only ever changes when the
    user comes back and calls the update endpoint below themselves.

    A real design fix, caught before shipping: when a URL is given, its
    real current price/city/type/area are extracted from the listing
    itself right here — the frontend never needs to guess or send
    placeholder values for fields a URL-based watch will genuinely learn
    from the page itself."""
    tier_id = get_active_tier(user_email)
    if not has_feature(tier_id, "price_drop_alert"):
        raise HTTPException(
            status_code=403,
            detail="Price Drop Alert requires an active Studio subscription that includes this feature."
        )

    tier = get_tier(tier_id)
    max_watches = tier.get("max_price_watches") if tier else None
    if max_watches is not None:
        current_count = count_active_watches_for_email(user_email)
        if current_count >= max_watches:
            raise HTTPException(
                status_code=403,
                detail=f"Your plan allows watching up to {max_watches} propert{'y' if max_watches == 1 else 'ies'} "
                       f"at a time. You're already watching {current_count} — cancel one or upgrade your plan "
                       f"to watch more."
            )

    price = request.price
    city = request.city
    property_type = request.property_type
    area_value = request.area_value
    location = request.location

    if request.url:
        try:
            extracted = extract_property_data(request.url)
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Couldn't read that listing to set up the watch: {exc}"
            ) from exc

        if extracted.get("quotedPrice"):
            price = extracted["quotedPrice"]
        if extracted.get("city"):
            city = extracted["city"]
        if extracted.get("propertyType"):
            property_type = extracted["propertyType"]
        if extracted.get("areaValue"):
            area_value = extracted["areaValue"]
            if extracted.get("areaUnit"):
                request.area_unit = extracted["areaUnit"]
        if location is None and extracted.get("location"):
            location = extracted["location"]

        if price is None:
            raise HTTPException(
                status_code=422,
                detail="Couldn't determine this listing's current price — please enter it "
                       "manually instead, or try a different listing."
            )
        # Context fields (city/type/area) are nice-to-have for display,
        # not required for the watch's core purpose (price vs target) —
        # reasonable defaults if the extraction genuinely found nothing.
        city = city or "Unknown"
        property_type = property_type or "Apartment"
        area_value = area_value or 1

    elif price is None or city is None or property_type is None or area_value is None:
        raise HTTPException(
            status_code=400,
            detail="Please provide a listing URL, or price/city/property_type/area_value manually."
        )

    try:
        return create_price_watch(
            email=user_email, price=price, city=city,
            property_type=property_type, area_value=area_value,
            target_price=request.target_price, area_unit=request.area_unit, url=request.url,
            location=location,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/price-watches/{watch_id}")
def api_get_price_watch(watch_id: str):
    """Public — lets the creator check on their watch's status via the
    link, no account needed."""
    watch = get_price_watch(watch_id)
    if watch is None:
        raise HTTPException(status_code=404, detail="This price watch doesn't exist.")
    return watch


@app.post("/api/price-watches/{watch_id}/update-price")
def api_update_watch_price(watch_id: str, request: UpdateWatchPriceRequest):
    """The only way a manual-entry (no-URL) watch's price can ever
    change — see create_price_watch's own docstring for why."""
    try:
        return update_watch_price(watch_id, request.new_price)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "No price watch found" in detail else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc


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
    labor_selections: dict[str, str] = {}
    region: str = "global"
    currency: str = "USD"


class RoomSpec(BaseModel):
    name: str
    x: float
    y: float
    length: float
    width: float
    color: Optional[str] = None  # "#rrggbb" — carried through to the real DXF export


# Site elements are landscaping/hardscape/site furnishings — distinct from
# rooms (never subject to Vastu checks, never counted in cost estimates or
# quota, never shown in the Materials/Room-list steps). "line"/"dotted_line"
# use (x, y) as one endpoint and (x2, y2) as the other; every other type
# uses (x, y, length, width) as a bounding box, same convention as rooms.
class SiteElementSpec(BaseModel):
    type: str  # tree | gazebo | pool | car | plant | pathway | bench | line | dotted_line
    x: float
    y: float
    length: Optional[float] = None
    width: Optional[float] = None
    x2: Optional[float] = None
    y2: Optional[float] = None
    color: Optional[str] = None
    rotation: float = 0  # degrees, rotates around the element's top-left corner —
    # matches the frontend canvas's pivot convention. Rooms stay unrotated
    # (Vastu zone math + DXF room export both assume axis-aligned rectangles).
    dash_style: Optional[str] = None  # solid | dotted | dash | dash-dot — lines only
    stroke_width: Optional[float] = None  # line thickness in ft — lines only


class MasterPlanElementSpec(BaseModel):
    type: str  # water_body | forest | mountain | open_space | main_road | religious_structure
    direction: str  # north | north-east | east | south-east | south | south-west | west | north-west


class ConstructionDesignRequest(BaseModel):
    plot_size_sqft: float
    plot_length_ft: float
    plot_width_ft: float
    selections: dict[str, str]
    labor_selections: dict[str, str] = {}
    region: str = "global"
    currency: str = "USD"
    entrance_direction: str
    road_facing_side: str
    slope_direction: Optional[str] = None
    master_plan_elements: list[MasterPlanElementSpec] = []
    rooms: list[RoomSpec] = []
    site_elements: list[SiteElementSpec] = []
    has_imported_materials: bool = False
    city: Optional[str] = None
    country: Optional[str] = None
    unit_system: Optional[str] = None


@app.get("/api/construction-studio/materials")
def construction_materials(region: str = "global", user_email: str = Depends(get_current_user_email)):
    """Available material/supplier options for a region, plus separate
    contractor/labor options (RCC work, brickwork, plasterwork — India
    only for now). Base costs are in USD; convert client-side or via
    /estimate for a specific currency.

    Requires an active subscription — a real, confirmed gap this closes
    (this endpoint had no auth requirement at all before). The
    standard_suppliers vs premium_global_suppliers distinction is real,
    not cosmetic: standard-tier users see only their own region's real,
    researched catalog (as today); premium-tier users get every
    country's suppliers regardless of the region they're actually
    building in — e.g. an India-region user on Studio Pro can also see
    and select Thai, Vietnamese, Indonesian, or Philippine suppliers for
    an imported/alternative material, not just India's own options."""
    tier_id = get_active_tier(user_email)
    if has_feature(tier_id, "premium_global_suppliers"):
        effective_region = "global"
    elif has_feature(tier_id, "standard_suppliers"):
        effective_region = region
    else:
        raise HTTPException(
            status_code=403,
            detail="The materials catalog requires an active Studio subscription. "
                   "Subscribe via POST /api/subscribe/checkout first."
        )

    return {
        "region": effective_region,
        "categories": get_catalog(effective_region),
        "labor_categories": get_labor_catalog(effective_region),
    }


class DisciplineOverlayRequest(BaseModel):
    rooms: list[dict[str, Any]]
    plot_length_ft: float
    plot_width_ft: float
    total_floors: int = 1


@app.post("/api/construction-studio/discipline-overlay")
def discipline_overlay(request: DisciplineOverlayRequest, discipline: str):
    """Computes a schematic Structural/Plumbing/Electrical overlay drawn
    over the exact same room footprint as the live floor plan preview.
    Deliberately public (no auth) — this is a pure, stateless geometric
    computation over data the caller already has (their own current room
    layout), not a gated feature or anything specific to a saved design.

    See discipline_overlays.py's own module docstring for the critical
    honesty boundary this endpoint's response always carries: every
    result includes an explicit `disclaimer` field stating this is a
    schematic visualization aid, not a licensed engineer's calculated
    design — never omit or soften that disclaimer when displaying this.
    Every discrete element additionally carries a `spec` field with a
    published reference dimension (see discipline_overlays.py's own
    sourcing comment) — uniform per element type, never fabricated per
    specific element, and always paired with the same "not calculated
    for this building" qualifier as the top-level disclaimer.

    `total_floors` is the building's REAL total floor count (not just
    this one floor's row count) — it picks which published G+1/G+2/G+3
    reference column size to quote for the structural overlay; ignored
    for plumbing/electrical."""
    if request.plot_length_ft <= 0 or request.plot_width_ft <= 0:
        raise HTTPException(status_code=400, detail="plot_length_ft and plot_width_ft must both be greater than zero.")
    if request.total_floors <= 0:
        raise HTTPException(status_code=400, detail="total_floors must be greater than zero.")

    discipline = (discipline or "").strip().lower()
    if discipline == "structural":
        return compute_structural_overlay(request.rooms, request.plot_length_ft, request.plot_width_ft, request.total_floors)
    if discipline == "plumbing":
        return compute_plumbing_overlay(request.rooms, request.plot_length_ft, request.plot_width_ft)
    if discipline == "electrical":
        return compute_electrical_overlay(request.rooms, request.plot_length_ft, request.plot_width_ft)
    raise HTTPException(status_code=400, detail="discipline must be 'structural', 'plumbing', or 'electrical'.")


@app.get("/api/construction-studio/compliance-rules")
def compliance_rules(tradition: str):
    """Backs the Vastu/Thai compliance info icon — a plain-language
    listing of every rule the live check actually validates against.
    Deliberately public (no auth/subscription required): this is
    informational only, not a computed result specific to any user's
    design, so there's no reason to gate it the way the live checks
    themselves are gated by the Studio subscription."""
    tradition = (tradition or "").strip().lower()
    if tradition == "vastu":
        return get_vastu_rules()
    if tradition == "thai":
        return get_thai_rules()
    raise HTTPException(status_code=400, detail="tradition must be 'vastu' or 'thai'.")


@app.post("/api/construction-studio/estimate")
def construction_estimate(request: ConstructionEstimateRequest):
    """Live running cost total as the user picks materials/labor — call
    this on every selection change to update the on-screen total."""
    if request.plot_size_sqft <= 0:
        raise HTTPException(status_code=400, detail="plot_size_sqft must be greater than 0")

    return estimate_cost(
        plot_size_sqft=request.plot_size_sqft,
        selections=request.selections,
        labor_selections=request.labor_selections,
        region=request.region,
        currency=request.currency,
    )


@app.post("/api/construction-studio/bill-of-materials")
def construction_bom(request: ConstructionEstimateRequest):
    """A Bill of Materials — a procurement list (what to order, and how
    much), materials only, no labor or cost totals. Distinct from a Bill
    of Quantities (see below), matching the real-world distinction
    between the two document types."""
    if request.plot_size_sqft <= 0:
        raise HTTPException(status_code=400, detail="plot_size_sqft must be greater than 0")

    return generate_bill_of_materials(
        plot_size_sqft=request.plot_size_sqft,
        selections=request.selections,
        region=request.region,
    )


@app.post("/api/construction-studio/bill-of-quantities")
def construction_boq(request: ConstructionEstimateRequest):
    """A Bill of Quantities — the tender/contract-grade document: every
    work item, materials AND labor together, grouped by trade, with
    quantity, unit rate, and line total for each. Totals reconcile
    exactly with /estimate's numbers (same underlying calculation)."""
    if request.plot_size_sqft <= 0:
        raise HTTPException(status_code=400, detail="plot_size_sqft must be greater than 0")

    return generate_bill_of_quantities(
        plot_size_sqft=request.plot_size_sqft,
        selections=request.selections,
        labor_selections=request.labor_selections,
        region=request.region,
        currency=request.currency,
    )


class AdjacencyCheckRequest(BaseModel):
    rooms: list[RoomSpec]
    style: str = "modern_open_plan"


@app.post("/api/construction-studio/adjacency-check")
def construction_adjacency_check(request: AdjacencyCheckRequest):
    """Space-planning adjacency report for the Review step — a
    server-side confirmation of the same rules the canvas already
    evaluates live during drag (see the JS port in RoomCanvas.jsx).
    Kept in sync deliberately so the two never silently drift apart."""
    return evaluate_adjacency(
        rooms=[r.model_dump() for r in request.rooms],
        style=request.style,
    )


@app.get("/api/construction-studio/adjacency-styles")
def construction_adjacency_styles():
    """The selectable architectural styles for adjacency validation."""
    return {
        "styles": [
            {"id": "modern_open_plan", "label": "Modern / Open-Plan"},
            {"id": "minimalist", "label": "Minimalist"},
            {"id": "traditional_zoned", "label": "Traditional / Zoned"},
        ]
    }


class VastuCheckRequest(BaseModel):
    plot_length_ft: float
    plot_width_ft: float
    rooms: list[RoomSpec] = []
    entrance_direction: str
    road_facing_side: str
    slope_direction: Optional[str] = None
    country: Optional[str] = None  # routes to the Thai traditional engine when this is Thailand — see below
    region: Optional[str] = None  # fallback signal if country is missing/stale (e.g. an older saved design)


@app.post("/api/construction-studio/vastu-check")
def construction_vastu_check(request: VastuCheckRequest, user_email: str = Depends(get_current_user_email)):
    """A lightweight, quota-free traditional-building compliance check —
    recomputes from the CURRENT room layout, unlike the result embedded
    in a generated design (which is a snapshot from whenever "Generate"
    was last clicked and goes stale the moment the user edits a room
    afterward — a real reported bug: compliance kept showing an old
    result after a room was removed or rearranged). Does not consume
    design quota, generate a DXF, or save anything — purely a read of
    the current layout, meant to be called reactively as the user edits,
    the same role adjacency-check plays for space-planning correctness.

    Requires an active subscription with the vastu_compliance feature —
    a real, confirmed gap this closes: this endpoint had NO auth
    requirement at all before, meaning every subscription tier listed
    "Vastu Compliance" as a paid feature while it was actually available
    to anyone, logged in or not, on any tier or none.

    Routes by country OR region: Vastu for India (the original, still
    the default — including when country/region are unset entirely, for
    backward compatibility with designs saved before this field
    existed), the Thai traditional-building engine when either country
    or region is Thailand. Kept as the same endpoint/URL the frontend
    already calls (rather than a breaking rename).

    Treats country and region as equally valid triggers rather than
    having one override the other — a real bug this closes: an older
    saved design (or one loaded before country was correctly restored
    on the frontend) can have region="thailand" while country is stuck
    at a stale default like "india". An earlier version of this fix
    tried to let an explicit country="india" win over region, but that
    exact stale-default state IS the bug being fixed, so that "override"
    logic silently defeated the whole point of the fallback — caught by
    testing the exact reported scenario directly rather than assuming
    the fix worked.

    For a country that's explicitly set to something OTHER than India
    or Thailand (Philippines, Vietnam, Indonesia, or any other country
    added later without a real researched traditional-building system)
    — this deliberately does NOT fall back to Vastu. Showing "Vastu
    Compliance" for a Philippines property would be actively misleading,
    not just incomplete — Vastu is a real, specific Indian tradition,
    not a generic placeholder. Returns an explicit "no specific
    tradition researched yet" response instead, which the frontend uses
    to hide the section entirely rather than show something wrong.
    The universal, country-agnostic adjacency (space-planning) check is
    unaffected either way — it's a separate endpoint/section that
    already works for any country."""
    tier_id = get_active_tier(user_email)
    if not has_feature(tier_id, "vastu_compliance"):
        raise HTTPException(
            status_code=403,
            detail="Vastu/traditional-building compliance checking requires an active Studio "
                   "subscription that includes this feature. Subscribe via POST /api/subscribe/checkout first."
        )
    country = (request.country or "").strip().lower()
    region = (request.region or "").strip().lower()

    if country == "thailand" or region == "thailand":
        if request.rooms:
            return check_thai_traditional_full(
                rooms=[r.model_dump() for r in request.rooms],
                entrance_direction=request.entrance_direction,
                road_facing_side=request.road_facing_side,
            )
        return check_thai_orientation(
            entrance_direction=request.entrance_direction,
            road_facing_side=request.road_facing_side,
        )

    if country not in ("", "india") and region != "india":
        return {"scope": "no_specific_tradition", "compliant": True, "findings": [], "notes": []}

    if request.rooms:
        return check_vastu_full(
            plot_length_ft=request.plot_length_ft,
            plot_width_ft=request.plot_width_ft,
            rooms=[r.model_dump() for r in request.rooms],
            entrance_direction=request.entrance_direction,
            road_facing_side=request.road_facing_side,
            slope_direction=request.slope_direction,
        )
    return check_vastu_basics(
        entrance_direction=request.entrance_direction,
        road_facing_side=request.road_facing_side,
        slope_direction=request.slope_direction,
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
    quota = tier.get("design_quota_per_month", 0) if tier else 0
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
        labor_selections=request.labor_selections,
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
            site_elements=[e.model_dump() for e in request.site_elements],
            road_facing_side=request.road_facing_side,
            include_dimensions=has_feature(tier_id, "priority_cad_formats"),
        )
        dxf_path = str(generated_path)

    plot_spec = {
        "plot_size_sqft": request.plot_size_sqft,
        "plot_length_ft": request.plot_length_ft,
        "plot_width_ft": request.plot_width_ft,
        "entrance_direction": request.entrance_direction,
        "road_facing_side": request.road_facing_side,
        "slope_direction": request.slope_direction,
        "master_plan_elements": [e.model_dump() for e in request.master_plan_elements],
        "rooms": [r.model_dump() for r in request.rooms],
        "site_elements": [e.model_dump() for e in request.site_elements],
        "selections": request.selections,
        "labor_selections": request.labor_selections,
        "city": request.city,
        "country": request.country,
        "unit_system": request.unit_system,
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
        "discipline_breakdown": group_by_discipline(cost_estimate["line_items"]),
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


class ConstructionReportRequest(BaseModel):
    floors: list[dict[str, Any]]
    property_name: str = ""


@app.post("/api/construction-studio/design/{design_id}/report")
def download_construction_report(design_id: str, request: ConstructionReportRequest):
    """Generates and returns the complete PDF report for a saved design
    (plot summary, room layout, cost by discipline, compliance, and
    Structural/Plumbing/Electrical schematics with legends and specs
    for every floor). `floors` is required in the request body — room
    layout isn't persisted with the saved design record itself (see
    construction_store.py's own schema), so the caller supplies it
    directly from what it already has in memory, same pattern as the
    stateless discipline-overlay endpoint above.

    Deliberately does not require auth beyond a design existing: the
    design itself was already created by an authenticated, tier-gated
    request, and this endpoint only re-renders that already-computed
    result as a PDF — no new computation a free-riding caller could
    exploit, same reasoning as the existing DXF download endpoint just
    above having no separate auth check either."""
    design = get_design(design_id)
    if design is None:
        raise HTTPException(status_code=404, detail="Design not found")
    if not request.floors:
        raise HTTPException(status_code=400, detail="floors must include at least one floor.")

    pdf_bytes = generate_construction_report_pdf(design, request.floors, request.property_name, design_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="PropertyIQ_ConstructionStudio_Report_{design_id}.pdf"'},
    )


class PropertyPlotSpec(BaseModel):
    plot_size_sqft: float
    plot_length_ft: float
    plot_width_ft: float
    region: str = "global"
    currency: str = "USD"
    entrance_direction: str
    road_facing_side: str
    slope_direction: Optional[str] = None
    master_plan_elements: list[MasterPlanElementSpec] = []
    city: Optional[str] = None
    country: Optional[str] = None
    unit_system: Optional[str] = None


class FloorInput(BaseModel):
    floor_number: int
    floor_label: str
    rooms: list[RoomSpec] = []


class CreatePropertyRequest(BaseModel):
    name: str
    plot_spec: PropertyPlotSpec
    selections: dict[str, str] = {}
    labor_selections: dict[str, str] = {}
    site_elements: list[SiteElementSpec] = []
    floors: list[FloorInput] = []
    supplier_preferences: dict[str, list[str]] = {}


class UpdatePropertyRequest(BaseModel):
    name: Optional[str] = None
    plot_spec: Optional[PropertyPlotSpec] = None
    selections: Optional[dict[str, str]] = None
    labor_selections: Optional[dict[str, str]] = None
    site_elements: Optional[list[SiteElementSpec]] = None
    supplier_preferences: Optional[dict[str, list[str]]] = None


class ShareRequest(BaseModel):
    emails: list[str]


class UpsertFloorRequest(BaseModel):
    floor_id: Optional[str] = None
    floor_number: int
    floor_label: str
    rooms: list[RoomSpec] = []


class SyncPropertyRequest(BaseModel):
    """Saves everything — property fields and the complete floor set — in
    one request. Preferred over the individual update/floors endpoints
    for the Studio's Save button specifically: one HTTP round-trip instead
    of 2+N, and floors omitted here are actually deleted server-side
    (the old per-floor-upsert flow never did, so a locally-removed floor
    would silently reappear on next load)."""
    name: Optional[str] = None
    plot_spec: Optional[PropertyPlotSpec] = None
    selections: Optional[dict[str, str]] = None
    labor_selections: Optional[dict[str, str]] = None
    site_elements: Optional[list[SiteElementSpec]] = None
    supplier_preferences: Optional[dict[str, list[str]]] = None
    floors: list[UpsertFloorRequest]


class ConfirmUnlockRequest(BaseModel):
    code: str


def _require_own_property(property_id: str, user_email: str) -> dict[str, Any]:
    """Allows access to the owner AND anyone the owner has explicitly
    shared this property with (the team_seats feature) — most
    operations (view, edit, sync, lock/unlock) are genuinely
    collaborative. Deleting the property or changing who it's shared
    with stays owner-only (see _require_property_owner below), since
    those are account-level decisions, not collaborative editing."""
    prop = get_property(property_id)
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")
    requester = user_email.strip().lower()
    if prop["user_email"] == requester:
        return prop
    if requester in prop.get("shared_with_emails", []):
        return prop
    raise HTTPException(status_code=403, detail="This property belongs to a different account")


def _require_property_owner(property_id: str, user_email: str) -> dict[str, Any]:
    """Stricter than _require_own_property — only the actual owner, never
    a shared/team_seats collaborator. Used for deleting a property and
    for managing who it's shared with, since those are account-level
    decisions a collaborator shouldn't be able to make."""
    prop = get_property(property_id)
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")
    if prop["user_email"] != user_email.strip().lower():
        raise HTTPException(status_code=403, detail="Only the property's owner can do this")
    return prop


@app.post("/api/properties")
def api_create_property(request: CreatePropertyRequest, user_email: str = Depends(get_current_user_email)):
    """Save a new multi-floor property design. Gated by the tier's
    saved_designs_limit (admin-configurable — separate from
    design_quota_per_month, which limits how many times you can GENERATE
    a design, not how many you can keep saved)."""

    tier_id = get_active_tier(user_email)
    if not tier_id:
        raise HTTPException(status_code=403, detail="Saving designs requires an active Studio subscription.")

    tier = get_tier(tier_id)
    limit = tier.get("saved_designs_limit", 0) if tier else 0
    if limit is not None:
        used = count_saved_properties(user_email)
        if used >= limit:
            raise HTTPException(
                status_code=403,
                detail=f"Saved design limit reached ({used}/{limit}) for the {tier['label']} tier. "
                       f"Delete an existing saved design or upgrade your plan."
            )

    if not request.floors:
        raise HTTPException(status_code=400, detail="A property must have at least one floor")

    prop = create_property(
        user_email=user_email,
        name=request.name,
        plot_spec=request.plot_spec.model_dump(),
        selections=request.selections,
        labor_selections=request.labor_selections,
        site_elements=[e.model_dump() for e in request.site_elements],
        floors=[f.model_dump() for f in request.floors],
        supplier_preferences=request.supplier_preferences,
    )
    return prop


@app.get("/api/properties")
def api_list_properties(user_email: str = Depends(get_current_user_email)):
    """Summary list for the Studio landing page's saved-designs picker."""
    return {"properties": list_properties_for_user(user_email)}


@app.get("/api/properties/shared-with-me")
def api_list_shared_properties(user_email: str = Depends(get_current_user_email)):
    """Designs someone else owns but has shared with this account —
    shown as a separate section from the user's own saved designs list,
    same summary shape plus which account actually owns each one.
    Registered BEFORE /api/properties/{property_id} deliberately —
    FastAPI matches routes in registration order, and the generic
    {property_id} route would otherwise swallow this literal path,
    treating "shared-with-me" as a property ID and returning 404."""
    return {"properties": list_properties_shared_with_user(user_email)}


@app.get("/api/properties/{property_id}")
def api_get_property(property_id: str, user_email: str = Depends(get_current_user_email)):
    return _require_own_property(property_id, user_email)


@app.put("/api/properties/{property_id}")
def api_update_property(property_id: str, request: UpdatePropertyRequest, user_email: str = Depends(get_current_user_email)):
    _require_own_property(property_id, user_email)
    try:
        updated = update_property(
            property_id=property_id,
            name=request.name,
            plot_spec=request.plot_spec.model_dump() if request.plot_spec else None,
            selections=request.selections,
            labor_selections=request.labor_selections,
            site_elements=[e.model_dump() for e in request.site_elements] if request.site_elements is not None else None,
            supplier_preferences=request.supplier_preferences,
        )
    except PermissionError:
        raise HTTPException(status_code=423, detail="This property is locked. Unlock it first to make changes.")
    return updated


@app.put("/api/properties/{property_id}/floors")
def api_upsert_floor(property_id: str, request: UpsertFloorRequest, user_email: str = Depends(get_current_user_email)):
    _require_own_property(property_id, user_email)
    try:
        updated = upsert_floor(
            property_id=property_id,
            floor_id=request.floor_id,
            floor_number=request.floor_number,
            floor_label=request.floor_label,
            rooms=[r.model_dump() for r in request.rooms],
        )
    except PermissionError:
        raise HTTPException(status_code=423, detail="This property is locked. Unlock it first to make changes.")
    return updated


@app.put("/api/properties/{property_id}/sync")
def api_sync_property(property_id: str, request: SyncPropertyRequest, user_email: str = Depends(get_current_user_email)):
    """One-request save for the Studio's Save button — property fields
    plus the complete floor set (floors omitted here are deleted, not
    just left untouched). Preferred over calling update + floors
    individually per floor."""
    _require_own_property(property_id, user_email)
    try:
        updated = sync_property(
            property_id=property_id,
            name=request.name,
            plot_spec=request.plot_spec.model_dump() if request.plot_spec else None,
            selections=request.selections,
            labor_selections=request.labor_selections,
            site_elements=[e.model_dump() for e in request.site_elements] if request.site_elements is not None else None,
            supplier_preferences=request.supplier_preferences,
            floors=[f.model_dump() for f in request.floors],
        )
    except PermissionError:
        raise HTTPException(status_code=423, detail="This property is locked. Unlock it first to make changes.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return updated


@app.delete("/api/properties/{property_id}/floors/{floor_id}")
def api_delete_floor(property_id: str, floor_id: str, user_email: str = Depends(get_current_user_email)):
    _require_own_property(property_id, user_email)
    try:
        delete_floor(property_id=property_id, floor_id=floor_id)
    except PermissionError:
        raise HTTPException(status_code=423, detail="This property is locked. Unlock it first to make changes.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return get_property(property_id)


@app.post("/api/properties/{property_id}/lock")
def api_lock_property(property_id: str, user_email: str = Depends(get_current_user_email)):
    """Locking is immediate — protecting your own work never needs extra
    verification. Only UNLOCKING requires the OTP round-trip below."""
    _require_own_property(property_id, user_email)
    return set_locked(property_id=property_id, locked=True)


@app.post("/api/properties/{property_id}/request-unlock")
def api_request_unlock(property_id: str, user_email: str = Depends(get_current_user_email)):
    """Sends a fresh email OTP that must be confirmed before the property
    actually unlocks. Being signed in is deliberately NOT sufficient on
    its own — an already-open session isn't treated as authorization to
    unlock a design someone locked on purpose."""
    _require_own_property(property_id, user_email)
    code = create_otp(user_email)
    send_otp_email(user_email, code, purpose="unlock_design")
    return {"sent": True}


@app.post("/api/properties/{property_id}/confirm-unlock")
def api_confirm_unlock(property_id: str, request: ConfirmUnlockRequest, user_email: str = Depends(get_current_user_email)):
    _require_own_property(property_id, user_email)
    if not verify_otp(user_email, request.code):
        raise HTTPException(status_code=401, detail="Incorrect or expired code.")
    return set_locked(property_id=property_id, locked=False)


@app.delete("/api/properties/{property_id}")
def api_delete_property(property_id: str, user_email: str = Depends(get_current_user_email)):
    prop = _require_property_owner(property_id, user_email)
    if prop["locked"]:
        raise HTTPException(status_code=423, detail="This property is locked. Unlock it first to delete it.")
    delete_property(property_id)
    return {"deleted": True}


@app.post("/api/properties/{property_id}/share")
def api_share_property(property_id: str, request: ShareRequest, user_email: str = Depends(get_current_user_email)):
    """Backs the team_seats tier feature: the owner can give up to
    MAX_SHARED_EMAILS_PER_PROPERTY teammates full collaborative access
    (view/edit/sync/lock) to this one property — not full account
    access, and not transferable to other properties on its own; each
    property is shared individually. Owner-only, and requires the
    owner's active subscription to include team_seats — a shared
    collaborator doesn't need their own subscription to use a design
    shared with them, matching how a real team seat works."""
    prop = _require_property_owner(property_id, user_email)
    tier_id = get_active_tier(user_email)
    if not has_feature(tier_id, "team_seats"):
        raise HTTPException(
            status_code=403,
            detail="Sharing a design with teammates requires an active Studio subscription "
                   "that includes the team_seats feature."
        )
    try:
        updated = set_shared_with_emails(property_id, user_email, request.emails)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return updated


@app.get("/")
def health():
    return {
        "service": "PropertyIQ API",
        "version": "1.0.0-beta",
        "status": "healthy"
    }    