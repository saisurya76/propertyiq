"""Direct unit coverage for backend/report_dynamic_translation.py.

This module was previously exercised only indirectly, through full
multi-language PDF-generation tests (test_agent_intelligence.py's
test_report_uses_real_thai_labels_for_a_thailand_property and similar)
— and since GEMINI_API_KEY is never configured in the test environment,
those tests only ever reached translate_dynamic_strings' no-key
fallback branch, never its real translate-then-parse logic, its
malformed-response fallback, or its partial-response handling. Those
are real, distinct code paths with real failure modes (a bad Gemini
response must never break report generation), so they get their own
direct tests here, mocking the Gemini client the same way
test_property_url_extract.py already does for the same underlying
SDK.
"""

import json
from unittest.mock import MagicMock, patch

from backend.report_dynamic_translation import translate_dynamic_strings, LANGUAGE_NAMES


def _fake_gemini_client(response_text):
    """Same real google-genai SDK shape test_property_url_extract.py's
    own _fake_gemini_client mocks: client.models.generate_content(...)
    returns an object with a .text property."""
    fake_response = MagicMock()
    fake_response.text = response_text
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = fake_response
    return mock_client


def test_translates_every_non_empty_string_via_a_single_batched_call():
    strings = ["Strong buy signal.", "Negotiate on price.", ""]
    fake_response = json.dumps({"0": "Sinal de compra forte.", "1": "Negocie o preço."})

    with patch("backend.report_dynamic_translation.get_gemini_api_key", return_value="fake_key_for_test"), \
         patch("backend.report_dynamic_translation.genai.Client") as mock_client_cls:
        mock_client_cls.return_value = _fake_gemini_client(fake_response)
        result = translate_dynamic_strings(strings, "Portuguese")

    # Exactly one real API call for the whole batch, not one per string.
    mock_client_cls.return_value.models.generate_content.assert_called_once()
    assert result == ["Sinal de compra forte.", "Negocie o preço.", ""]


def test_empty_strings_pass_through_untranslated_without_any_api_call():
    with patch("backend.report_dynamic_translation.genai.Client") as mock_client_cls:
        result = translate_dynamic_strings(["", "   ", ""], "Thai")

    mock_client_cls.assert_not_called()
    assert result == ["", "   ", ""]


def test_all_blank_list_never_even_checks_for_an_api_key():
    """Real cost-saving behavior, matching property_url_extract's own
    skip-the-paid-call-when-unnecessary pattern: nothing to translate
    means get_gemini_api_key should never even be consulted."""
    with patch("backend.report_dynamic_translation.get_gemini_api_key") as mock_get_key, \
         patch("backend.report_dynamic_translation.genai.Client") as mock_client_cls:
        result = translate_dynamic_strings([""], "Vietnamese")

    mock_get_key.assert_not_called()
    mock_client_cls.assert_not_called()
    assert result == [""]


def test_falls_back_to_english_when_no_gemini_key_is_configured():
    strings = ["Recommended.", "Avoid this deal."]
    with patch("backend.report_dynamic_translation.get_gemini_api_key", return_value=""), \
         patch("backend.report_dynamic_translation.genai.Client") as mock_client_cls:
        result = translate_dynamic_strings(strings, "Indonesian")

    mock_client_cls.assert_not_called()
    assert result == strings


def test_falls_back_to_english_on_unparseable_response_rather_than_raising():
    """A report must always generate successfully, with or without
    translation — unlike property_url_extract's own equivalent case
    (which deliberately raises), this one deliberately swallows the
    error, since there's a perfectly good English fallback available."""
    strings = ["Good investment.", "High risk."]
    with patch("backend.report_dynamic_translation.get_gemini_api_key", return_value="fake_key_for_test"), \
         patch("backend.report_dynamic_translation.genai.Client") as mock_client_cls:
        mock_client_cls.return_value = _fake_gemini_client("not valid json at all")
        result = translate_dynamic_strings(strings, "Thai")

    assert result == strings


def test_strips_markdown_code_fences_from_the_response_before_parsing():
    strings = ["Solid deal."]
    fenced_response = "```json\n" + json.dumps({"0": "Đây là một thỏa thuận tốt."}) + "\n```"

    with patch("backend.report_dynamic_translation.get_gemini_api_key", return_value="fake_key_for_test"), \
         patch("backend.report_dynamic_translation.genai.Client") as mock_client_cls:
        mock_client_cls.return_value = _fake_gemini_client(fenced_response)
        result = translate_dynamic_strings(strings, "Vietnamese")

    assert result == ["Đây là một thỏa thuận tốt."]


def test_a_missing_index_in_the_response_keeps_just_that_one_string_in_english():
    """A partial, mostly-successful batch shouldn't discard the parts
    that DID translate correctly — only the specific missing/invalid
    entry should fall back."""
    strings = ["First insight.", "Second insight.", "Third insight."]
    # Response only covers indices 0 and 2 — index 1 is missing entirely.
    partial_response = json.dumps({"0": "Première analyse.", "2": "Troisième analyse."})

    with patch("backend.report_dynamic_translation.get_gemini_api_key", return_value="fake_key_for_test"), \
         patch("backend.report_dynamic_translation.genai.Client") as mock_client_cls:
        mock_client_cls.return_value = _fake_gemini_client(partial_response)
        result = translate_dynamic_strings(strings, "French")

    assert result == ["Première analyse.", "Second insight.", "Troisième analyse."]


def test_a_non_string_value_in_the_response_keeps_the_original_for_that_index():
    """A malformed individual entry (e.g. the model nests a JSON object
    instead of a plain string) must not corrupt the report with a
    non-string value where text is expected -- that one index falls
    back to its original English text, same as a genuinely missing
    entry."""
    strings = ["Fair pricing."]
    weird_response = json.dumps({"0": {"unexpected": "nested object"}})

    with patch("backend.report_dynamic_translation.get_gemini_api_key", return_value="fake_key_for_test"), \
         patch("backend.report_dynamic_translation.genai.Client") as mock_client_cls:
        mock_client_cls.return_value = _fake_gemini_client(weird_response)
        result = translate_dynamic_strings(strings, "Thai")

    assert result == ["Fair pricing."]


def test_language_names_cover_exactly_the_3_supported_report_languages():
    """Matches report_translations.py's own real, deliberate scope
    (Thailand/Vietnam/Indonesia only) -- a drift here would silently
    mistranslate or skip translation for a language this app claims to
    support elsewhere."""
    assert LANGUAGE_NAMES == {"th": "Thai", "vi": "Vietnamese", "id": "Indonesian"}
