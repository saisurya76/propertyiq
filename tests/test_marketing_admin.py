"""Admin marketing control: admin-only, safe edits only, never leaks the token."""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app  # noqa: E402
from backend import marketing_admin as m  # noqa: E402

client = TestClient(app)
PW = {"password": "test-admin-pw"}


def future(h=48):
    return (datetime.now(timezone.utc) + timedelta(hours=h)).isoformat()


def posts():
    return [{"id": f"p0{i}", "status": "draft", "scheduled_at": None} for i in range(1, 4)]


def test_every_marketing_endpoint_needs_the_admin_password():
    for path, body in [("list", {}), ("update", {"post_id": "p01", "status": "approved"}), ("run", {"mode": "send"})]:
        r = client.post(f"/api/admin/marketing/{path}", json={"password": "wrong", **body})
        assert r.status_code == 403, path


def test_not_connected_without_a_token(monkeypatch):
    monkeypatch.delenv("MARKETING_GITHUB_TOKEN", raising=False)
    r = client.post("/api/admin/marketing/list", json=PW)
    assert r.status_code == 503


def test_approve_needs_a_future_send_time():
    with pytest.raises(m.MarketingError) as e:
        m.apply_update(posts(), "p01", "approved", None)
    assert e.value.status == 400
    with pytest.raises(m.MarketingError):
        m.apply_update(posts(), "p01", "approved", (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat())
    with pytest.raises(m.MarketingError):
        m.apply_update(posts(), "p01", "approved", "not a date")


def test_approve_stores_utc_and_unapprove_returns_to_draft():
    ps = posts()
    p = m.apply_update(ps, "p01", "approved", future())
    assert p["status"] == "approved" and p["scheduled_at"].endswith(".000Z")
    p = m.apply_update(ps, "p01", "draft", None)
    assert p["status"] == "draft"


def test_posts_already_with_buffer_cannot_be_changed():
    ps = posts()
    ps[0]["status"] = "queued"
    with pytest.raises(m.MarketingError) as e:
        m.apply_update(ps, "p01", "draft", None)
    assert e.value.status == 409
    ps[0]["status"] = "sent"
    with pytest.raises(m.MarketingError):
        m.apply_update(ps, "p01", "approved", future())


def test_status_must_be_draft_or_approved_and_post_must_exist():
    with pytest.raises(m.MarketingError) as e:
        m.apply_update(posts(), "p01", "queued", future())
    assert e.value.status == 400
    with pytest.raises(m.MarketingError) as e:
        m.apply_update(posts(), "nope", "approved", future())
    assert e.value.status == 404


def test_safe_queue_cap_is_enforced():
    ps = [{"id": f"x{i}", "status": "queued", "scheduled_at": None} for i in range(8)] + posts()
    with pytest.raises(m.MarketingError) as e:
        m.apply_update(ps, "p01", "approved", future())
    assert e.value.status == 409


def test_run_rejects_unknown_modes():
    with pytest.raises(m.MarketingError):
        m.run_job("rm -rf")


def test_github_failure_never_leaks_the_token(monkeypatch):
    monkeypatch.setenv("MARKETING_GITHUB_TOKEN", "ghp_SECRET123")

    class R:
        status_code = 403
        ok = False
        def json(self): return {}

    with patch("backend.marketing_admin.requests.request", return_value=R()):
        r = client.post("/api/admin/marketing/list", json=PW)
    assert r.status_code == 502 and "ghp_SECRET123" not in r.text


def test_update_saves_through_github_and_retries_on_conflict(monkeypatch):
    monkeypatch.setenv("MARKETING_GITHUB_TOKEN", "t")
    calls = {"put": 0}

    class Get:
        status_code = 200
        ok = True
        def json(self):
            import base64, json
            return {"sha": "abc", "content": base64.b64encode(json.dumps(posts()).encode()).decode()}

    class Put:
        def __init__(self, code): self.status_code = code; self.ok = code < 300

    def fake(method, url, **kw):
        if method == "GET":
            return Get()
        calls["put"] += 1
        return Put(409 if calls["put"] == 1 else 200)

    with patch("backend.marketing_admin.requests.request", side_effect=fake):
        r = client.post("/api/admin/marketing/update",
                        json={**PW, "post_id": "p01", "status": "approved", "scheduled_at": future()})
    assert r.status_code == 200 and calls["put"] == 2
