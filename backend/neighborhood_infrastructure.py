"""Powers the Neighborhood Insights page's "Upcoming infrastructure"
card with a genuinely search-grounded summary — not a plain LLM
completion, which could hallucinate a metro line or highway that
doesn't exist.

Uses Tavily's search API (tavily.com) rather than Gemini's built-in
Google Search grounding tool, which this module originally used. That
approach was replaced deliberately, not as a downgrade: Gemini's own
Search grounding turned out to be one of the most expensive options on
the market (up to $35/1,000 queries, billed per individual search the
model runs, not per prompt) and repeatedly hit a real, externally-
confirmed quota-routing issue (multiple independent developer reports,
including on Google's own official forum, describe grounded requests
getting miscategorized against a much smaller quota bucket than the
one meant for them — reproduced directly on this project's own Free
and paid-adjacent keys, including a fresh key created specifically to
rule out a one-off issue). Tavily is purpose-built for exactly this
(feeding real web content to an AI/app), has a genuinely free tier
(1,000 credits/month, recurring, no credit card), and returns both raw
search results AND an optional synthesized answer in a single call —
removing the need for a separate LLM call entirely for this feature.

HONESTY BOUNDARY, unchanged from the Gemini-based version: this is
city-level general news, not verified as being near any specific
address, and news itself can be outdated, cancelled, or delayed after
announcement. Every result carries an explicit disclaimer saying so,
and the real source links Tavily returns are always shown so the user
can check them directly — this is a starting point to verify
independently, not a confirmed fact sheet. Deliberately requires BOTH
a real synthesized answer AND at least one real source URL to count as
"has data" — an answer with zero real sources would mean the search
didn't actually turn up anything to ground it in, exactly the
ungrounded-guess case this feature exists to avoid.

CACHING: results are cached per city for 24 hours via the same
get_app_setting/set_app_setting key-value store live_comparables.py
already uses for its own price cache. Even though Tavily's free tier
is far more generous than Gemini's grounding was, caching still means
the same city is only ever searched once per day regardless of how
many users look it up — real, sensible efficiency, not a necessity
imposed by a tiny quota this time.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from tavily import TavilyClient

from backend.config_store import get_app_setting, set_app_setting

logger = logging.getLogger(__name__)

CACHE_HOURS = 24

TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "")

INFRASTRUCTURE_DISCLAIMER = (
    "AI-generated summary of general city-level news, using real web search — not verified as being "
    "near this specific address, and infrastructure news can be outdated, delayed, or cancelled after "
    "announcement. Check the sources below yourself, and verify with your local municipal or urban "
    "development authority before treating any of this as confirmed."
)


def _no_data(reason: str, error_detail: str = "") -> dict[str, Any]:
    return {
        "has_data": False,
        "summary": "",
        "sources": [],
        "disclaimer": INFRASTRUCTURE_DISCLAIMER,
        "reason": reason,
        "error_detail": error_detail,
    }


def _cache_key(city_slug: str) -> str:
    return f"infra_summary_{city_slug}"


def _get_cached(city_slug: str) -> Optional[dict[str, Any]]:
    raw = get_app_setting(_cache_key(city_slug))
    if not raw:
        return None
    try:
        cached = json.loads(raw)
        fetched_at = datetime.fromisoformat(cached["fetched_at"])
        age_hours = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
        if age_hours < CACHE_HOURS:
            return cached["result"]
    except (json.JSONDecodeError, KeyError, ValueError):
        pass  # a corrupted/unexpected cache entry is treated as a cache miss, not an error
    return None


def _set_cached(city_slug: str, result: dict[str, Any]) -> None:
    # Only ever cache a genuine success — caching a failure would mean
    # a transient outage gets "stuck" for a full day even after it
    # clears, which is worse than just re-trying on the next request.
    if not result["has_data"]:
        return
    set_app_setting(_cache_key(city_slug), json.dumps({"result": result, "fetched_at": datetime.now(timezone.utc).isoformat()}))


def get_infrastructure_summary(city: str) -> dict[str, Any]:
    """Returns {has_data, summary, sources, disclaimer, reason,
    error_detail}. `sources` is a list of {title, uri} pulled from
    Tavily's own real search results — never fabricated — so
    genuinely empty if the search turned up nothing (in which case
    has_data is also False)."""
    if not city or not city.strip():
        return _no_data("no_city")

    city_slug = city.strip().lower().replace(" ", "_")
    cached = _get_cached(city_slug)
    if cached is not None:
        return cached

    if not TAVILY_API_KEY:
        logger.warning("neighborhood_infrastructure: TAVILY_API_KEY is not configured.")
        return _no_data("no_api_key")

    query = f"upcoming infrastructure projects metro highway development {city.strip()} India 2026"

    try:
        client = TavilyClient(api_key=TAVILY_API_KEY)
        response = client.search(
            query=query,
            search_depth="basic",
            topic="news",
            max_results=5,
            include_answer=True,
            country="india",
        )
    except Exception as exc:
        exc_text = str(exc)
        is_quota_error = "quota" in exc_text.lower() or "429" in exc_text or "usage" in exc_text.lower()
        logger.error(f"neighborhood_infrastructure: Tavily API call failed for city={city!r}: {exc}")
        return _no_data("quota_exceeded" if is_quota_error else "api_error", error_detail=exc_text)

    answer = (response.get("answer") or "").strip()
    sources = [
        {"title": r.get("title") or r.get("url", ""), "uri": r["url"]}
        for r in response.get("results", [])
        if r.get("url")
    ]

    # Deliberately requires BOTH a real synthesized answer AND at least
    # one real source URL — an answer with zero real sources would mean
    # the search didn't actually turn up anything to ground it in,
    # exactly the ungrounded-guess case this feature exists to avoid.
    if not answer or not sources:
        logger.info(f"neighborhood_infrastructure: no usable result for city={city!r} (answer_len={len(answer)}, sources={len(sources)}).")
        return _no_data("no_grounded_sources")

    result = {
        "has_data": True,
        "summary": answer,
        "sources": sources,
        "disclaimer": INFRASTRUCTURE_DISCLAIMER,
        "reason": "",
        "error_detail": "",
    }
    _set_cached(city_slug, result)
    return result
