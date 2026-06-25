from dataclasses import dataclass


@dataclass
class RecommendationConfidence:
    score: float
    rating: str
    reason: str


def assess_recommendation_confidence(
    buyer_protection_score: float,
    developer_score: float,
    inventory_score: float,
    valuation_score: float
):

    score = round(
        (
            buyer_protection_score +
            developer_score +
            inventory_score +
            valuation_score
        ) / 4,
        2
    )

    if score >= 90:

        rating = "VERY HIGH"

        reason = (
            "PropertyIQ's recommendation is supported by "
            "strong and consistent signals across all "
            "assessment models."
        )

    elif score >= 80:

        rating = "HIGH"

        reason = (
            "The recommendation is supported by multiple "
            "independent assessment models with good "
            "overall agreement."
        )

    elif score >= 70:

        rating = "MODERATE"

        reason = (
            "Most assessment models support the recommendation, "
            "though some uncertainty remains."
        )

    elif score >= 60:

        rating = "LOW"

        reason = (
            "Assessment results are mixed. Additional due "
            "diligence is recommended."
        )

    else:

        rating = "VERY LOW"

        reason = (
            "Assessment signals are inconsistent. Exercise "
            "additional caution before proceeding."
        )

    return RecommendationConfidence(
        score=score,
        rating=rating,
        reason=reason
    )