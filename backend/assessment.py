from dataclasses import dataclass

from backend.findings import FindingsResult

from backend.government_intelligence import (
    GovernmentIntelligence
)

@dataclass
class PropertyAssessment:
    property_name: str
    developer_name: str

    country: str
    state_province: str
    city: str

    quoted_price: float
    fair_value: float

    quoted_price_per_sqft: float
    fair_value_per_sqft: float

    quoted_price_per_sqft: float

    fair_value_per_sqft: float

    unit_area: float
    area_unit: str

    overpricing_percent: float

    inventory_risk: str

    developer_rating: str

    valuation_score: float
    inventory_score: float
    developer_score: float

    buyer_protection_score: float
    buyer_protection_rating: str

    recommendation: str
    
    deal_quality: str
    deal_quality_reason: str

    negotiation_position: str
    negotiation_reason: str

    target_price: float
    low_offer: float
    high_offer: float

    potential_savings: float
    buyer_advantage_score: float
    buyer_advantage_rating: str
    buyer_advantage_reason: str

    recommendation_confidence_score: float
    recommendation_confidence_rating: str
    recommendation_confidence_reason: str

    findings: FindingsResult

    government_intelligence: GovernmentIntelligence

    # Market Intelligence

    comparables: list

    market_average_price_per_sqft: float


def create_assessment(
    property_name: str,
    developer_name: str,
    country: str,
    state_province: str,
    city: str,

    quoted_price: float,
    fair_value: float,

    quoted_price_per_sqft: float,

    fair_value_per_sqft: float,

    unit_area: float,
    area_unit: str,

    overpricing_percent: float,

    inventory_risk: str,

    developer_rating: str,

    valuation_score: float,
    inventory_score: float,
    developer_score: float,

    buyer_protection_score: float,
    buyer_protection_rating: str,

    negotiation_position: str,
    negotiation_reason: str,

    target_price: float,
    low_offer: float,
    high_offer: float,

    potential_savings: float,
    buyer_advantage_score: float,
    buyer_advantage_rating: str,
    buyer_advantage_reason: str,

    recommendation_confidence_score: float,
    recommendation_confidence_rating: str,
    recommendation_confidence_reason: str,

    recommendation: str,
    deal_quality: str,
    deal_quality_reason: str,

    findings: FindingsResult,

    government_intelligence: GovernmentIntelligence,

    comparables: list,

    market_average_price_per_sqft: float
) -> PropertyAssessment:

    return PropertyAssessment(
        property_name=property_name,
        developer_name=developer_name,
        country=country,
        state_province=state_province,
        city=city,

        quoted_price=quoted_price,
        fair_value=fair_value,
                
        quoted_price_per_sqft=
            quoted_price_per_sqft,

        fair_value_per_sqft=
            fair_value_per_sqft,

        unit_area=unit_area,
        area_unit=area_unit,

        overpricing_percent=overpricing_percent,

        inventory_risk=inventory_risk,

        developer_rating=developer_rating,

        valuation_score=valuation_score,
        inventory_score=inventory_score,
        developer_score=developer_score,

        buyer_protection_score=buyer_protection_score,
        buyer_protection_rating=buyer_protection_rating,

        recommendation=recommendation,

        deal_quality=deal_quality,
        deal_quality_reason=
            deal_quality_reason,

        negotiation_position=
            negotiation_position,

        negotiation_reason=
            negotiation_reason,

        target_price=
            target_price,

        low_offer=
            low_offer,

        high_offer=
            high_offer,

        potential_savings=
            potential_savings,    

        buyer_advantage_score=
            buyer_advantage_score,

        buyer_advantage_rating=
            buyer_advantage_rating,

        buyer_advantage_reason=
            buyer_advantage_reason,

        recommendation_confidence_score=
            recommendation_confidence_score,

        recommendation_confidence_rating=
            recommendation_confidence_rating,

        recommendation_confidence_reason=
            recommendation_confidence_reason,        

        findings=findings,

        government_intelligence=
            government_intelligence,

        comparables=comparables,

        market_average_price_per_sqft=
            market_average_price_per_sqft
    )