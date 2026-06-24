from dataclasses import dataclass

from backend.comparables import (
    get_comparables,
    average_price_per_sqft
)

from configs.defaults import (
    DEFAULT_COMPARABLE_PRICES,
    DEFAULT_TARGET_YIELD,
    DEFAULT_REPLACEMENT_COST
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

from backend.findings import (
    generate_findings
)

from backend.assessment import (
    create_assessment
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

    unit_area: float
    area_unit: str

    monthly_rent: float

    total_units: int
    unsold_units: int

    projects_completed: int
    projects_delayed: int
    years_in_business: int
    rera_violations: int


def run_assessment(
    property_input: PropertyInput
):

    # Normalize Area

    normalized_area = to_sqft(
        property_input.unit_area,
        property_input.area_unit
    )

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
        DEFAULT_COMPARABLE_PRICES
    )

    # Rental Yield Value

    rental_value = rental_yield_value(
        property_input.monthly_rent,
        DEFAULT_TARGET_YIELD
    )

    # Replacement Cost Value

    replacement_value = replacement_cost_value(
        **DEFAULT_REPLACEMENT_COST
    )

    # Weighted Fair Value

    fair_value = weighted_fair_value(
        comparable_value=comparable_value,
        rental_value=rental_value,
        replacement_value=replacement_value
    )

    # Overpricing

    overpricing = calculate_overpricing_percent(
        property_input.quoted_price,
        fair_value
    )

    # Inventory Assessment

    inventory = assess_inventory_risk(
        property_input.total_units,
        property_input.unsold_units
    )

    # Developer Assessment

    developer = assess_developer(
        property_input.projects_completed,
        property_input.projects_delayed,
        property_input.years_in_business,
        property_input.rera_violations
    )

    # Component Scores

    valuation_score_value = valuation_score(
        overpricing
    )

    inventory_score_value = inventory_score(
        inventory.risk_level
    )

    # Buyer Protection Score

    bps = calculate_buyer_protection_score(
        valuation_score=valuation_score_value,
        inventory_score=inventory_score_value,
        developer_score=developer.score
    )

    # Recommendation

    recommendation = get_recommendation(
        overpricing_percent=overpricing,
        inventory_risk=inventory.risk_level,
        developer_rating=developer.rating,
        buyer_protection_score=bps.score
    )

    # Findings

    findings = generate_findings(
        overpricing_percent=overpricing,
        inventory_risk=inventory.risk_level,
        developer_rating=developer.rating,
        recommendation=recommendation
    )

    # Assessment

    return create_assessment(
        property_name=property_input.property_name,
        developer_name=property_input.developer_name,

        quoted_price=property_input.quoted_price,
        fair_value=fair_value,

        unit_area=property_input.unit_area,
        area_unit=property_input.area_unit,

        overpricing_percent=overpricing,

        inventory_risk=inventory.risk_level,

        developer_rating=developer.rating,

        valuation_score=valuation_score_value,
        inventory_score=inventory_score_value,
        developer_score=developer.score,

        buyer_protection_score=bps.score,
        buyer_protection_rating=bps.rating,

        recommendation=recommendation,

        findings=findings,

        comparables=comparables,

        market_average_price_per_sqft=
            market_average_price_per_sqft
    )