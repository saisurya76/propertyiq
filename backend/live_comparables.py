"""Fetches genuinely live, current-month property price data — at zero
additional cost — from SquareYards' own public "Property Rates in
{City}" pages, which are confirmed (by directly re-fetching the same
URL a month apart during development) to be re-rendered with current
data each month, not a static page. This directly replaces relying
solely on comparables.py's hand-researched, one-time snapshot for
India cities, which can meaningfully drift from real current prices
over time — confirmed directly during development: the static
snapshot had Mumbai at ~₹14,000/sqft, while this live page currently
shows the real, current asking price at ~₹38,600/sqft, a genuinely
large gap this closes.

Honest, deliberate scope, not an oversight:
- India cities only — SquareYards doesn't cover the Thailand/Vietnam/
  Indonesia/Philippines cities this app also supports, which continue
  to rely on comparables.py's static research for now.
- Apartment type only, matching what this page's headline figure
  covers and what comparables.py already scoped itself to.
- Results are cached for 24 hours (in the same generic app_config
  key-value table property_url_extract's Gemini key uses) — long
  enough to avoid re-fetching this page on every single request (which
  would be both slow for users and inconsiderate of a free public
  source), short enough that "live" genuinely means current, not a
  new multi-month-stale snapshot of its own.
- If the live fetch or parsing fails for ANY reason (site restructured
  its HTML, temporarily down, network hiccup, an unmapped city) this
  falls back to comparables.py's static data automatically — this
  feature must never make Instant Score/Hidden Deal/etc LESS reliable
  than they already were; it can only make them more current when it
  successfully can.
"""

import json
import re
from datetime import datetime, timezone
from typing import Optional

from backend.property_url_extract import fetch_page_html, _html_to_text
from backend.config_store import get_app_setting, set_app_setting

CACHE_HOURS = 24

# SquareYards' own URL slug for each India city already covered by
# comparables.py's static data — the one place this mapping needs to
# stay in sync with that module's INDIA_COMPARABLES city list.
CITY_SLUGS = {
    "mumbai": "mumbai",
    "delhi": "delhi",
    "bangalore": "bangalore",
    "hyderabad": "hyderabad",
    "chennai": "chennai",
    "kolkata": "kolkata",
    "pune": "pune",
    "ahmedabad": "ahmedabad",
    "lucknow": "lucknow",
    "nagpur": "nagpur",
}

# Matches the page's own headline text pattern, e.g. "Asking Sale Price
# ₹ 9,300/Sq.Ft. For apartment" — deliberately loose on whitespace/case
# since this is matched against HTML-stripped plain text, not a fixed
# DOM structure, making it more resilient to markup changes specifically
# (though not immune to the page rewording this exact phrase entirely,
# which is the real, honest limit of any text-pattern approach here).
_ASKING_PRICE_PATTERN = re.compile(
    r"Asking\s+Sale\s+Price\s*₹\s*([\d,]+)\s*/\s*Sq\.?\s*Ft\.?\s*For\s+apartment",
    re.IGNORECASE,
)


def _cache_key(city_slug: str) -> str:
    return f"live_comparable_{city_slug}"


def _get_cached(city_slug: str) -> Optional[float]:
    raw = get_app_setting(_cache_key(city_slug))
    if not raw:
        return None
    try:
        cached = json.loads(raw)
        fetched_at = datetime.fromisoformat(cached["fetched_at"])
        age_hours = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
        if age_hours < CACHE_HOURS:
            return cached["price_per_sqft"]
    except (json.JSONDecodeError, KeyError, ValueError):
        pass  # a corrupted/unexpected cache entry is treated as a cache miss, not an error
    return None


def _set_cached(city_slug: str, price_per_sqft: float) -> None:
    set_app_setting(
        _cache_key(city_slug),
        json.dumps({"price_per_sqft": price_per_sqft, "fetched_at": datetime.now(timezone.utc).isoformat()}),
    )


def _parse_asking_price(html: str) -> Optional[float]:
    text = _html_to_text(html)
    match = _ASKING_PRICE_PATTERN.search(text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def get_live_price_per_sqft(city: str) -> Optional[float]:
    """Returns the current, live Apartment asking price per sqft for a
    supported India city, or None if the city isn't covered by this
    live source, the fetch fails, or the page's format has changed
    beyond what this parser recognizes — callers are expected to fall
    back to comparables.py's static data in every None case, not treat
    it as an error."""
    city_slug = CITY_SLUGS.get(city.strip().lower())
    if not city_slug:
        return None

    cached = _get_cached(city_slug)
    if cached is not None:
        return cached

    try:
        html = fetch_page_html(f"https://www.squareyards.com/property-rates-in-{city_slug}")
        price = _parse_asking_price(html)
    except Exception:
        return None

    if price is not None:
        _set_cached(city_slug, price)
    return price
