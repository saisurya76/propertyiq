"""Extracts structured property data from an arbitrary real-estate listing
URL — the property_url_import feature. Fetches the page, strips it down to
visible text, and asks Claude to extract only the fields it can genuinely
find, matching PropertyIQ's own property-form schema.

Honest, deliberate scope limitation, not an oversight: a real listing page
typically only publishes "marketing-side" facts (name, developer, quoted
price, area, location, unit counts) — the fraud-verification fields
PropertyIQ's own form asks for (government guidance value / circle rate,
independently-researched market average, the developer's track record —
projects completed/delayed, years in business, regulatory violations) are
essentially never published on a listing page, because if they were, there
would be no gap for a tool like PropertyIQ to help close in the first
place. This module explicitly extracts only what's genuinely on the page
and returns null for everything else — it must never guess or hallucinate
a value for a field it can't actually find, since a fraud-detection tool
silently inventing its own verification numbers would defeat the entire
point of the product.
"""

import json
import os
import re
from typing import Any, Optional

import requests
from anthropic import Anthropic
from bs4 import BeautifulSoup

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Only fields a real listing page could plausibly publish — the
# verification-specific fields are deliberately excluded from what this
# extractor is even asked to attempt, so there's no risk of it inventing a
# value for something no listing page would ever state.
EXTRACTABLE_FIELDS = [
    "propertyName",
    "developerName",
    "propertyType",
    "city",
    "location",
    "quotedPrice",
    "areaValue",
    "areaUnit",
    "totalUnits",
    "monthlyRent",
]

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def fetch_page_text(url: str, timeout: int = 12) -> str:
    """Fetches a URL and returns its visible text content, script/style
    stripped. Raises requests.RequestException on network failure, or
    ValueError if the response isn't real HTML — both are meant to be
    caught by the caller and turned into a clear, honest error message
    rather than silently returning nothing."""
    response = requests.get(url, headers={"User-Agent": _UA}, timeout=timeout)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    if "html" not in content_type.lower():
        raise ValueError(f"URL did not return an HTML page (Content-Type: {content_type})")

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    text = re.sub(r"\n{2,}", "\n", text).strip()
    return text


def extract_property_data(url: str) -> dict[str, Any]:
    """Fetches the given URL and asks Claude to extract whichever of
    EXTRACTABLE_FIELDS it can genuinely find on the page. Returns a dict
    with exactly those keys — any field not found is explicitly None, not
    omitted, so the caller always knows the full set of fields that were
    attempted. Raises on fetch failure or if the extraction call itself
    fails; does not silently return an empty/guessed result."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured on the backend.")

    page_text = fetch_page_text(url)
    # A very short page is a strong signal the fetch didn't get real
    # listing content (a login wall, a bot-block page, a redirect stub) —
    # worth failing clearly here rather than sending near-empty content to
    # the model and getting an all-null result that looks like "nothing
    # found" when it's really "couldn't access the real page".
    if len(page_text) < 200:
        raise ValueError(
            "The page returned very little content — it may require sign-in, "
            "block automated access, or the URL may not point directly to a listing."
        )

    # Real pages can be very long; keep this bounded so a single request
    # stays reasonably fast and cheap regardless of page size.
    page_text = page_text[:15000]

    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = f"""You are extracting structured data from a real-estate listing page's text content. Below is the visible text of a property listing page.

Extract ONLY these fields, and ONLY if the value is genuinely, explicitly present in the text below. Do NOT guess, estimate, or infer a value that isn't actually stated. If a field isn't clearly present, its value MUST be null.

Fields to extract:
- propertyName: the name of the specific property/project (string or null)
- developerName: the real estate developer/builder's name (string or null)
- propertyType: one of "Apartment", "Villa", "Plot", "Commercial" if clearly stated, else null
- city: the city the property is in (string or null)
- location: the specific locality/neighborhood (string or null)
- quotedPrice: the listed/asking price, as a plain number with no currency symbols or commas (number or null)
- areaValue: the property's area/size, as a plain number (number or null)
- areaUnit: "sqft" or "sqm" — whichever unit the area was stated in (string or null)
- totalUnits: total number of units in the project, if stated (number or null)
- monthlyRent: monthly rent, if this is a rental listing (number or null)

Respond with ONLY a single JSON object with exactly these 10 keys, no other text, no markdown code fences.

Page text:
{page_text}"""

    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Extraction did not return valid JSON: {raw[:200]}") from exc

    # Always return exactly EXTRACTABLE_FIELDS keys, regardless of what the
    # model actually included — a field the model omitted (rather than
    # explicitly nulling) still comes back as None, never silently missing.
    return {field: parsed.get(field) for field in EXTRACTABLE_FIELDS}
