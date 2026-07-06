from dataclasses import dataclass
from typing import Optional

@dataclass
class BuyerProtectionResult:
    score: float
    rating: str


def calculate_buyer_protection_score(
    valuation_score: float,
    inventory_score: Optional[float],
    developer_score: Optional[float]
) -> BuyerProtectionResult:

    weighted_score = 0
    total_weight = 0

    weighted_score += valuation_score * 0.50
    total_weight += 0.50

    if inventory_score is not None:
        weighted_score += inventory_score * 0.30
        total_weight += 0.30

    if developer_score is not None:
        weighted_score += developer_score * 0.20
        total_weight += 0.20

    score = weighted_score / total_weight

    if score >= 90:
        rating = "EXCEPTIONAL"

    elif score >= 80:
        rating = "STRONG"

    elif score >= 70:
        rating = "FAIR"

    elif score >= 60:
        rating = "CAUTION"

    else:
        rating = "HIGH RISK"

    return BuyerProtectionResult(
        score=round(score,2),
        rating=rating
    )