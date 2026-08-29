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


def test_returns_real_grounded_summary_and_sources_when_available():
    fake_response = _mock_grounded_response(
        "- Hyderabad Metro Phase 2 approved, connecting Airport to Old City\n- ORR-linked expressway widening announced for 2027",
        [("Metro Phase 2 news", "https://example-news.com/metro-phase-2"), ("HMDA announcement", "https://hmda.gov.in/announcement")],
    )
    with patch("backend.neighborhood_infrastructure.get_gemini_api_key", return_value="fake_key"):
        with patch("backend.neighborhood_infrastructure.genai.Client") as mock_client_cls:
            mock_client_cls.return_value.models.generate_content.return_value = fake_response
            result = get_infrastructure_summary("Hyderabad")

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
    with patch("backend.neighborhood_infrastructure.get_gemini_api_key", return_value="fake_key"):
        with patch("backend.neighborhood_infrastructure.genai.Client") as mock_client_cls:
            mock_client_cls.return_value.models.generate_content.return_value = fake_response
            result = get_infrastructure_summary("SomeObscureTown")

    assert result["has_data"] is False
    assert result["summary"] == ""
    assert result["sources"] == []


def test_returns_no_data_when_gemini_key_is_not_configured():
    with patch("backend.neighborhood_infrastructure.get_gemini_api_key", return_value=""):
        result = get_infrastructure_summary("Hyderabad")

    assert result["has_data"] is False
    assert result["summary"] == ""
    assert result["sources"] == []
    assert result["disclaimer"] == INFRASTRUCTURE_DISCLAIMER


def test_returns_no_data_for_an_empty_city_without_calling_gemini_at_all():
    with patch("backend.neighborhood_infrastructure.get_gemini_api_key", return_value="fake_key"):
        with patch("backend.neighborhood_infrastructure.genai.Client") as mock_client_cls:
            result = get_infrastructure_summary("   ")
            mock_client_cls.assert_not_called()

    assert result["has_data"] is False


def test_degrades_gracefully_to_no_data_on_a_gemini_api_failure_not_a_crash():
    with patch("backend.neighborhood_infrastructure.get_gemini_api_key", return_value="fake_key"):
        with patch("backend.neighborhood_infrastructure.genai.Client") as mock_client_cls:
            mock_client_cls.return_value.models.generate_content.side_effect = Exception("simulated API failure")
            result = get_infrastructure_summary("Hyderabad")

    assert result["has_data"] is False
    assert result["summary"] == ""


def test_every_result_always_carries_the_disclaimer_regardless_of_outcome():
    """Whether data is found or not, the disclaimer must always be
    present -- the honesty boundary can't be dropped in the success
    path just because the response happens to look complete."""
    with patch("backend.neighborhood_infrastructure.get_gemini_api_key", return_value=""):
        no_key_result = get_infrastructure_summary("Hyderabad")
    assert no_key_result["disclaimer"] == INFRASTRUCTURE_DISCLAIMER

    fake_response = _mock_grounded_response("- Real project", [("Source", "https://example.com")])
    with patch("backend.neighborhood_infrastructure.get_gemini_api_key", return_value="fake_key"):
        with patch("backend.neighborhood_infrastructure.genai.Client") as mock_client_cls:
            mock_client_cls.return_value.models.generate_content.return_value = fake_response
            success_result = get_infrastructure_summary("Hyderabad")
    assert success_result["disclaimer"] == INFRASTRUCTURE_DISCLAIMER


def test_infrastructure_endpoint_is_genuinely_public_no_auth_required():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    with patch("backend.api.get_infrastructure_summary", return_value={"has_data": False, "summary": "", "sources": [], "disclaimer": INFRASTRUCTURE_DISCLAIMER}):
        r = client.get("/api/neighborhood-insights/infrastructure?city=Hyderabad")
    assert r.status_code == 200
