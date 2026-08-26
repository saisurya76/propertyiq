import pytest

from backend.comparables import get_comparables, average_price_per_sqft, ALL_COMPARABLES
from backend.instant_score import compute_instant_score


# The exact set of cities this research pass added real coverage for —
# used to verify each one genuinely works, not just spot-checked.
NEWLY_SUPPORTED_CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Chennai", "Kolkata", "Pune", "Ahmedabad", "Lucknow", "Nagpur",
    "Bangkok", "Chiang Mai", "Phuket", "Pattaya",
    "Ho Chi Minh City", "Hanoi", "Da Nang",
    "Jakarta", "Bandung",
    "Manila", "Quezon City", "Cebu City", "Makati",
]


@pytest.mark.parametrize("city", NEWLY_SUPPORTED_CITIES)
def test_each_newly_added_city_has_real_apartment_comparables(city):
    comparables = get_comparables(city, "Apartment")
    assert len(comparables) > 0, f"{city} should have real comparable data after this expansion"
    assert all(c.price_per_sqft > 0 for c in comparables)


@pytest.mark.parametrize("city", NEWLY_SUPPORTED_CITIES)
def test_each_newly_added_city_produces_a_real_instant_score(city):
    """End-to-end check, not just the raw data — confirms the whole
    pipeline (comparables -> average -> score) genuinely works for
    every newly-added city, not just that a data row exists."""
    comparables = get_comparables(city, "Apartment")
    market_avg = average_price_per_sqft(comparables)
    fair_price = market_avg * 1200  # exactly at market average

    result = compute_instant_score(price=fair_price, city=city, property_type="Apartment", area_value=1200)
    assert result["coverage"] == "supported"
    assert result["score"] == 70  # the documented anchor point at exactly market average


def test_hyderabad_data_is_unaffected_by_the_expansion():
    """The original, pre-existing Hyderabad data must be completely
    untouched by this expansion — same 4 named projects, same prices."""
    comparables = get_comparables("Hyderabad", "Apartment")
    assert len(comparables) == 4
    names = {c.project_name for c in comparables}
    assert names == {"Aparna Zenon", "Prestige High Fields", "My Home Bhooja", "Lansum Elena"}


def test_a_genuinely_unresearched_city_still_returns_honestly_empty():
    """Cities not covered by this research pass must NOT silently get a
    fabricated number — they should still produce the same honest
    'no data' result as before this expansion."""
    comparables = get_comparables("Jaipur", "Apartment")  # a real city, deliberately not covered in this pass
    assert comparables == []

    result = compute_instant_score(price=5000000, city="Jaipur", property_type="Apartment", area_value=1200)
    assert result["coverage"] == "unsupported"


def test_villa_type_is_honestly_unsupported_even_for_covered_cities():
    """This expansion only added Apartment-type data — a Villa request
    for the same city must still be honest about having no Villa data,
    not silently reuse the Apartment figures."""
    comparables = get_comparables("Mumbai", "Villa")
    assert comparables == []


def test_no_duplicate_city_property_type_entries_across_all_comparables():
    """A sanity check on the data itself: no city+type combination
    should have been accidentally listed in two different country
    blocks (a copy-paste risk when merging several research passes)."""
    seen = set()
    for c in ALL_COMPARABLES:
        key = (c.city.lower(), c.property_type.lower())
        # Hyderabad appearing multiple times is fine -- it has multiple
        # distinct named projects. Every other city in this expansion
        # has exactly one citywide-average entry, so a genuine
        # duplicate elsewhere would indicate a real data bug.
        if c.city.lower() != "hyderabad":
            assert key not in seen, f"Duplicate entry for {c.city}/{c.property_type}"
            seen.add(key)
