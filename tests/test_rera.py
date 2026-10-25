import os

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from datetime import date  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app  # noqa: E402
from backend.auth_store import create_otp  # noqa: E402
from backend import rera  # noqa: E402
from backend.config_store import (  # noqa: E402
    get_free_features, set_free_features, user_has_feature, ensure_default_free_features,
    set_app_setting, RERA_FREE_MIGRATION_KEY,
)

client = TestClient(app)
PW = "test-admin-pw"


def _headers(email):
    code = create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    return {"Authorization": f"Bearer {r.json()['session_token']}"}


def test_states_are_public_and_have_portal_links():
    r = client.get("/api/rera/states").json()
    codes = {s["code"] for s in r["states"]}
    assert {"MH", "KA", "TS", "GA"} <= codes
    assert all(s["portal_url"].startswith("https://") for s in r["states"])
    assert "not a verification" in r["disclaimer"]


def test_check_requires_sign_in():
    assert client.post("/api/rera/check", json={"state": "MH", "registration_number": "P51700012345"}).status_code in (401, 403)


def test_signed_in_user_gets_guidance_never_verified():
    set_free_features(["rera_verification"])
    h = _headers("rerauser@example.com")
    r = client.post("/api/rera/check", headers=h, json={"state": "MH", "registration_number": "P51700012345"})
    assert r.status_code == 200
    body = r.json()
    assert body["verified"] is False
    assert body["state"]["portal_url"].startswith("https://")
    assert body["checklist"] and body["format_check"]["level"] == "ok"


def test_blocked_when_admin_turns_it_off():
    set_free_features([])
    h = _headers("rerablocked@example.com")
    r = client.post("/api/rera/check", headers=h, json={"state": "MH", "registration_number": "P51700012345"})
    assert r.status_code == 403
    set_free_features(["rera_verification"])


def test_bad_inputs():
    set_free_features(["rera_verification"])
    h = _headers("rerabad@example.com")
    assert client.post("/api/rera/check", headers=h, json={"state": "MH", "registration_number": "  "}).status_code == 400
    assert client.post("/api/rera/check", headers=h, json={"state": "ZZ", "registration_number": "P5170001"}).status_code == 400
    assert client.post("/api/rera/check", headers=h, json={"state": "MH", "registration_number": "x" * 200}).status_code == 400
    assert client.post("/api/rera/check", headers=h, json={"state": "MH", "registration_number": "P5170001", "advance_percent": -3}).status_code == 400


def test_format_hints_are_soft():
    assert rera.check_format("MH", "12")["level"] == "warn"
    assert rera.check_format("MH", "abcdef")["level"] == "warn"
    assert rera.check_format("MH", "PRM/KA/RERA/1251/309")["level"] == "note"
    assert rera.check_format("KA", "PRM/KA/RERA/1251/309/PR/171014/001")["level"] == "ok"


def test_analysis_rules():
    t = date(2026, 10, 25)
    a = rera.basic_analysis(possession_date="2025-01-01", is_under_construction=True, today=t)
    assert any(x["level"] == "warn" and "passed" in x["text"] for x in a)
    a = rera.basic_analysis(quoted_price_per_sqft=5000, market_price_per_sqft=8000, today=t)
    assert any("below" in x["text"] for x in a)
    a = rera.basic_analysis(advance_percent=25, today=t)
    assert any("10%" in x["text"] and x["level"] == "warn" for x in a)
    a = rera.basic_analysis(possession_date="not a date", today=t)
    assert any("not understood" in x["text"] for x in a)


def test_admin_can_override_a_portal_link_and_reset():
    r = client.post("/api/admin/settings", json={"password": PW, "rera_portal_urls": {"GA": "https://example.org/goa"}})
    assert r.json()["rera_portal_urls"]["GA"] == "https://example.org/goa"
    client.post("/api/admin/settings", json={"password": PW, "rera_portal_urls": {"GA": "javascript:alert(1)", "ZZ": "https://x.org"}})
    assert rera.get_portal_urls()["GA"] == "https://example.org/goa"  # bad value ignored
    assert "ZZ" not in rera.get_portal_urls()
    client.post("/api/admin/settings", json={"password": PW, "rera_portal_urls": {"GA": ""}})
    assert rera.get_portal_urls()["GA"] == rera.RERA_STATES["GA"][1]


def test_free_migration_runs_once_and_respects_admin_off():
    set_app_setting(RERA_FREE_MIGRATION_KEY, "")
    set_free_features([])
    ensure_default_free_features()
    assert "rera_verification" in get_free_features()
    set_free_features([])  # admin switches it off
    ensure_default_free_features()
    assert "rera_verification" not in get_free_features()
    set_free_features(["rera_verification"])


def test_homepage_strip_defaults():
    assert client.get("/api/homepage-panels/visibility").json()["rera_verification"] is True
    assert client.get("/api/homepage-panels/sticker-text").json()["rera_verification"]
