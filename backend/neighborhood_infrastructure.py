"""Powers the Neighborhood Insights page's "Upcoming infrastructure"
card with a genuinely search-grounded summary — not a plain text
completion, which could hallucinate a metro line or highway that
doesn't exist. Uses Gemini's real Google Search grounding tool, which
actually searches the web and cites real, current pages, rather than
generating from training data alone.

HONESTY BOUNDARY, same spirit as discipline_overlays.py's own: this is
city-level general news, not verified as being near any specific
address, and news itself can be outdated, cancelled, or delayed after
announcement. Every result carries an explicit disclaimer saying so,
and the real source links returned by grounding are always shown so
the user can check them directly — this is a starting point to verify
independently, not a confirmed fact sheet.

Every no-data result also carries a `reason` code
(no_api_key/no_city/api_error/quota_exceeded/no_grounded_sources) — a
real, previously missing distinction: "the Gemini key isn't
configured" and "Gemini genuinely found nothing for this city" used to
look identical to the caller, which made a real misconfiguration (a
missing env var) indistinguishable from an honest empty result.
`error_detail` carries the real exception text for the api_error/
quota_exceeded cases specifically, logged server-side for debugging —
never shown to the end user as-is, since a raw exception string isn't
something a property buyer needs to see.

CACHING: results are cached per city for 24 hours via the same
get_app_setting/set_app_setting key-value store live_comparables.py
already uses for its own price cache — a real, necessary mitigation
for a genuine, confirmed external constraint: Google Search grounding
requests are, per multiple independent reports on Google's own
developer forum (including from paid-tier accounts), sometimes
miscategorized against a much smaller quota bucket than the one meant
for grounding. Caching means the same city is only ever asked of
Gemini once per day regardless of how many users look it up, which
matters directly given that constraint — not just a nice-to-have."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from google import genai
from google.genai import types

from backend.property_url_extract import get_gemini_api_key
from backend.config_store import get_app_setting, set_app_setting

logger = logging.getLogger(__name__)

CACHE_HOURS = 24

# Matches AccidentIQ's own real pattern for this exact setting
# (lib/aiProviderClient.js: `process.env.GEMINI_MODEL || 'gemini-3.5-flash-lite'`)
# — an env var override lets the model be changed directly in Render
# without a code change/redeploy, useful while diagnosing the real,
# external Search-grounding quota-routing issue this module works
# around (see CACHING note above and this module's own docstring).
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")

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
    # Only ever cache a genuine success — caching a quota-exceeded or
    # api_error result would mean a transient failure gets "stuck" for
    # a full day even after Google's own issue clears up, which is
    # worse than just re-trying (and re-hitting the same tiny quota
    # bucket) on the next real request.
    if not result["has_data"]:
        return
    set_app_setting(_cache_key(city_slug), json.dumps({"result": result, "fetched_at": datetime.now(timezone.utc).isoformat()}))


def get_infrastructure_summary(city: str) -> dict[str, Any]:
    """Returns {has_data, summary, sources, disclaimer, reason,
    error_detail}. `sources` is a list of {title, uri} pulled from
    Gemini's own real grounding metadata — never fabricated — so
    genuinely empty if grounding didn't return any (in which case
    has_data is also False, since an ungrounded summary here would be
    exactly the fabrication risk this feature exists to avoid)."""
    if not city or not city.strip():
        return _no_data("no_city")

    city_slug = city.strip().lower().replace(" ", "_")
    cached = _get_cached(city_slug)
    if cached is not None:
        return cached

    api_key = get_gemini_api_key()
    if not api_key:
        logger.warning("neighborhood_infrastructure: GEMINI_API_KEY is not configured (env var or admin panel).")
        return _no_data("no_api_key")

    prompt = f"""What are the major upcoming or recently announced infrastructure projects (metro lines, highways, expressways, major commercial or residential developments) in {city.strip()}, India?

Provide a concise, factual summary as 3-5 short bullet points, covering only real, currently-known projects you can find through search. If you cannot find reliable, current information for this specific city, say so plainly instead of guessing or generalizing from a different city.

Do not use markdown formatting other than a plain "- " prefix for each bullet point."""

    try:
        client = genai.Client(api_key=api_key)
        grounding_tool = types.Tool(google_search=types.GoogleSearch())
        response = client.models.generate_content(
            # Defaults to gemini-3.5-flash-lite — AccidentIQ's own
            # confirmed-working model (verified directly from that
            # repo's actual lib/aiProviderClient.js) — but overridable
            # via the GEMINI_MODEL env var (see that constant's own
            # comment) so a different model can be tried directly in
            # Render while diagnosing the real, external Search-
            # grounding quota-routing issue, without needing a code
            # change. AccidentIQ's own calls never use grounding at all
            # (plain generateContent, no tools), so matching its model
            # alone isn't guaranteed to resolve this — but changes
            # nothing about the grounding safeguard itself either way.
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(tools=[grounding_tool]),
        )
    except Exception as exc:
        # Previously a bare `except Exception: return no-data` swallowed
        # the real error entirely, making a genuine API failure (bad
        # key, wrong model name, quota exceeded, etc) indistinguishable
        # from an honest "nothing found" — logged here specifically so
        # this exact situation is diagnosable server-side, not silently
        # identical to every other no-data case.
        #
        # Quota exhaustion is detected specifically (not lumped into the
        # generic api_error bucket) because it's a real, distinct,
        # externally-confirmed case: Google Search grounding requests
        # are, per multiple independent developer reports (including
        # paid-tier accounts) on Google's own forum, sometimes
        # miscategorized against a much smaller quota bucket than the
        # one meant for grounding. Telling the user "temporarily
        # unavailable, try again shortly" is honest and actionable here,
        # whereas the generic "no reliable information found for this
        # city" would wrongly imply the city itself lacks real news.
        exc_text = str(exc)
        is_quota_error = "RESOURCE_EXHAUSTED" in exc_text or "429" in exc_text
        logger.error(f"neighborhood_infrastructure: Gemini API call failed for city={city!r}: {exc}")
        return _no_data("quota_exceeded" if is_quota_error else "api_error", error_detail=exc_text)

    summary = (response.text or "").strip()

    sources = []
    try:
        for candidate in response.candidates or []:
            metadata = getattr(candidate, "grounding_metadata", None)
            if not metadata or not metadata.grounding_chunks:
                continue
            for chunk in metadata.grounding_chunks:
                if chunk.web and chunk.web.uri:
                    sources.append({"title": chunk.web.title or chunk.web.uri, "uri": chunk.web.uri})
    except Exception as exc:
        logger.error(f"neighborhood_infrastructure: failed to parse grounding metadata for city={city!r}: {exc}")
        sources = []

    # Deliberately requires BOTH a real summary AND at least one real,
    # citable source — a summary with no grounding sources at all would
    # mean the model didn't actually search for this city, which is
    # exactly the ungrounded-guess case this feature exists to avoid.
    if not summary or not sources:
        logger.info(f"neighborhood_infrastructure: no grounded result for city={city!r} (summary_len={len(summary)}, sources={len(sources)}).")
        return _no_data("no_grounded_sources")

    result = {
        "has_data": True,
        "summary": summary,
        "sources": sources,
        "disclaimer": INFRASTRUCTURE_DISCLAIMER,
        "reason": "",
        "error_detail": "",
    }
    _set_cached(city_slug, result)
    return result
