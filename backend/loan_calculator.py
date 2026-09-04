"""Real, standard EMI (equated monthly installment) and loan
amortization math — no external data, no estimates, no honesty
concerns of the kind the rest of Neighborhood Insights has to navigate
for things like cost of living: this is a deterministic financial
calculation with one correct answer, verifiable against any standard
loan calculator or textbook formula.
"""

from typing import Any


def calculate_emi(principal: float, annual_rate_percent: float, tenure_years: float) -> float:
    """The standard EMI formula:
        EMI = P x R x (1+R)^N / ((1+R)^N - 1)
    where R is the MONTHLY rate (annual_rate_percent / 12 / 100) and N
    is the number of monthly installments (tenure_years * 12).

    A real, deliberate edge case handled correctly rather than
    dividing by zero: a 0% interest rate is a genuine, valid input
    (some builder/developer financing schemes are advertised this
    way) — the EMI in that case is simply principal / N, not an error."""
    if principal <= 0:
        raise ValueError("Principal must be greater than zero.")
    if tenure_years <= 0:
        raise ValueError("Tenure must be greater than zero.")
    if annual_rate_percent < 0:
        raise ValueError("Interest rate cannot be negative.")

    n = round(tenure_years * 12)
    if annual_rate_percent == 0:
        return principal / n

    r = annual_rate_percent / 12 / 100
    factor = (1 + r) ** n
    return principal * r * factor / (factor - 1)


def build_amortization_schedule(principal: float, annual_rate_percent: float, tenure_years: float) -> list[dict[str, Any]]:
    """Month-by-month breakdown of an EMI into its interest and
    principal components, and the remaining loan balance after each
    payment — the real, standard "amortization" a borrower would see
    from their own lender, not a simplified/averaged approximation.

    The final month's principal component is set to exactly whatever
    balance remains (rather than the formula's own rounded EMI split)
    so the schedule's last row always brings the balance to precisely
    zero — real amortization schedules do this too, since compounding
    a fixed, rounded EMI across many months would otherwise leave a
    few cents of drift at the end."""
    n = round(tenure_years * 12)
    emi = calculate_emi(principal, annual_rate_percent, tenure_years)
    r = annual_rate_percent / 12 / 100

    schedule = []
    balance = principal
    for month in range(1, n + 1):
        interest_component = balance * r
        principal_component = emi - interest_component
        if month == n:
            principal_component = balance
            payment = balance + interest_component
        else:
            payment = emi
        balance -= principal_component
        schedule.append({
            "month": month,
            "payment": round(payment, 2),
            "principal_component": round(principal_component, 2),
            "interest_component": round(interest_component, 2),
            "remaining_balance": round(max(balance, 0), 2),
        })
    return schedule


def summarize_loan(principal: float, annual_rate_percent: float, tenure_years: float) -> dict[str, Any]:
    """The real, high-level numbers a borrower actually wants at a
    glance, computed from the exact same schedule the detailed
    month-by-month view uses — never a separately-approximated
    "quick estimate" that could quietly disagree with the real
    schedule."""
    schedule = build_amortization_schedule(principal, annual_rate_percent, tenure_years)
    total_paid = sum(row["payment"] for row in schedule)
    total_interest = sum(row["interest_component"] for row in schedule)
    return {
        "emi": round(calculate_emi(principal, annual_rate_percent, tenure_years), 2),
        "total_months": len(schedule),
        "total_paid": round(total_paid, 2),
        "total_interest": round(total_interest, 2),
        "principal": principal,
    }
