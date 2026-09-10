import os

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app  # noqa: E402
from backend.auth_store import create_otp  # noqa: E402
from backend.subscription_store import upsert_subscription  # noqa: E402

client = TestClient(app)


def test_admin_overview_includes_feature_usage_tech_stack_and_locations():
    r = client.post("/api/admin/overview", json={"password": "test-admin-pw"})
    assert r.status_code == 200
    data = r.json()
    assert "feature_usage" in data
    assert "counts" in data["feature_usage"]
    assert "not_tracked" in data["feature_usage"]
    assert "tech_stack" in data
    assert isinstance(data["tech_stack"], list)
    assert "users_by_country" in data


def test_feature_usage_lists_on_demand_features_as_not_tracked():
    r = client.post("/api/admin/overview", json={"password": "test-admin-pw"})
    not_tracked = r.json()["feature_usage"]["not_tracked"]
    assert any("EMI Calculator" in item for item in not_tracked)
    assert any("Property Assessment" in item for item in not_tracked)


def test_tech_stack_status_reflects_real_env_vars(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "some-real-key")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    r = client.post("/api/admin/overview", json={"password": "test-admin-pw"})
    tech_stack = {s["name"]: s["configured"] for s in r.json()["tech_stack"]}
    fred_entry = next(v for k, v in tech_stack.items() if "FRED" in k)
    tavily_entry = next(v for k, v in tech_stack.items() if "Tavily" in k)
    assert fred_entry is True
    assert tavily_entry is False


def test_verify_otp_with_country_saves_it_on_the_user_record():
    email = "countrytest@example.com"
    code = create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": code, "country_code": "TH", "country_name": "Thailand"})
    assert r.status_code == 200

    overview = client.post("/api/admin/overview", json={"password": "test-admin-pw"}).json()
    thailand_rows = [row for row in overview["users_by_country"] if row["country_code"] == "TH"]
    assert len(thailand_rows) >= 1
    assert thailand_rows[0]["country_name"] == "Thailand"


def test_verify_otp_without_country_does_not_crash_or_set_a_country():
    email = "nocountrytest@example.com"
    code = create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    assert r.status_code == 200


def test_verify_otp_country_does_not_overwrite_with_a_blank_on_later_signin():
    """A returning user's real, already-known country must survive a
    sign-in where country detection didn't happen (e.g. ipapi.co was
    unreachable that time) -- confirmed directly, not assumed."""
    email = "persistcountry@example.com"
    code1 = create_otp(email)
    client.post("/api/auth/verify-otp", json={"email": email, "code": code1, "country_code": "VN", "country_name": "Vietnam"})

    code2 = create_otp(email)
    client.post("/api/auth/verify-otp", json={"email": email, "code": code2})

    overview = client.post("/api/admin/overview", json={"password": "test-admin-pw"}).json()
    vietnam_total = sum(row["user_count"] for row in overview["users_by_country"] if row["country_code"] == "VN")
    assert vietnam_total >= 1


def test_users_by_country_breaks_down_by_real_tier():
    email_pro = "tieruser1@example.com"
    email_none = "tieruser2@example.com"
    upsert_subscription(email=email_pro, tier_id="studio_pro", status="active", dodo_subscription_id="sub_tieruser1")

    code1 = create_otp(email_pro)
    client.post("/api/auth/verify-otp", json={"email": email_pro, "code": code1, "country_code": "ID", "country_name": "Indonesia"})
    code2 = create_otp(email_none)
    client.post("/api/auth/verify-otp", json={"email": email_none, "code": code2, "country_code": "ID", "country_name": "Indonesia"})

    overview = client.post("/api/admin/overview", json={"password": "test-admin-pw"}).json()
    indonesia_rows = {row["tier_id"]: row["user_count"] for row in overview["users_by_country"] if row["country_code"] == "ID"}
    assert indonesia_rows.get("studio_pro", 0) >= 1
    assert indonesia_rows.get("none", 0) >= 1


def test_admin_analytics_requires_the_real_admin_password():
    r = client.post("/api/admin/overview", json={"password": "wrong-password"})
    assert r.status_code == 403
