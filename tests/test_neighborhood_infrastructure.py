from unittest.mock import patch

from backend.neighborhood_infrastructure import get_infrastructure_summary, INFRASTRUCTURE_DISCLAIMER

# Results are cached per city for 24h against the real, shared
# app_config database table (see neighborhood_infrastructure.py's own
# module docstring for why). To keep these tests independent of each
# other and of whatever ran before them, every test that isn't
# specifically testing the cache itself uses its own unique city name,
# and explicitly mocks get_app_setting/set_app_setting so tests never
# depend on real leftover cache state — a real test-isolation bug hit
# in an earlier version of this file (a shared "Hyderabad" across
# tests let one test's cached success leak into a later test expecting
# a totally different scenario).


def _mock_tavily_response(answer, results):
    """Builds a response matching Tavily's own real shape (a dict with
    'answer' and 'results': [{'title', 'url', ...}]), confirmed
    directly against the installed tavily-python package's real
    TavilyClient.search() return type."""
    return {"answer": answer, "results": [{"title": t, "url": u} for t, u in results]}


def test_returns_real_answer_and_sources_when_available():
    fake_response = _mock_tavily_response(
        "Hyderabad Metro Phase 2 has been approved, extending service toward the airport, alongside ORR-linked expressway widening planned for 2027.",
        [("Metro Phase 2 news", "https://example-news.com/metro-phase-2"), ("HMDA announcement", "https://hmda.gov.in/announcement")],
    )
    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=None), \
         patch("backend.neighborhood_infrastructure.set_app_setting"), \
         patch("backend.neighborhood_infrastructure.TAVILY_API_KEY", "fake_key"), \
         patch("backend.neighborhood_infrastructure.TavilyClient") as mock_client_cls:
        mock_client_cls.return_value.search.return_value = fake_response
        result = get_infrastructure_summary("TestCity_tavily_success")

    assert result["has_data"] is True
    assert "Metro Phase 2" in result["summary"]
    assert len(result["sources"]) == 2
    assert result["sources"][0]["uri"] == "https://example-news.com/metro-phase-2"
    assert result["disclaimer"] == INFRASTRUCTURE_DISCLAIMER


def test_sends_a_real_india_scoped_query_with_expected_tavily_parameters():
    """Confirms the actual call passed to Tavily uses the real,
    intended parameters -- news topic, India country boost, and
    include_answer so a synthesized summary comes back in the same
    call rather than needing a separate LLM step."""
    fake_response = _mock_tavily_response("Some answer", [("Source", "https://example.com")])
    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=None), \
         patch("backend.neighborhood_infrastructure.set_app_setting"), \
         patch("backend.neighborhood_infrastructure.TAVILY_API_KEY", "fake_key"), \
         patch("backend.neighborhood_infrastructure.TavilyClient") as mock_client_cls:
        mock_client_cls.return_value.search.return_value = fake_response
        get_infrastructure_summary("Hyderabad")

    call_kwargs = mock_client_cls.return_value.search.call_args.kwargs
    assert "Hyderabad" in call_kwargs["query"]
    assert "India" in call_kwargs["query"]
    assert call_kwargs["topic"] == "news"
    assert call_kwargs["country"] == "india"
    assert call_kwargs["include_answer"] is True


def test_honestly_reports_no_data_when_search_returns_no_sources():
    """The real, important honesty guarantee: an answer with zero real
    source URLs means the search didn't actually ground anything --
    must not be treated as real data even if Tavily returned some
    answer text."""
    fake_response = _mock_tavily_response("Some generic-sounding text with no real citations.", [])
    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=None), \
         patch("backend.neighborhood_infrastructure.set_app_setting"), \
         patch("backend.neighborhood_infrastructure.TAVILY_API_KEY", "fake_key"), \
         patch("backend.neighborhood_infrastructure.TavilyClient") as mock_client_cls:
        mock_client_cls.return_value.search.return_value = fake_response
        result = get_infrastructure_summary("SomeObscureTown")

    assert result["has_data"] is False
    assert result["summary"] == ""
    assert result["sources"] == []
    assert result["reason"] == "no_grounded_sources"


def test_honestly_reports_no_data_when_there_is_no_answer_even_with_sources():
    """The reverse honesty case: real source URLs with no synthesized
    answer text still doesn't count as usable data for this feature."""
    fake_response = _mock_tavily_response("", [("Source", "https://example.com")])
    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=None), \
         patch("backend.neighborhood_infrastructure.set_app_setting"), \
         patch("backend.neighborhood_infrastructure.TAVILY_API_KEY", "fake_key"), \
         patch("backend.neighborhood_infrastructure.TavilyClient") as mock_client_cls:
        mock_client_cls.return_value.search.return_value = fake_response
        result = get_infrastructure_summary("TestCity_no_answer")

    assert result["has_data"] is False
    assert result["reason"] == "no_grounded_sources"


def test_returns_no_data_when_tavily_key_is_not_configured():
    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=None), \
         patch("backend.neighborhood_infrastructure.TAVILY_API_KEY", ""):
        result = get_infrastructure_summary("TestCity_no_key")

    assert result["has_data"] is False
    assert result["reason"] == "no_api_key"
    assert result["disclaimer"] == INFRASTRUCTURE_DISCLAIMER


def test_returns_no_data_for_an_empty_city_without_calling_tavily_at_all():
    with patch("backend.neighborhood_infrastructure.TAVILY_API_KEY", "fake_key"), \
         patch("backend.neighborhood_infrastructure.TavilyClient") as mock_client_cls:
        result = get_infrastructure_summary("   ")
        mock_client_cls.assert_not_called()

    assert result["has_data"] is False


def test_degrades_gracefully_to_no_data_on_a_tavily_api_failure_not_a_crash():
    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=None), \
         patch("backend.neighborhood_infrastructure.TAVILY_API_KEY", "fake_key"), \
         patch("backend.neighborhood_infrastructure.TavilyClient") as mock_client_cls:
        mock_client_cls.return_value.search.side_effect = Exception("simulated API failure")
        result = get_infrastructure_summary("TestCity_api_failure")

    assert result["has_data"] is False
    assert result["reason"] == "api_error"
    assert "simulated API failure" in result["error_detail"]


def test_a_quota_related_failure_is_distinguished_from_a_generic_api_error():
    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=None), \
         patch("backend.neighborhood_infrastructure.TAVILY_API_KEY", "fake_key"), \
         patch("backend.neighborhood_infrastructure.TavilyClient") as mock_client_cls:
        mock_client_cls.return_value.search.side_effect = Exception("429 usage limit exceeded, please upgrade your plan")
        result = get_infrastructure_summary("TestCity_quota_error")

    assert result["reason"] == "quota_exceeded"


def test_every_result_always_carries_the_disclaimer_regardless_of_outcome():
    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=None), \
         patch("backend.neighborhood_infrastructure.TAVILY_API_KEY", ""):
        no_key_result = get_infrastructure_summary("TestCity_disclaimer_1")
    assert no_key_result["disclaimer"] == INFRASTRUCTURE_DISCLAIMER

    fake_response = _mock_tavily_response("Real project", [("Source", "https://example.com")])
    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=None), \
         patch("backend.neighborhood_infrastructure.set_app_setting"), \
         patch("backend.neighborhood_infrastructure.TAVILY_API_KEY", "fake_key"), \
         patch("backend.neighborhood_infrastructure.TavilyClient") as mock_client_cls:
        mock_client_cls.return_value.search.return_value = fake_response
        success_result = get_infrastructure_summary("TestCity_disclaimer_2")
    assert success_result["disclaimer"] == INFRASTRUCTURE_DISCLAIMER


def test_infrastructure_endpoint_is_genuinely_public_no_auth_required():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    with patch("backend.api.get_infrastructure_summary", return_value={"has_data": False, "summary": "", "sources": [], "disclaimer": INFRASTRUCTURE_DISCLAIMER}):
        r = client.get("/api/neighborhood-insights/infrastructure?city=TestCity_endpoint_public")
    assert r.status_code == 200


def test_a_cached_success_is_returned_without_calling_tavily_again():
    """The real point of caching: a second lookup for the same city
    within 24h must not consume another search credit at all."""
    cached_result = {
        "has_data": True, "summary": "Cached project info", "sources": [{"title": "Cached source", "uri": "https://example.com/cached"}],
        "disclaimer": INFRASTRUCTURE_DISCLAIMER, "reason": "", "error_detail": "",
    }
    import json
    from datetime import datetime, timezone
    cached_json = json.dumps({"result": cached_result, "fetched_at": datetime.now(timezone.utc).isoformat()})

    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=cached_json), \
         patch("backend.neighborhood_infrastructure.TavilyClient") as mock_client_cls:
        result = get_infrastructure_summary("TestCity_cache_hit")
        mock_client_cls.assert_not_called()

    assert result == cached_result


def test_a_failed_result_is_never_cached():
    with patch("backend.neighborhood_infrastructure.get_app_setting", return_value=None), \
         patch("backend.neighborhood_infrastructure.set_app_setting") as mock_set, \
         patch("backend.neighborhood_infrastructure.TAVILY_API_KEY", "fake_key"), \
         patch("backend.neighborhood_infrastructure.TavilyClient") as mock_client_cls:
        mock_client_cls.return_value.search.side_effect = Exception("simulated failure")
        get_infrastructure_summary("TestCity_no_cache_on_failure")

    mock_set.assert_not_called()
