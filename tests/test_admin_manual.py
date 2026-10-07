"""The admin manual is admin-only, accurate about what exists, and holds no secrets."""
import os
import re
from pathlib import Path

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app  # noqa: E402
from backend.admin_manual import MANUAL, QUICK  # noqa: E402

client = TestClient(app)
ROOT = Path(__file__).resolve().parent.parent


def _all_text():
    out = []
    for s in MANUAL:
        out.append(s["title"])
        for b in s["blocks"]:
            out.extend(b["items"] if "items" in b else [b["text"]])
    return "\n".join(out)


def test_manual_needs_the_admin_password():
    assert client.post("/api/admin/manual", json={"password": "wrong"}).status_code == 403
    assert client.post("/api/admin/manual", json={}).status_code == 422
    assert client.get("/api/admin/manual").status_code in (404, 405)


def test_manual_returns_every_section_to_the_admin():
    r = client.post("/api/admin/manual", json={"password": "test-admin-pw"})
    assert r.status_code == 200
    ids = [s["id"] for s in r.json()["sections"]]
    assert ids == [s["id"] for s in MANUAL] and len(ids) == len(set(ids)) >= 10


def test_manual_is_not_bundled_into_the_public_site():
    for path in (ROOT / "frontend" / "src").rglob("*.js*"):
        assert "Getting in and the basics" not in path.read_text(errors="ignore"), path
    for path in (ROOT / "frontend" / "public").rglob("*"):
        if path.is_file() and path.suffix in (".html", ".txt", ".xml"):
            assert "Getting in and the basics" not in path.read_text(errors="ignore")


def test_manual_holds_no_secret_values():
    text = _all_text()
    assert not re.search(r"whsec_[A-Za-z0-9]{6,}|sk_[A-Za-z0-9]{10,}|re_[A-Za-z0-9]{10,}|postgres(ql)?://", text)


def test_every_setting_name_in_the_manual_really_exists_in_the_code():
    code = "\n".join(p.read_text(errors="ignore") for p in (ROOT / "backend").glob("*.py") if p.name != "admin_manual.py")
    names = set(re.findall(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+){1,}\b", _all_text()))
    ignore = {"WIND_DOWN", "INSUFFICIENT_WALLET_FUNDS"}  # a confirmation phrase and a Dodo error code, not settings
    assert "VITE_API_BASE" in (ROOT / "frontend" / "src" / "config.js").read_text()  # the one frontend setting named
    missing = sorted(n for n in names - ignore if n not in code and n != "VITE_API_BASE")
    assert not missing, missing


def test_every_admin_menu_screen_is_covered():
    menu = (ROOT / "frontend" / "src" / "studio" / "AdminPanel.jsx").read_text()
    labels = re.findall(r'\{ screen: "[a-z-]+", label: "([^"]+)"', menu)
    text = _all_text()
    first_words = {"Overview & Analytics": "Overview", "Property URL Import — Gemini API Key": "Gemini",
                   "Loan Eligibility — Thresholds": "Loan Eligibility", "Neighborhood Insights — Page Sections": "Neighborhood Insights",
                   "Homepage — Free Quick-Check Panels": "Homepage", "Quick Analysis Grants": "Quick Analysis Grants",
                   "User Manual": "User Manual"}
    for label in labels:
        key = first_words.get(label, label)
        assert key in text or label == "User Manual", label


def test_quick_links_point_at_real_chapters_and_the_api_returns_them():
    ids = {s["id"] for s in MANUAL}
    assert QUICK and all(q["target"] in ids for q in QUICK)
    r = client.post("/api/admin/manual", json={"password": "test-admin-pw"}).json()
    assert r["quick"] == QUICK
