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


def test_names_are_echoed_back_and_length_limited():
    set_free_features(["rera_verification"])
    h = _headers("reranames@example.com")
    r = client.post("/api/rera/check", headers=h, json={"state": "MH", "registration_number": "P51700012345", "project_name": " Sky Towers ", "builder_name": "ABC Builders"})
    assert r.json()["provided"] == {"project_name": "Sky Towers", "builder_name": "ABC Builders"}
    assert client.post("/api/rera/check", headers=h, json={"state": "MH", "registration_number": "P51700012345", "project_name": "x" * 200}).status_code == 400


def test_strip_shows_on_every_country_site():
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "frontend/src/App.jsx").read_text()
    assert "homepagePanelVisibility.rera_verification && (" in src


def _post(h, **body):
    return client.post("/api/rera/check", headers=h, json=body)


def test_countries_listed_publicly_with_official_links():
    c = {x["code"]: x for x in client.get("/api/rera/states").json()["countries"]}
    assert set(c) == {"TH", "PH", "VN", "ID"}
    assert all(l["url"].startswith("https://") for x in c.values() for l in x["links"])
    assert c["ID"]["certificate_types"]


def test_philippines_without_lts_number_is_warned():
    set_free_features(["rera_verification"])
    h = _headers("rera-ph@example.com")
    body = _post(h, country="PH").json()
    assert body["verified"] is False and body["country"] == "PH"
    assert any(a["level"] == "warn" and "License to Sell" in a["text"] for a in body["analysis"])
    ok = _post(h, country="PH", registration_number="LTS-123").json()
    assert not any(a["level"] == "warn" for a in ok["analysis"])


def test_vietnam_deposit_and_first_payment_caps():
    set_free_features(["rera_verification"])
    h = _headers("rera-vn@example.com")
    a = _post(h, country="VN", advance_percent=10, first_payment_percent=40).json()["analysis"]
    assert sum(1 for x in a if x["level"] == "warn") == 2
    a = _post(h, country="VN", advance_percent=5, first_payment_percent=30).json()["analysis"]
    assert not any(x["level"] == "warn" for x in a)


def test_thailand_and_indonesia_rules():
    set_free_features(["rera_verification"])
    h = _headers("rera-thid@example.com")
    a = _post(h, country="TH", advance_percent=50, buyer_is_foreign=True).json()["analysis"]
    assert any(x["level"] == "warn" for x in a) and any("49%" in x["text"] for x in a)
    a = _post(h, country="ID", buyer_is_foreign=True, certificate_type="hak_milik").json()["analysis"]
    assert any(x["level"] == "warn" and "citizens" in x["text"] for x in a)


def test_unknown_country_and_india_still_needs_number():
    set_free_features(["rera_verification"])
    h = _headers("rera-xx@example.com")
    assert _post(h, country="ZZ").status_code == 400
    assert _post(h, country="IN", state="MH").status_code == 400


def test_admin_can_fix_a_country_link():
    client.post("/api/admin/settings", json={"password": PW, "country_link_urls": {"TH.dbd": "https://example.org/dbd", "XX.y": "https://x.org"}})
    from backend import country_checks
    assert country_checks.get_link_urls()["TH.dbd"] == "https://example.org/dbd"
    assert "XX.y" not in country_checks.get_link_urls()
    client.post("/api/admin/settings", json={"password": PW, "country_link_urls": {"TH.dbd": ""}})
    assert country_checks.get_link_urls()["TH.dbd"].startswith("https://ebiz.dbd")
