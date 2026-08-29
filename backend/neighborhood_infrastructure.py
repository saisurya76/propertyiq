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
(no_api_key/no_city/api_error/no_grounded_sources) — a real, previously
missing distinction: "the Gemini key isn't configured" and "Gemini
genuinely found nothing for this city" used to look identical to the
caller, which made a real misconfiguration (a missing env var)
indistinguishable from an honest empty result. `error_detail` carries
the real exception text for the api_error case specifically, logged
server-side for debugging — never shown to the end user as-is, since a
raw exception string isn't something a property buyer needs to see.
"""

import logging
from typing import Any

from google import genai
from google.genai import types

from backend.property_url_extract import get_gemini_api_key

logger = logging.getLogger(__name__)

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


def get_infrastructure_summary(city: str) -> dict[str, Any]:
    """Returns {has_data, summary, sources, disclaimer, reason,
    error_detail}. `sources` is a list of {title, uri} pulled from
    Gemini's own real grounding metadata — never fabricated — so
    genuinely empty if grounding didn't return any (in which case
    has_data is also False, since an ungrounded summary here would be
    exactly the fabrication risk this feature exists to avoid)."""
    api_key = get_gemini_api_key()
    if not api_key:
        logger.warning("neighborhood_infrastructure: GEMINI_API_KEY is not configured (env var or admin panel).")
        return _no_data("no_api_key")

    if not city or not city.strip():
        return _no_data("no_city")

    prompt = f"""What are the major upcoming or recently announced infrastructure projects (metro lines, highways, expressways, major commercial or residential developments) in {city.strip()}, India?

Provide a concise, factual summary as 3-5 short bullet points, covering only real, currently-known projects you can find through search. If you cannot find reliable, current information for this specific city, say so plainly instead of guessing or generalizing from a different city.

Do not use markdown formatting other than a plain "- " prefix for each bullet point."""

    try:
        client = genai.Client(api_key=api_key)
        grounding_tool = types.Tool(google_search=types.GoogleSearch())
        response = client.models.generate_content(
            model="gemini-flash-latest",
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
        logger.error(f"neighborhood_infrastructure: Gemini API call failed for city={city!r}: {exc}")
        return _no_data("api_error", error_detail=str(exc))

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

    return {
        "has_data": True,
        "summary": summary,
        "sources": sources,
        "disclaimer": INFRASTRUCTURE_DISCLAIMER,
        "reason": "",
        "error_detail": "",
    }
