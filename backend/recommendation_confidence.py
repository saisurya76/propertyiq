from dataclasses import dataclass
from typing import Optional

@dataclass
class RecommendationConfidence:
    score: float
    rating: str
    reason: str


def assess_recommendation_confidence(
    buyer_protection_score: float,
    developer_score: Optional[float],
    inventory_score: Optional[float],
    valuation_score: float
):

    scores = [
        buyer_protection_score,
        valuation_score
    ]

    if developer_score is not None:
        scores.append(
            developer_score
        )

    if inventory_score is not None:
        scores.append(
            inventory_score
        )

    score = round(
        sum(scores) / len(scores),
        2
    )

    if score >= 90:

        rating = "VERY HIGH"

        reason = (
            "PropertyIQ's recommendation is supported by "
            "strong and consistent evidence."
        )

    elif score >= 80:

        rating = "HIGH"

        reason = (
            "Most available assessment models support "
            "the recommendation."
        )

    elif score >= 70:

        rating = "MODERATE"

        reason = (
            "The available evidence generally supports "
            "the recommendation."
        )

    elif score >= 60:

        rating = "LOW"

        reason = (
            "Available evidence is mixed. Additional "
            "due diligence is recommended."
        )

    else:

        rating = "VERY LOW"

        reason = (
            "Available evidence is limited or inconsistent. "
            "Exercise additional caution."
        )

    return RecommendationConfidence(
        score=score,
        rating=rating,
        reason=reason
    )