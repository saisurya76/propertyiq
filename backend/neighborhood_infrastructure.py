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
"""

from typing import Any

from google import genai
from google.genai import types

from backend.property_url_extract import get_gemini_api_key

INFRASTRUCTURE_DISCLAIMER = (
    "AI-generated summary of general city-level news, using real web search — not verified as being "
    "near this specific address, and infrastructure news can be outdated, delayed, or cancelled after "
    "announcement. Check the sources below yourself, and verify with your local municipal or urban "
    "development authority before treating any of this as confirmed."
)


def get_infrastructure_summary(city: str) -> dict[str, Any]:
    """Returns {has_data, summary, sources, disclaimer}. `sources` is a
    list of {title, uri} pulled from Gemini's own real grounding
    metadata — never fabricated — so genuinely empty if grounding
    didn't return any (in which case has_data is also False, since an
    ungrounded summary here would be exactly the fabrication risk this
    feature exists to avoid)."""
    api_key = get_gemini_api_key()
    if not api_key:
        return {"has_data": False, "summary": "", "sources": [], "disclaimer": INFRASTRUCTURE_DISCLAIMER}

    if not city or not city.strip():
        return {"has_data": False, "summary": "", "sources": [], "disclaimer": INFRASTRUCTURE_DISCLAIMER}

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
    except Exception:
        return {"has_data": False, "summary": "", "sources": [], "disclaimer": INFRASTRUCTURE_DISCLAIMER}

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
    except Exception:
        sources = []

    # Deliberately requires BOTH a real summary AND at least one real,
    # citable source — a summary with no grounding sources at all would
    # mean the model didn't actually search for this city, which is
    # exactly the ungrounded-guess case this feature exists to avoid.
    has_data = bool(summary) and len(sources) > 0

    return {
        "has_data": has_data,
        "summary": summary if has_data else "",
        "sources": sources if has_data else [],
        "disclaimer": INFRASTRUCTURE_DISCLAIMER,
    }
