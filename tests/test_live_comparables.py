from unittest.mock import patch

import pytest

from backend.live_comparables import (
    get_live_price_per_sqft,
    _parse_asking_price,
    _get_cached,
    _set_cached,
    CITY_SLUGS,
)
from backend.comparables import get_comparables


def test_parse_asking_price_matches_the_real_page_pattern():
    """A realistic fixture built from the actual observed page
    structure (Aug 2026 fetch) — the headline "Asking Sale Price ... For
    apartment" figure this whole module is built around."""
    html = """
    <html><body>
    <div>Asking Sale Price</div>
    <div>₹ 9,300/Sq.Ft.</div>
    <div>For apartment</div>
    </body></html>
    """
    assert _parse_asking_price(html) == 9300.0


def test_parse_asking_price_returns_none_for_unrecognized_structure():
    """A site redesign or genuinely different page must fail cleanly,
    not crash or return a wrong number."""
    html = "<html><body><p>This page structure has completely changed.</p></body></html>"
    assert _parse_asking_price(html) is None


def test_unmapped_city_returns_none_without_attempting_a_fetch():
    with patch("backend.live_comparables.fetch_page_html") as mock_fetch:
        result = get_live_price_per_sqft("SomeCityNotOnSquareYards")
    assert result is None
    mock_fetch.assert_not_called()


def test_fetch_failure_returns_none_gracefully():
    with patch("backend.live_comparables.fetch_page_html", side_effect=Exception("network error")):
        result = get_live_price_per_sqft("Hyderabad")
    assert result is None


def test_successful_fetch_is_cached_for_subsequent_calls():
    html = "<html><body>Asking Sale Price ₹ 9,300/Sq.Ft. For apartment</body></html>"
    with patch("backend.live_comparables.fetch_page_html", return_value=html) as mock_fetch:
        first = get_live_price_per_sqft("Hyderabad")
    assert first == 9300.0
    assert mock_fetch.call_count == 1

    with patch("backend.live_comparables.fetch_page_html") as mock_fetch_2:
        second = get_live_price_per_sqft("Hyderabad")
    assert second == 9300.0
    mock_fetch_2.assert_not_called()  # cache hit, no re-fetch


def test_get_comparables_uses_live_data_when_available():
    """The core integration this whole module exists for: when live
    data is genuinely fetchable, it replaces the static snapshot
    entirely for Apartment requests to a supported city."""
    with patch("backend.live_comparables.get_live_price_per_sqft", return_value=25000.0):
        comparables = get_comparables("Hyderabad", "Apartment")
    assert len(comparables) == 1
    assert comparables[0].price_per_sqft == 25000.0
    assert "Live" in comparables[0].project_name


def test_get_comparables_falls_back_to_static_when_live_data_unavailable():
    """The other half of the same guarantee: when live data can't be
    fetched for any reason, the static snapshot is used exactly as
    before this feature existed — this addition can only ever make
    results more current, never less reliable."""
    with patch("backend.live_comparables.get_live_price_per_sqft", return_value=None):
        comparables = get_comparables("Hyderabad", "Apartment")
    assert len(comparables) == 4  # the original 4 named Hyderabad projects
    names = {c.project_name for c in comparables}
    assert names == {"Aparna Zenon", "Prestige High Fields", "My Home Bhooja", "Lansum Elena"}


def test_get_comparables_never_attempts_live_fetch_for_non_apartment_types():
    """The live source only covers Apartment listings — a Villa/Plot/
    Commercial request must never even attempt it, matching this
    module's own explicitly stated scope."""
    with patch("backend.live_comparables.get_live_price_per_sqft") as mock_live:
        get_comparables("Hyderabad", "Villa")
    mock_live.assert_not_called()


def test_real_unmocked_fallback_behavior_in_this_sandbox():
    """A real, non-mocked call — in this sandbox (no internet access to
    squareyards.com), this must gracefully and quickly fall back to the
    static data, proving the fallback chain works end-to-end, not just
    in a mocked unit test. Deliberately uses a city not touched by any
    other test in this file (Pune, not Hyderabad) — several tests above
    populate the live-price cache for Hyderabad, and since that cache
    lives in the same persistent database tests share, reusing that
    city here would silently read the earlier test's cached value
    instead of genuinely exercising the no-internet fallback path."""
    comparables = get_comparables("Pune", "Apartment")
    assert len(comparables) == 1
    assert comparables[0].project_name == "Citywide Average (Aug 2026)"
    from backend.comparables import average_price_per_sqft
    assert average_price_per_sqft(comparables) == 12950.0


@pytest.mark.parametrize("city", list(CITY_SLUGS.keys()))
def test_every_mapped_city_has_a_real_squareyards_slug(city):
    """A sanity check on the mapping itself — every city this module
    claims to cover must have a real, non-empty slug string."""
    assert CITY_SLUGS[city]
    assert isinstance(CITY_SLUGS[city], str)
