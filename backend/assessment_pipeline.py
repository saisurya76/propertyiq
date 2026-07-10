from dataclasses import dataclass
from typing import Optional

from backend.government_intelligence import (
    assess_government_intelligence
)

from backend.negotiation_intelligence import (
    assess_negotiation_position
)

from backend.recommendation_confidence import (
    assess_recommendation_confidence
)

from backend.decision_intelligence import (
    generate_decision
)

from backend.comparables import (
    get_comparables,
    average_price_per_sqft
)

from backend.valuation_models import (
    comparable_sales_value,
    rental_yield_value,
    replacement_cost_value,
    weighted_fair_value
)

from backend.unit_conversion import (
    to_sqft
)

from backend.inventory import (
    assess_inventory_risk
)

from backend.developer import (
    assess_developer
)

from backend.deal_quality import (
    get_deal_quality
)

from backend.recommendation import (
    calculate_overpricing_percent,
    get_recommendation
)

from backend.scoring import (
    valuation_score,
    inventory_score
)

from backend.buyer_protection import (
    calculate_buyer_protection_score
)

from backend.buyer_advantage import (
    assess_buyer_advantage
)

from backend.findings import (
    generate_findings
)

from backend.assessment import (
    create_assessment
)

from backend.fraud_intelligence.engine import (
    generate_fraud_report
)

from backend.unit_rate_conversion import (
    to_rate_per_sqft
)

@dataclass
class PropertyInput:
    country: str
    state_province: str
    city: str
    locality: str

    property_type: str

    property_name: str
    developer_name: str

    quoted_price: float
    currency: str

    government_guidance: float
    market_average: float

    unit_area: float
    area_unit: str

    monthly_rent: float

    total_units: Optional[int]
    unsold_units: Optional[int]

    projects_completed: Optional[int]
    projects_delayed: Optional[int]
    years_in_business: Optional[int]
    rera_violations: Optional[int]


def run_assessment(
    property_input: PropertyInput
):

    # Normalize Area

    normalized_area = to_sqft(
        property_input.unit_area,
        property_input.area_unit
    )

    normalized_government_rate = to_rate_per_sqft(
        property_input.government_guidance,
        property_input.area_unit
    )

    normalized_market_rate = to_rate_per_sqft(
        property_input.market_average,
        property_input.area_unit
    )

    quoted_price_per_sqft = (
        property_input.quoted_price /
        normalized_area
    )

    fair_value_per_sqft = 0.0

    # Market Intelligence

    comparables = get_comparables(
    property_input.city
    )

    market_average_price_per_sqft = (
        average_price_per_sqft(
            comparables
        )
    )

    # Comparable Sales Value

    comparable_value = comparable_sales_value(
        normalized_area,
        [normalized_market_rate]
    )

    # Rental Yield Value

    if property_input.monthly_rent > 0:

        rental_value = rental_yield_value(
            property_input.monthly_rent,
            4.0
        )

    else:

        rental_value = 0.0

    # Replacement Cost Value

    replacement_value = 0.0

    # Weighted Fair Value

    fair_value = weighted_fair_value(
        comparable_value=comparable_value,
        rental_value=rental_value,
        replacement_value=replacement_value
    )

    fair_value_per_sqft = (
        fair_value /
        normalized_area
    )

    # Overpricing

    overpricing = calculate_overpricing_percent(
        property_input.quoted_price,
        fair_value
    )

    # Inventory Assessment

    if (
        property_input.total_units is not None and
        property_input.unsold_units is not None
    ):
        inventory = assess_inventory_risk(
            property_input.total_units,
            property_input.unsold_units
        )
    else:
        inventory = None

    # Developer Assessment

    if all(
        value is not None
        for value in [
            property_input.projects_completed,
            property_input.projects_delayed,
            property_input.years_in_business,
            property_input.rera_violations
        ]
    ):
        developer = assess_developer(
            property_input.projects_completed,
            property_input.projects_delayed,
            property_input.years_in_business,
            property_input.rera_violations
        )
    else:
        developer = None

    inventory_risk = (
        inventory.risk_level
        if inventory is not None
        else "NOT_ASSESSED"
    )

    inventory_score_value = (
        inventory_score(inventory_risk)
        if inventory is not None
        else None
    )

    developer_rating = (
        developer.rating
        if developer is not None
        else "NOT_ASSESSED"
    )

    developer_score = (
        developer.score
        if developer is not None
        else None
    )

    inventory_score_output = (
        inventory_score_value
        if inventory_score_value is not None
        else 0.0
    )

    developer_score_output = (
        developer_score
        if developer_score is not None
        else 0.0
    )

    # Component Scores

    valuation_score_value = valuation_score(
        overpricing
    )

    # Buyer Protection Score

    bps = calculate_buyer_protection_score(
        valuation_score=valuation_score_value,
        inventory_score=inventory_score_value,
        developer_score=developer_score
    )

    # Recommendation

    recommendation = get_recommendation(
        overpricing_percent=overpricing,
        inventory_risk=inventory_risk,
        developer_rating=developer_rating,
        buyer_protection_score=bps.score
    )

    # Deal Quality

    deal_quality, deal_quality_reason = (
        get_deal_quality(
            overpricing_percent=overpricing,
            buyer_protection_score=bps.score
        )
    )

    # Negotiation Intelligence

    negotiation = (
        assess_negotiation_position(
            quoted_price=
                property_input.quoted_price,

            fair_value=
                fair_value,

            inventory_risk=
                inventory_risk
        )
    )

    # Buyer Advantage

    buyer_advantage = assess_buyer_advantage(
        overpricing_percent=overpricing,
        inventory_risk=inventory_risk,
        negotiation_position=negotiation.position,
        buyer_protection_score=bps.score
    )

    # Recommendation Confidence

    recommendation_confidence = (
        assess_recommendation_confidence(
            buyer_protection_score=bps.score,
            developer_score=developer_score,
            inventory_score=inventory_score_value,
            valuation_score=valuation_score_value
        )
    )

    government_intelligence = (
        assess_government_intelligence(
            country=property_input.country,

            state_province=
                property_input.state_province,

            city=
                property_input.city,

            property_type=
                property_input.property_type,

            unit_area=
                normalized_area,

            government_rate=
                normalized_government_rate
        )
    )

    #fraud_intelligence
    fraud_intelligence = (
        generate_fraud_report(
            country=property_input.country,
            state=property_input.state_province,
            city=property_input.city,
            locality=property_input.locality
        )
    )

    # Findings

    findings = generate_findings(
        overpricing_percent=overpricing,
        inventory_risk=inventory_risk,
        developer_rating=developer_rating,
        recommendation=recommendation
    )

    # Decision

    decision = generate_decision(
        recommendation=recommendation,
        buyer_protection_score=bps.score,
        overpricing_percent=overpricing,
        developer_rating=developer_rating,
        inventory_risk=inventory_risk,
        negotiation_position=negotiation.position
    )

    # Assessment

    return create_assessment(
        property_name=property_input.property_name,
        developer_name=property_input.developer_name,
        
        country=property_input.country,

        state_province=property_input.state_province,

        city=property_input.city,

        property_type=
            property_input.property_type,

        quoted_price=property_input.quoted_price,
        fair_value=fair_value,

        quoted_price_per_sqft=
            quoted_price_per_sqft,

        fair_value_per_sqft=
            fair_value_per_sqft,

        unit_area=property_input.unit_area,
        area_unit=property_input.area_unit,
        normalized_area=normalized_area,

        overpricing_percent=overpricing,

        inventory_risk=inventory_risk,

        developer_rating=developer_rating,

        valuation_score=valuation_score_value,
        inventory_score=inventory_score_output,
        developer_score=developer_score_output,

        buyer_protection_score=bps.score,
        buyer_protection_rating=bps.rating,

        recommendation=recommendation,

        deal_quality=deal_quality,
        deal_quality_reason=
            deal_quality_reason,

        negotiation_position=
            negotiation.position,

        negotiation_reason=
            negotiation.reason,
    
        target_price=
            negotiation.target_price,

        low_offer=
            negotiation.low_offer,

        high_offer=
            negotiation.high_offer,

        potential_savings=
            negotiation.potential_savings,    

        buyer_advantage_score=
            buyer_advantage.score,

        buyer_advantage_rating=
            buyer_advantage.rating,

        buyer_advantage_reason=
            buyer_advantage.reason,    

        recommendation_confidence_score=
            recommendation_confidence.score,

        recommendation_confidence_rating=
            recommendation_confidence.rating,

        recommendation_confidence_reason=
            recommendation_confidence.reason,    

        findings=findings,

        government_intelligence=
            government_intelligence,
            
        fraud_intelligence=
            fraud_intelligence,

        comparables=comparables,

        market_average_price_per_sqft=
            market_average_price_per_sqft,

        decision=decision    
    )