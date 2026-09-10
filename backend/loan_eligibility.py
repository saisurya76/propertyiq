"""Real, transparent loan eligibility estimation.

Unlike loan_calculator.py's EMI math (a deterministic formula with one
correct answer), real bank underwriting varies enormously by lender,
country, and product — there is no single "correct" eligibility
answer this app could compute. This module is honest about that: it
applies standard, named, configurable rules of thumb (FOIR, LTV, an
age-at-maturity cap, a minimum credit rating) that a real lender's own
underwriting is likely to check in some form, and clearly labels the
result as an estimate, not a loan offer or approval — same honesty
standard as the EMI calculator's own "illustrative only" language.

Every threshold is admin-configurable (via the same generic
app_config key-value store get_app_setting/set_app_setting already
uses for the Gemini API key), with a real, reasonable default so the
feature works immediately without any admin setup.
"""

from typing import Any, Optional

from backend.config_store import get_app_setting, set_app_setting

_DEFAULTS = {
    # FOIR: (existing monthly obligations + the new EMI) as a % of
    # monthly income. 50% is a commonly-cited real-world lender
    # threshold across multiple countries, not this app's own invention.
    "loan_eligibility_max_foir_percent": "50",
    # LTV: loan amount as a % of the property's price — the
    # complement is the minimum real down payment a borrower needs.
    # 80% (20% minimum down payment) is a common real baseline.
    "loan_eligibility_max_ltv_percent": "80",
    # A borrower's age plus the loan's own tenure shouldn't exceed
    # this — a standard real constraint most mortgage lenders apply.
    "loan_eligibility_max_age_at_maturity": "65",
    # Below this self-reported rating, eligibility fails regardless of
    # the numbers — real lenders weight credit history heavily, and
    # this app has no real credit-bureau integration to pull an actual
    # score from (these vary by country: CIBIL in India, etc.), so a
    # simple, universal self-reported rating is the honest substitute.
    "loan_eligibility_min_credit_rating": "fair",
}

CREDIT_RATINGS = ["poor", "fair", "good", "excellent"]  # ordered worst to best


def get_loan_eligibility_settings() -> dict[str, Any]:
    return {
        "max_foir_percent": float(get_app_setting("loan_eligibility_max_foir_percent") or _DEFAULTS["loan_eligibility_max_foir_percent"]),
        "max_ltv_percent": float(get_app_setting("loan_eligibility_max_ltv_percent") or _DEFAULTS["loan_eligibility_max_ltv_percent"]),
        "max_age_at_maturity": int(get_app_setting("loan_eligibility_max_age_at_maturity") or _DEFAULTS["loan_eligibility_max_age_at_maturity"]),
        "min_credit_rating": get_app_setting("loan_eligibility_min_credit_rating") or _DEFAULTS["loan_eligibility_min_credit_rating"],
    }


def set_loan_eligibility_settings(
    *,
    max_foir_percent: Optional[float] = None,
    max_ltv_percent: Optional[float] = None,
    max_age_at_maturity: Optional[int] = None,
    min_credit_rating: Optional[str] = None,
) -> dict[str, Any]:
    if max_foir_percent is not None:
        if not (0 < max_foir_percent <= 100):
            raise ValueError("Max FOIR % must be between 0 and 100.")
        set_app_setting("loan_eligibility_max_foir_percent", str(max_foir_percent))
    if max_ltv_percent is not None:
        if not (0 < max_ltv_percent <= 100):
            raise ValueError("Max LTV % must be between 0 and 100.")
        set_app_setting("loan_eligibility_max_ltv_percent", str(max_ltv_percent))
    if max_age_at_maturity is not None:
        if not (18 < max_age_at_maturity <= 100):
            raise ValueError("Max age at maturity must be a realistic age.")
        set_app_setting("loan_eligibility_max_age_at_maturity", str(max_age_at_maturity))
    if min_credit_rating is not None:
        if min_credit_rating not in CREDIT_RATINGS:
            raise ValueError(f"Credit rating must be one of: {', '.join(CREDIT_RATINGS)}")
        set_app_setting("loan_eligibility_min_credit_rating", min_credit_rating)
    return get_loan_eligibility_settings()


def check_loan_eligibility(
    *,
    monthly_income: float,
    existing_monthly_obligations: float,
    property_price: float,
    down_payment_available: float,
    age: int,
    credit_rating: str,
    annual_rate_percent: float,
    tenure_years: float,
) -> dict[str, Any]:
    """Real, transparent pass/fail against each configured rule —
    returns every individual check's own result, not just a final
    yes/no, so a borrower or agent can see exactly which real
    constraint is the blocker."""
    from backend.loan_calculator import calculate_emi

    if monthly_income <= 0:
        raise ValueError("Monthly income must be greater than zero.")
    if property_price <= 0:
        raise ValueError("Property price must be greater than zero.")
    if down_payment_available < 0 or existing_monthly_obligations < 0:
        raise ValueError("Down payment and existing obligations cannot be negative.")
    if credit_rating not in CREDIT_RATINGS:
        raise ValueError(f"Credit rating must be one of: {', '.join(CREDIT_RATINGS)}")

    settings = get_loan_eligibility_settings()
    loan_amount = max(0.0, property_price - down_payment_available)
    proposed_emi = calculate_emi(loan_amount, annual_rate_percent, tenure_years) if loan_amount > 0 else 0.0

    foir_percent = ((existing_monthly_obligations + proposed_emi) / monthly_income) * 100
    foir_pass = foir_percent <= settings["max_foir_percent"]

    ltv_percent = (loan_amount / property_price) * 100 if property_price else 0
    ltv_pass = ltv_percent <= settings["max_ltv_percent"]

    age_at_maturity = age + tenure_years
    age_pass = age_at_maturity <= settings["max_age_at_maturity"]

    credit_pass = CREDIT_RATINGS.index(credit_rating) >= CREDIT_RATINGS.index(settings["min_credit_rating"])

    checks = [
        {"name": "Debt-to-income (FOIR)", "pass": foir_pass, "detail": f"{foir_percent:.1f}% of income (max {settings['max_foir_percent']:.0f}%)"},
        {"name": "Loan-to-value (LTV)", "pass": ltv_pass, "detail": f"{ltv_percent:.1f}% of property price (max {settings['max_ltv_percent']:.0f}%)"},
        {"name": "Age at loan maturity", "pass": age_pass, "detail": f"{age_at_maturity:.0f} years old at payoff (max {settings['max_age_at_maturity']})"},
        {"name": "Credit rating", "pass": credit_pass, "detail": f"{credit_rating.title()} (minimum: {settings['min_credit_rating'].title()})"},
    ]
    is_eligible = all(c["pass"] for c in checks)

    # A real, useful number even when the check fails: the largest
    # loan that WOULD satisfy the FOIR rule at this income and these
    # obligations, holding rate/tenure fixed — found by solving the
    # EMI formula for principal rather than guessing.
    max_affordable_emi = max(0.0, (monthly_income * settings["max_foir_percent"] / 100) - existing_monthly_obligations)
    max_eligible_loan = _max_principal_for_emi(max_affordable_emi, annual_rate_percent, tenure_years)

    return {
        "is_eligible": is_eligible,
        "checks": checks,
        "requested_loan_amount": round(loan_amount, 2),
        "proposed_emi": round(proposed_emi, 2),
        "max_eligible_loan_amount": round(max_eligible_loan, 2),
        "settings_used": settings,
    }


def _max_principal_for_emi(max_emi: float, annual_rate_percent: float, tenure_years: float) -> float:
    """Inverse of the standard EMI formula — the real principal that
    the given EMI, rate, and tenure would finance, not an estimate."""
    if max_emi <= 0:
        return 0.0
    n = round(tenure_years * 12)
    if annual_rate_percent == 0:
        return max_emi * n
    r = annual_rate_percent / 12 / 100
    factor = (1 + r) ** n
    return max_emi * (factor - 1) / (r * factor)
