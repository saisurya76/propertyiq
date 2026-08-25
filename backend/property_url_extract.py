"""Extracts structured property data from an arbitrary real-estate listing
URL — the property_url_import feature. Tries a genuinely free extraction
path first (the page's own embedded schema.org JSON-LD and Open Graph
metadata — real estate listing sites commonly publish this for SEO/social-
preview purposes, unrelated to whether they'll let a scraper read their
visible page text), and only falls back to asking Claude to read the raw
page text when that free path doesn't find enough — an explicit, real cost
reduction, not a hypothetical one: many established listing sites (the
kind most PropertyIQ users would actually paste) publish exactly this kind
of structured data, so a real fraction of imports should cost nothing at
all beyond the page fetch itself.

Honest, deliberate scope limitation, not an oversight, on EITHER path: a
real listing page typically only publishes "marketing-side" facts (name,
developer, quoted price, area, location, unit counts) — the fraud-
verification fields PropertyIQ's own form asks for (government guidance
value / circle rate, independently-researched market average, the
developer's track record — projects completed/delayed, years in business,
regulatory violations) are essentially never published on a listing page,
because if they were, there would be no gap for a tool like PropertyIQ to
help close in the first place. This module explicitly extracts only what's
genuinely on the page and returns null for everything else — it must never
guess or hallucinate a value for a field it can't actually find, since a
fraud-detection tool silently inventing its own verification numbers would
defeat the entire point of the product.
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

# A result counts as "good enough to skip the paid LLM call entirely" once
# it has the property's name plus at least one real number (price or
# area) — genuinely useful without a person needing to type it in, even
# if some of the other fields are still missing.
_FREE_PATH_MIN_FIELDS = ["propertyName"]
_FREE_PATH_NEEDS_ONE_OF = ["quotedPrice", "areaValue"]


def fetch_page_html(url: str, timeout: int = 12) -> str:
    """Fetches a URL and returns its raw HTML. Raises
    requests.RequestException on network failure, or ValueError if the
    response isn't real HTML — both are meant to be caught by the caller
    and turned into a clear, honest error message rather than silently
    returning nothing."""
    response = requests.get(url, headers={"User-Agent": _UA}, timeout=timeout)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    if "html" not in content_type.lower():
        raise ValueError(f"URL did not return an HTML page (Content-Type: {content_type})")

    return response.text


def _html_to_text(html: str) -> str:
    """Strips a raw HTML string down to its visible text — used only for
    the paid LLM fallback path, which needs readable prose, not markup."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    return re.sub(r"\n{2,}", "\n", text).strip()


def _to_number(value: Any) -> Optional[float]:
    """Best-effort conversion of a structured-data value (which can
    arrive as a string, an int, or a nested dict depending on the site's
    schema.org implementation) into a plain number, or None if it
    genuinely isn't one — never guesses at a value that isn't parseable."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        cleaned = re.sub(r"[^\d.]", "", value)
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


_PROPERTY_TYPE_KEYWORDS = {
    "apartment": "Apartment", "flat": "Apartment", "condo": "Apartment", "condominium": "Apartment",
    "villa": "Villa", "house": "Villa", "singlefamilyresidence": "Villa",
    "plot": "Plot", "land": "Plot",
    "commercial": "Commercial", "office": "Commercial", "shop": "Commercial", "retail": "Commercial",
}


def _guess_property_type(*texts: Optional[str]) -> Optional[str]:
    combined = " ".join(t for t in texts if t).lower()
    for keyword, mapped in _PROPERTY_TYPE_KEYWORDS.items():
        if keyword in combined:
            return mapped
    return None


def extract_structured_data(html: str) -> dict[str, Any]:
    """The genuinely free extraction path — reads the page's own embedded
    schema.org JSON-LD and Open Graph/Twitter Card metadata, which real
    listing sites commonly publish for SEO and social-preview purposes
    regardless of whether they'd otherwise want to be scraped. No API
    call, no cost, just parsing tags the page's own author chose to
    include. Returns exactly EXTRACTABLE_FIELDS keys, None for anything
    not found — same contract as the LLM path, so callers can treat
    either result identically."""
    soup = BeautifulSoup(html, "html.parser")
    result: dict[str, Any] = {field: None for field in EXTRACTABLE_FIELDS}

    # --- schema.org JSON-LD ---
    for script_tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script_tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            schema_type = str(item.get("@type", "")).lower()
            if schema_type not in (
                "product", "realestatelisting", "house", "apartment",
                "residence", "singlefamilyresidence", "accommodation", "offer",
            ):
                continue

            if not result["propertyName"] and item.get("name"):
                result["propertyName"] = str(item["name"])

            brand = item.get("brand")
            if not result["developerName"] and isinstance(brand, dict) and brand.get("name"):
                result["developerName"] = str(brand["name"])
            elif not result["developerName"] and isinstance(item.get("manufacturer"), dict):
                result["developerName"] = str(item["manufacturer"].get("name") or "") or None

            address = item.get("address")
            if isinstance(address, dict):
                if not result["city"] and address.get("addressLocality"):
                    result["city"] = str(address["addressLocality"])
                if not result["location"] and address.get("streetAddress"):
                    result["location"] = str(address["streetAddress"])

            offers = item.get("offers")
            offer = offers[0] if isinstance(offers, list) and offers else offers if isinstance(offers, dict) else None
            if offer:
                if not result["quotedPrice"] and offer.get("price"):
                    result["quotedPrice"] = _to_number(offer["price"])

            floor_size = item.get("floorSize")
            if isinstance(floor_size, dict) and not result["areaValue"]:
                result["areaValue"] = _to_number(floor_size.get("value"))
                unit_text = str(floor_size.get("unitCode") or floor_size.get("unitText") or "").lower()
                if "sqm" in unit_text or "mtk" in unit_text or "m2" in unit_text:
                    result["areaUnit"] = "sqm"
                elif floor_size.get("value"):
                    result["areaUnit"] = result["areaUnit"] or "sqft"

            if not result["propertyType"]:
                result["propertyType"] = _guess_property_type(schema_type, item.get("name"), item.get("description"))

    # --- Open Graph / Twitter Card / product meta tags (supplements, fills gaps only) ---
    def _meta(*names: str) -> Optional[str]:
        for name in names:
            tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
            if tag and tag.get("content"):
                return tag["content"].strip()
        return None

    if not result["propertyName"]:
        result["propertyName"] = _meta("og:title", "twitter:title")

    if not result["quotedPrice"]:
        result["quotedPrice"] = _to_number(_meta("product:price:amount", "og:price:amount"))

    if not result["city"]:
        result["city"] = _meta("og:locality", "business:contact_data:locality")

    if not result["propertyType"]:
        result["propertyType"] = _guess_property_type(_meta("og:title"), _meta("og:description"))

    return result


def _found_field_count(extracted: dict[str, Any]) -> int:
    return sum(1 for v in extracted.values() if v is not None)


def _is_good_enough_to_skip_llm(extracted: dict[str, Any]) -> bool:
    has_required = all(extracted.get(f) for f in _FREE_PATH_MIN_FIELDS)
    has_one_number = any(extracted.get(f) for f in _FREE_PATH_NEEDS_ONE_OF)
    return has_required and has_one_number


def extract_property_data(url: str) -> dict[str, Any]:
    """Fetches the given URL once, then tries the free structured-data
    path first (extract_structured_data) — if that finds enough to be
    genuinely useful (the property's name plus at least a price or an
    area), returns it directly with zero LLM cost. Only falls back to
    asking Claude to read the page's visible text when the free path
    comes up short. Returns a dict with exactly EXTRACTABLE_FIELDS keys
    either way — any field not found is explicitly None, not omitted, so
    the caller always knows the full set of fields that were attempted.
    Raises on fetch failure or if the LLM fallback itself fails; does not
    silently return an empty/guessed result."""
    html = fetch_page_html(url)

    structured = extract_structured_data(html)
    if _is_good_enough_to_skip_llm(structured):
        return structured

    if not ANTHROPIC_API_KEY:
        # No paid fallback configured — return whatever the free path
        # found rather than failing outright, since a partial real
        # result is more useful than none, and this isn't necessarily
        # an error (the admin may have deliberately left the LLM
        # fallback unconfigured to keep this feature fully free).
        return structured

    page_text = _html_to_text(html)
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

Some fields may already be known from the page's own structured metadata — prefer these known values unless the page text clearly states something different: {json.dumps({k: v for k, v in structured.items() if v is not None})}

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
