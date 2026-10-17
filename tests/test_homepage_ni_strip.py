"""The Neighborhood Insights homepage strip: on by default, admin can hide it
and re-word its sticker, and it is never tied to a paid plan."""
import os

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app  # noqa: E402

client = TestClient(app)
PW = "test-admin-pw"


def test_strip_is_visible_by_default_with_a_sticker():
    assert client.get("/api/homepage-panels/visibility").json()["neighborhood_insights"] is True
    assert client.get("/api/homepage-panels/sticker-text").json()["neighborhood_insights"]


def test_admin_can_hide_the_strip_and_reword_the_sticker_then_restore():
    r = client.post("/api/admin/settings", json={"password": PW,
        "homepage_panel_visibility": {"neighborhood_insights": False},
        "feature_sticker_text": {"neighborhood_insights": "📍 Try it"}})
    assert r.status_code == 200
    assert client.get("/api/homepage-panels/visibility").json()["neighborhood_insights"] is False
    assert client.get("/api/homepage-panels/sticker-text").json()["neighborhood_insights"] == "📍 Try it"
    # other strips untouched
    assert client.get("/api/homepage-panels/visibility").json()["construction_studio"] is True
    client.post("/api/admin/settings", json={"password": PW,
        "homepage_panel_visibility": {"neighborhood_insights": True},
        "feature_sticker_text": {"neighborhood_insights": "🆓 Free Tool"}})
    assert client.get("/api/homepage-panels/visibility").json()["neighborhood_insights"] is True


def test_blank_sticker_keeps_current_text():
    client.post("/api/admin/settings", json={"password": PW, "feature_sticker_text": {"neighborhood_insights": "  "}})
    assert client.get("/api/homepage-panels/sticker-text").json()["neighborhood_insights"].strip()


def test_launch_mode_does_not_hide_it():
    # a free public page: the launch gate only applies to Studio-tied strips
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "frontend/src/App.jsx").read_text()
    assert "homepagePanelVisibility.neighborhood_insights &&" in src
    assert 'stripShown("neighborhood_insights")' not in src
