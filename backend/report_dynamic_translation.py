"""Real, live translation for the handful of dynamically-generated
narrative strings an agent report shows (the assessment engine's own
recommendation text, decision narrative, deal-quality/negotiation/
buyer-advantage reasoning) — the part report_translations.py's static
dictionary genuinely can't cover, since this text is generated fresh
per property, not known ahead of time.

Reuses this app's own existing, already-configured Gemini integration
(same get_gemini_api_key() property_url_extract.py already uses — an
admin-set key, with an env-var fallback) rather than adding a new
service or a new API key to manage. Batches every string that needs
translating into a single real API call per report, not one call per
string, to keep this bounded and fast. Falls back to the original
English text — for the whole batch — on any real failure (no API key
configured, a bad/unparseable response, a network error): a report
must always generate successfully, with or without translation.
"""

import json
import logging
import re
from typing import Optional

from google import genai

from backend.property_url_extract import get_gemini_api_key

logger = logging.getLogger(__name__)


def translate_dynamic_strings(strings: list[str], target_language_name: str) -> list[str]:
    """strings in, same-length list out — either genuinely translated,
    or (on any failure) the exact original strings, so a caller never
    has to branch on whether translation actually happened. Empty
    strings pass through unchanged rather than being sent to the API."""
    non_empty_indices = [i for i, s in enumerate(strings) if s and s.strip()]
    if not non_empty_indices:
        return list(strings)

    gemini_api_key = get_gemini_api_key()
    if not gemini_api_key:
        logger.warning("translate_dynamic_strings: Gemini API key is not configured — report falls back to English.")
        return list(strings)

    to_translate = {str(i): strings[i] for i in non_empty_indices}
    prompt = f"""Translate each value in this JSON object into {target_language_name}. Keep the same real estate/financial terminology tone as the source. Do not add commentary, explanations, or extra text — translate only.

Respond with ONLY a single JSON object with the exact same keys, each mapped to its translation. No markdown code fences, no other text.

{json.dumps(to_translate, ensure_ascii=False)}"""

    try:
        client = genai.Client(api_key=gemini_api_key)
        response = client.models.generate_content(model="gemini-flash-latest", contents=prompt)
        raw = (response.text or "").strip()
        raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.MULTILINE).strip()
        translated = json.loads(raw)
    except Exception as exc:
        logger.error(f"translate_dynamic_strings: translation failed, falling back to English: {exc}")
        return list(strings)

    result = list(strings)
    for i in non_empty_indices:
        value = translated.get(str(i))
        if isinstance(value, str) and value.strip():
            result[i] = value
        # A missing/invalid entry for this one index keeps the
        # original English string for just that item, rather than
        # discarding the rest of a mostly-successful batch.
    return result


# Real, human-readable target names for the prompt above — matching
# report_translations.py's own 3 supported languages.
LANGUAGE_NAMES = {"th": "Thai", "vi": "Vietnamese", "id": "Indonesian"}
