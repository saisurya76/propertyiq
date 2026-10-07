"""Service wind-down: batch-cancel renewals on Dodo, email customers, never
delete anything, and reopen cleanly."""
import copy
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import backend.api as api  # noqa: E402
from backend.api import app  # noqa: E402
from backend.config_store import (  # noqa: E402
    DEFAULT_TIER_CONFIG, get_all_tiers_merged, set_app_setting, set_free_features, set_tier_config,
)
from backend.db import get_connection  # noqa: E402
from backend.subscription_store import get_subscription, upsert_subscription  # noqa: E402

client = TestClient(app)
PW = "test-admin-pw"


def _reset():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM subscriptions")
            cur.execute("DELETE FROM wind_down_items")
        conn.commit()
    set_tier_config(copy.deepcopy(DEFAULT_TIER_CONFIG))
    set_free_features([])
    for k in ("launch_mode_snapshot", "wind_down_state", "safety_monitor_log"):
        set_app_setting(k, "")


setup_function = teardown_function = _reset


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(api, "WIND_DOWN_PAUSE_SECONDS", 0)


def _sub(email, tier="studio_pro", dodo="sub_" ):
    upsert_subscription(email=email, tier_id=tier, status="active", dodo_subscription_id=f"{dodo}{email.split('@')[0]}")


def _dodo():
    d = MagicMock()
    d.subscriptions.retrieve.return_value = SimpleNamespace(
        next_billing_date=datetime(2026, 11, 20, tzinfo=timezone.utc), cancel_at_next_billing_date=False
    )
    d.payments.list.return_value = SimpleNamespace(items=[SimpleNamespace(payment_id="pay_1")])
    d.refunds.create.return_value = SimpleNamespace(refund_id="ref_1", amount=2900, currency="USD")
    return d


def _post(path, **body):
    return client.post(f"/api/admin/wind-down/{path}", json={"password": PW, **body})


def _start(mode="period_end", **kw):
    return _post("start", mode=mode, confirm="WIND DOWN", **kw)


def test_start_needs_the_confirmation_phrase_and_valid_mode():
    assert _post("start", mode="period_end", confirm="yes").status_code == 400
    assert _post("start", mode="soon", confirm="WIND DOWN").status_code == 400


def test_start_closes_tiers_lists_subscribers_and_touches_nothing_on_dodo():
    _sub("wd1@example.com"); _sub("wd2@example.com", "studio_starter")
    with patch("backend.api.DodoPayments") as dp:
        r = _start()
    assert r.status_code == 200 and r.json()["counts"] == {"pending": 2}
    dp.assert_not_called()
    tiers = get_all_tiers_merged()
    assert all(tiers[t]["coming_soon"] for t in ("studio_starter", "studio_pro", "studio_unlimited"))
    assert tiers["insight_addon"]["coming_soon"] is False
    assert get_subscription("wd1@example.com")["status"] == "active"
    assert client.get("/api/site-notice").json()["active"] is True


def test_starting_twice_is_refused():
    assert _start().status_code == 200
    assert _start().status_code == 409


def test_period_end_batch_schedules_non_renewal_keeps_access_and_emails():
    for n in range(3):
        _sub(f"wd{n}@example.com")
    _start(message="Back soon")
    d = _dodo()
    with patch("backend.api.DodoPayments", return_value=d), patch("backend.api.send_email") as mail:
        r = _post("run-batch", batch_size=2).json()
        assert r["processed"] == 2 and r["remaining"] == 1
        r = _post("run-batch", batch_size=2).json()
    assert r["remaining"] == 0 and r["counts"] == {"scheduled": 3}
    assert d.subscriptions.update.call_count == 3
    kwargs = d.subscriptions.update.call_args.kwargs
    assert kwargs["cancel_at_next_billing_date"] is True and "status" not in kwargs
    d.refunds.create.assert_not_called()
    assert get_subscription("wd0@example.com")["status"] == "active"  # access until period end
    assert mail.call_count == 3
    body = mail.call_args.kwargs["html"]
    for needle in ("20 November 2026", "terms-of-service.html", "refund-policy.html", "privacy-policy.html", "Back soon", "not deleted"):
        assert needle in body


def test_failures_are_recorded_and_only_failed_ones_retry():
    _sub("wd1@example.com"); _sub("wd2@example.com")
    _start()
    d = _dodo()
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("Dodo down")
    d.subscriptions.update.side_effect = flaky
    with patch("backend.api.DodoPayments", return_value=d), patch("backend.api.send_email") as mail:
        r = _post("run-batch").json()
        assert r["counts"] == {"failed": 1, "scheduled": 1} and r["remaining"] == 1
        assert mail.call_count == 1  # no email for the one that failed
        r = _post("run-batch").json()
    assert r["counts"] == {"scheduled": 2} and r["processed"] == 1 and mail.call_count == 2


def test_already_scheduled_on_dodo_is_not_updated_again():
    _sub("wd1@example.com"); _start()
    d = _dodo()
    d.subscriptions.retrieve.return_value.cancel_at_next_billing_date = True
    with patch("backend.api.DodoPayments", return_value=d), patch("backend.api.send_email"):
        _post("run-batch")
    d.subscriptions.update.assert_not_called()


def test_immediate_refunds_then_cancels_and_blocks_quick_analysis_too():
    _sub("wd1@example.com"); _start("immediate")
    assert get_all_tiers_merged()["insight_addon"]["coming_soon"] is True
    d = _dodo()
    with patch("backend.api.DodoPayments", return_value=d), patch("backend.api.send_email") as mail:
        r = _post("run-batch").json()
    assert r["counts"] == {"cancelled": 1}
    d.refunds.create.assert_called_once()
    assert d.subscriptions.update.call_args.kwargs["status"] == "cancelled"
    assert get_subscription("wd1@example.com")["status"] == "cancelled"
    assert "USD 29.00" in mail.call_args.kwargs["html"]


def test_immediate_refund_failure_leaves_customer_active_and_retry_does_not_double_refund():
    _sub("wd1@example.com"); _start("immediate")
    d = _dodo()
    d.refunds.create.side_effect = RuntimeError("INSUFFICIENT_WALLET_FUNDS")
    with patch("backend.api.DodoPayments", return_value=d), patch("backend.api.send_email") as mail:
        r = _post("run-batch").json()
        assert r["counts"] == {"failed": 1}
        assert get_subscription("wd1@example.com")["status"] == "active"
        mail.assert_not_called()
        d.refunds.create.side_effect = None
        _post("run-batch")
        # a further failure after the refund must not refund twice
    assert d.refunds.create.call_count == 2 and get_subscription("wd1@example.com")["status"] == "cancelled"


def test_immediate_is_refused_while_launch_mode_is_on():
    assert client.post("/api/admin/launch-mode", json={"password": PW, "enabled": True}).status_code == 200
    assert _start("immediate").status_code == 409
    assert _start("period_end").status_code == 200


def test_resume_undoes_non_renewal_and_emails():
    _sub("wd1@example.com"); _start()
    d = _dodo()
    with patch("backend.api.DodoPayments", return_value=d), patch("backend.api.send_email") as mail:
        _post("run-batch")
        r = _post("resume").json()
    assert r["resumed"] == 1 and r["counts"] == {"resumed": 1}
    assert d.subscriptions.update.call_args.kwargs == {"cancel_at_next_billing_date": False}
    assert "continues" in mail.call_args.kwargs["subject"]


def test_reopen_restores_only_what_it_closed_and_keeps_history():
    cfg = copy.deepcopy(DEFAULT_TIER_CONFIG)
    cfg["studio_unlimited"]["coming_soon"] = True  # admin had closed this already
    set_tier_config(cfg)
    _sub("wd1@example.com"); _start()
    r = _post("reopen")
    assert r.status_code == 200 and r.json()["state"] is None and len(r.json()["items"]) == 1
    t = get_all_tiers_merged()
    assert t["studio_pro"]["coming_soon"] is False and t["studio_unlimited"]["coming_soon"] is True
    assert client.get("/api/site-notice").json() == {"active": False}


def test_nothing_is_deleted_by_a_whole_wind_down():
    from backend.auth_store import create_otp
    _sub("wd1@example.com"); _start("immediate")
    with patch("backend.api.DodoPayments", return_value=_dodo()), patch("backend.api.send_email"):
        _post("run-batch")
    row = get_subscription("wd1@example.com")
    assert row is not None and row["tier_id"] == "studio_pro"
    code = create_otp("wd1@example.com")
    assert client.post("/api/auth/verify-otp", json={"email": "wd1@example.com", "code": code}).status_code == 200


def test_safety_monitor_refuses_reopening_a_tier_during_wind_down_and_repairs_drift():
    _start()
    cfg = copy.deepcopy(get_all_tiers_merged())
    cfg["studio_pro"]["coming_soon"] = False
    r = client.post("/api/admin/tiers", json={"password": PW, "tier_config": cfg})
    assert r.status_code == 409
    # Quick Analysis may still be edited: wind-down alone does not require it to stay on sale
    cfg = copy.deepcopy(get_all_tiers_merged())
    cfg["insight_addon"]["price_usd"] = 6
    assert client.post("/api/admin/tiers", json={"password": PW, "tier_config": cfg}).status_code == 200
    persisted = copy.deepcopy(get_all_tiers_merged()); persisted["studio_pro"]["coming_soon"] = False
    set_tier_config(persisted)
    assert api.run_safety_check() == []
    assert get_all_tiers_merged()["studio_pro"]["coming_soon"] is True


def test_admin_calls_need_the_password():
    for path in ("status", "start", "run-batch", "resume", "reopen"):
        r = client.post(f"/api/admin/wind-down/{path}", json={"password": "wrong", "mode": "period_end", "confirm": "WIND DOWN"})
        assert r.status_code in (401, 403)
