from dataclasses import dataclass


@dataclass
class DeveloperResult:
    score: float
    rating: str


def assess_developer(
    projects_completed: int,
    projects_delayed: int,
    years_in_business: int,
    rera_violations: int
) -> DeveloperResult:

    if projects_completed < 0:
        raise ValueError(
            "Projects completed cannot be negative."
        )

    if projects_delayed < 0:
        raise ValueError(
            "Projects delayed cannot be negative."
        )

    if years_in_business < 0:
        raise ValueError(
            "Years in business cannot be negative."
        )

    if rera_violations < 0:
        raise ValueError(
            "Regulatory violations cannot be negative."
        )

    total_projects = (
        projects_completed +
        projects_delayed
    )

    if total_projects == 0:
        raise ValueError(
            "Developer must have projects."
        )

    delay_percent = (
        projects_delayed /
        total_projects
    ) * 100

    delivery_score = max(
        50,
        100 - delay_percent
    )

    longevity_score = min(
        100,
        years_in_business * 5
    )

    compliance_score = max(
        50,
        100 - (rera_violations * 10)
    )

    score = (
        delivery_score * 0.50 +
        longevity_score * 0.25 +
        compliance_score * 0.25
    )

    if score >= 90:
        rating = "EXCELLENT"
    elif score >= 80:
        rating = "GOOD"
    elif score >= 70:
        rating = "AVERAGE"
    else:
        rating = "WEAK"

    return DeveloperResult(
        score=round(score, 2),
        rating=rating
    )