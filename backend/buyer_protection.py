from dataclasses import dataclass


@dataclass
class BuyerProtectionResult:
    score: float
    rating: str


def calculate_buyer_protection_score(
    valuation_score: float,
    inventory_score: float,
    developer_score: float
) -> BuyerProtectionResult:

    score = (
        valuation_score * 0.50
        + inventory_score * 0.30
        + developer_score * 0.20
    )

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
        score=round(score, 2),
        rating=rating
    )