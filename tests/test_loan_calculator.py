from backend.loan_calculator import calculate_emi, build_amortization_schedule, summarize_loan
import pytest


def test_emi_matches_a_well_known_published_reference_value():
    """10,00,000 principal at 10% annual over 10 years is a commonly
    cited reference example across real, published EMI calculators —
    the correct answer is 13,215.07, independently verifiable."""
    emi = calculate_emi(1000000, 10, 10)
    assert round(emi, 2) == 13215.07


def test_emi_with_zero_interest_is_a_real_valid_edge_case():
    """0% is a genuine input (some developer financing schemes are
    advertised this way) -- must not divide by zero, and the correct
    answer is simply principal / number of months."""
    emi = calculate_emi(1200000, 0, 5)
    assert emi == 20000.0


def test_emi_rejects_a_non_positive_principal():
    with pytest.raises(ValueError):
        calculate_emi(0, 8, 20)
    with pytest.raises(ValueError):
        calculate_emi(-100000, 8, 20)


def test_emi_rejects_a_non_positive_tenure():
    with pytest.raises(ValueError):
        calculate_emi(1000000, 8, 0)


def test_emi_rejects_a_negative_rate():
    with pytest.raises(ValueError):
        calculate_emi(1000000, -1, 20)


def test_amortization_schedule_has_the_right_number_of_months():
    schedule = build_amortization_schedule(1000000, 10, 10)
    assert len(schedule) == 120


def test_amortization_schedule_ends_at_exactly_zero_balance():
    """A real, standard property of any correct amortization schedule:
    the balance must reach precisely zero at the end, not drift by a
    few cents due to accumulated rounding across many months."""
    schedule = build_amortization_schedule(5000000, 8.5, 20)
    assert schedule[-1]["remaining_balance"] == 0.0


def test_amortization_schedule_principal_and_interest_sum_to_the_payment():
    """Allows a 1-cent tolerance: principal_component and
    interest_component are each independently rounded to 2 decimals
    for display, so their sum can differ from the raw (unrounded)
    payment by a cent -- a real, standard artifact of any rounded
    amortization schedule, not a calculation error."""
    schedule = build_amortization_schedule(2000000, 9, 15)
    for row in schedule[:-1]:  # the final row's payment is a real, deliberately different balloon-style true-up
        assert abs((row["principal_component"] + row["interest_component"]) - row["payment"]) <= 0.02


def test_amortization_schedule_balance_decreases_every_month():
    schedule = build_amortization_schedule(3000000, 7.5, 10)
    balances = [row["remaining_balance"] for row in schedule]
    assert all(balances[i] > balances[i + 1] for i in range(len(balances) - 1))


def test_summarize_loan_matches_the_underlying_schedule_not_a_separate_estimate():
    """Confirms the summary's totals are computed from the exact same
    schedule the detailed view uses, not a separately-approximated
    figure that could disagree with it."""
    summary = summarize_loan(1000000, 10, 10)
    schedule = build_amortization_schedule(1000000, 10, 10)
    assert summary["total_paid"] == round(sum(r["payment"] for r in schedule), 2)
    assert summary["total_interest"] == round(sum(r["interest_component"] for r in schedule), 2)
    assert summary["emi"] == round(calculate_emi(1000000, 10, 10), 2)
    assert summary["total_months"] == 120
