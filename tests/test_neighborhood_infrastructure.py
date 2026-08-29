from unittest.mock import MagicMock, patch

from backend.neighborhood_infrastructure import get_infrastructure_summary, INFRASTRUCTURE_DISCLAIMER


def _mock_grounded_response(text, sources):
    """Builds a fake Gemini response matching the real SDK's shape
    (response.text, response.candidates[i].grounding_metadata.grounding_chunks[j].web.{title,uri}),
    so these tests exercise the actual parsing logic, not a simplified stand-in."""
    response = MagicMock()
    response.text = text

    chunks = []
    for title, uri in sources:
        chunk = MagicMock()
        chunk.web.title = title
        chunk.web.uri = uri
        chunks.append(chunk)

    candidate = MagicMock()
    candidate.grounding_metadata.grounding_chunks = chunks
    response.candidates = [candidate]
    return response


# Results are now cached per city for 24h against the real, shared
# app_config database table (see neighborhood_infrastructure.py's own
# module docstring for why). To keep these tests independent of each
# other and of whatever ran before them, every test that isn't
# specifically testing the cache itself uses its own unique city name
# — a real, necessary test-isolation fix: an earlier test's cached
# success previously leaked into a later test expecting a totally
# different code path (e.g. no_api_key), since both used "Hyderabad."
# Also patches get_app_setting/set_app_setting directly so these tests
# never depend on real cache state left over from a previous run.


def test_returns_real_grounded_summary_and_sources_when_available():
    fake_response = _mock_grounded_response(
        "- Hyderabad Metro Phase 2 approved, connecting Airport to Old City\n- ORR-linked expressway widening announced for 2027",
        [("Metro Phase 2 news", "https://example-news.com/metro-phase-2"), ("HMDA announcement", "https://hmda.gov.in/announcement")],
    )
    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=None), \
         patch("backend.neighborhood_infrastructure.set_app_setting"), \
         patch("backend.neighborhood_infrastructure.get_gemini_api_key", return_value="fake_key"), \
         patch("backend.neighborhood_infrastructure.genai.Client") as mock_client_cls:
        mock_client_cls.return_value.models.generate_content.return_value = fake_response
        result = get_infrastructure_summary("TestCity_grounded_success")

    assert result["has_data"] is True
    assert "Metro Phase 2" in result["summary"]
    assert len(result["sources"]) == 2
    assert result["sources"][0]["uri"] == "https://example-news.com/metro-phase-2"
    assert result["disclaimer"] == INFRASTRUCTURE_DISCLAIMER


def test_honestly_reports_no_data_when_grounding_returns_no_sources():
    """The real, important honesty guarantee: a summary with text but
    zero real grounding sources means the model didn't actually search
    for this city -- exactly the ungrounded-guess case this feature
    exists to prevent, so it must not be treated as real data."""
    fake_response = _mock_grounded_response("Some generic-sounding text with no real citations.", [])
    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=None), \
         patch("backend.neighborhood_infrastructure.set_app_setting"), \
         patch("backend.neighborhood_infrastructure.get_gemini_api_key", return_value="fake_key"), \
         patch("backend.neighborhood_infrastructure.genai.Client") as mock_client_cls:
        mock_client_cls.return_value.models.generate_content.return_value = fake_response
        result = get_infrastructure_summary("SomeObscureTown")

    assert result["has_data"] is False
    assert result["summary"] == ""
    assert result["sources"] == []
    assert result["reason"] == "no_grounded_sources"


def test_returns_no_data_when_gemini_key_is_not_configured():
    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=None), \
         patch("backend.neighborhood_infrastructure.get_gemini_api_key", return_value=""):
        result = get_infrastructure_summary("TestCity_no_key")

    assert result["has_data"] is False
    assert result["summary"] == ""
    assert result["sources"] == []
    assert result["disclaimer"] == INFRASTRUCTURE_DISCLAIMER
    assert result["reason"] == "no_api_key"


def test_returns_no_data_for_an_empty_city_without_calling_gemini_at_all():
    with patch("backend.neighborhood_infrastructure.get_gemini_api_key", return_value="fake_key"):
        with patch("backend.neighborhood_infrastructure.genai.Client") as mock_client_cls:
            result = get_infrastructure_summary("   ")
            mock_client_cls.assert_not_called()

    assert result["has_data"] is False


def test_degrades_gracefully_to_no_data_on_a_gemini_api_failure_not_a_crash():
    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=None), \
         patch("backend.neighborhood_infrastructure.get_gemini_api_key", return_value="fake_key"), \
         patch("backend.neighborhood_infrastructure.genai.Client") as mock_client_cls:
        mock_client_cls.return_value.models.generate_content.side_effect = Exception("simulated API failure")
        result = get_infrastructure_summary("TestCity_api_failure")

    assert result["has_data"] is False
    assert result["summary"] == ""
    assert result["reason"] == "api_error"


def test_a_real_api_failure_is_distinguishable_from_a_missing_key_via_reason_and_error_detail():
    """The exact real bug this fixes: a missing GEMINI_API_KEY and a
    genuine Gemini API exception previously both produced the identical
    no-data response, making a real misconfiguration indistinguishable
    from an honest empty result. Confirms these two cases now carry
    different `reason` codes, and the real exception text is preserved
    in `error_detail` for the api_error case specifically (never
    fabricated, never present on the no_api_key case, which has no
    real exception to report)."""
    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=None), \
         patch("backend.neighborhood_infrastructure.get_gemini_api_key", return_value=""):
        no_key_result = get_infrastructure_summary("TestCity_distinguish_1")
    assert no_key_result["reason"] == "no_api_key"
    assert no_key_result["error_detail"] == ""

    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=None), \
         patch("backend.neighborhood_infrastructure.get_gemini_api_key", return_value="fake_key"), \
         patch("backend.neighborhood_infrastructure.genai.Client") as mock_client_cls:
        mock_client_cls.return_value.models.generate_content.side_effect = Exception("401 Unauthorized: invalid API key")
        api_error_result = get_infrastructure_summary("TestCity_distinguish_2")
    assert api_error_result["reason"] == "api_error"
    assert "401 Unauthorized" in api_error_result["error_detail"]

    assert no_key_result["reason"] != api_error_result["reason"]


def test_every_result_always_carries_the_disclaimer_regardless_of_outcome():
    """Whether data is found or not, the disclaimer must always be
    present -- the honesty boundary can't be dropped in the success
    path just because the response happens to look complete."""
    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=None), \
         patch("backend.neighborhood_infrastructure.get_gemini_api_key", return_value=""):
        no_key_result = get_infrastructure_summary("TestCity_disclaimer_1")
    assert no_key_result["disclaimer"] == INFRASTRUCTURE_DISCLAIMER

    fake_response = _mock_grounded_response("- Real project", [("Source", "https://example.com")])
    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=None), \
         patch("backend.neighborhood_infrastructure.set_app_setting"), \
         patch("backend.neighborhood_infrastructure.get_gemini_api_key", return_value="fake_key"), \
         patch("backend.neighborhood_infrastructure.genai.Client") as mock_client_cls:
        mock_client_cls.return_value.models.generate_content.return_value = fake_response
        success_result = get_infrastructure_summary("TestCity_disclaimer_2")
    assert success_result["disclaimer"] == INFRASTRUCTURE_DISCLAIMER


def test_infrastructure_endpoint_is_genuinely_public_no_auth_required():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    with patch("backend.api.get_infrastructure_summary", return_value={"has_data": False, "summary": "", "sources": [], "disclaimer": INFRASTRUCTURE_DISCLAIMER}):
        r = client.get("/api/neighborhood-insights/infrastructure?city=TestCity_endpoint_public")
    assert r.status_code == 200


def test_a_gemini_quota_error_is_distinguished_from_a_generic_api_error():
    """The exact real bug the user hit: a 429 RESOURCE_EXHAUSTED quota
    error (confirmed directly from real Render logs, not a hypothetical)
    was previously indistinguishable from both a genuine "no news for
    this city" result and any other API failure. Confirms it now gets
    its own distinct reason code, so the frontend can tell the user this
    is a temporary, site-wide limit rather than implying the city itself
    has no infrastructure news."""
    real_quota_error_text = (
        "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, "
        "please check your plan and billing details.', 'status': 'RESOURCE_EXHAUSTED'}}"
    )
    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=None), \
         patch("backend.neighborhood_infrastructure.get_gemini_api_key", return_value="fake_key"), \
         patch("backend.neighborhood_infrastructure.genai.Client") as mock_client_cls:
        mock_client_cls.return_value.models.generate_content.side_effect = Exception(real_quota_error_text)
        result = get_infrastructure_summary("TestCity_quota_error")

    assert result["has_data"] is False
    assert result["reason"] == "quota_exceeded"
    assert "RESOURCE_EXHAUSTED" in result["error_detail"]


def test_a_non_quota_api_error_still_gets_the_generic_api_error_reason():
    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=None), \
         patch("backend.neighborhood_infrastructure.get_gemini_api_key", return_value="fake_key"), \
         patch("backend.neighborhood_infrastructure.genai.Client") as mock_client_cls:
        mock_client_cls.return_value.models.generate_content.side_effect = Exception("500 Internal Server Error")
        result = get_infrastructure_summary("TestCity_non_quota_error")

    assert result["reason"] == "api_error"


def test_a_cached_success_is_returned_without_calling_gemini_again():
    """The real point of caching: a second lookup for the same city
    within 24h must not consume another (scarce, per the quota-routing
    issue this exists to mitigate) Gemini request at all."""
    cached_result = {
        "has_data": True, "summary": "- Cached project", "sources": [{"title": "Cached source", "uri": "https://example.com/cached"}],
        "disclaimer": INFRASTRUCTURE_DISCLAIMER, "reason": "", "error_detail": "",
    }
    import json
    from datetime import datetime, timezone
    cached_json = json.dumps({"result": cached_result, "fetched_at": datetime.now(timezone.utc).isoformat()})

    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=cached_json), \
         patch("backend.neighborhood_infrastructure.genai.Client") as mock_client_cls:
        result = get_infrastructure_summary("TestCity_cache_hit")
        mock_client_cls.assert_not_called()

    assert result == cached_result


def test_a_quota_exceeded_result_is_never_cached():
    """A real, deliberate choice: caching a transient failure would
    "stick" it for a full day even after Google's own issue clears —
    worse than just re-trying (and re-hitting the same small quota
    bucket) on the next genuine request."""
    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=None), \
         patch("backend.neighborhood_infrastructure.set_app_setting") as mock_set, \
         patch("backend.neighborhood_infrastructure.get_gemini_api_key", return_value="fake_key"), \
         patch("backend.neighborhood_infrastructure.genai.Client") as mock_client_cls:
        mock_client_cls.return_value.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED")
        get_infrastructure_summary("TestCity_no_cache_on_quota_error")

    mock_set.assert_not_called()


def test_uses_the_same_model_confirmed_working_in_accidentiq():
    """gemini-flash-latest (this module's original model) was swapped
    for gemini-3.5-flash-lite -- the exact model confirmed directly from
    AccidentIQ's own real source (lib/aiProviderClient.js) to work
    without hitting the Search-grounding quota-routing issue. Grounding
    itself stays enabled here (unlike AccidentIQ's own calls, which
    never use it at all) -- this fixes the concrete, testable model
    difference without dropping the real-search safeguard this feature
    exists for."""
    fake_response = _mock_grounded_response("- Real project", [("Source", "https://example.com")])
    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=None), \
         patch("backend.neighborhood_infrastructure.set_app_setting"), \
         patch("backend.neighborhood_infrastructure.get_gemini_api_key", return_value="fake_key"), \
         patch("backend.neighborhood_infrastructure.genai.Client") as mock_client_cls:
        mock_client_cls.return_value.models.generate_content.return_value = fake_response
        get_infrastructure_summary("TestCity_model_check")

    call_kwargs = mock_client_cls.return_value.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-3.5-flash-lite"
    # Grounding must still be enabled -- confirms this is a model swap,
    # not a quiet removal of the real-search safeguard.
    assert call_kwargs["config"].tools[0].google_search is not None
