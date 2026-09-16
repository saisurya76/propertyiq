import os

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app  # noqa: E402
from backend.rate_limiter import check_rate_limit, reset_rate_limit  # noqa: E402

client = TestClient(app)


def test_check_rate_limit_allows_up_to_the_real_max():
    key = "test-key-allows-max"
    for _ in range(5):
        assert check_rate_limit(key, max_attempts=5, window_seconds=60) is True
    assert check_rate_limit(key, max_attempts=5, window_seconds=60) is False


def test_check_rate_limit_prunes_attempts_outside_the_window():
    """Real proof the sliding window actually slides, not just a
    fixed-count check -- uses a real, tiny window and a real sleep."""
    import time
    key = "test-key-window-expiry"
    for _ in range(3):
        assert check_rate_limit(key, max_attempts=3, window_seconds=1) is True
    assert check_rate_limit(key, max_attempts=3, window_seconds=1) is False
    time.sleep(1.1)
    assert check_rate_limit(key, max_attempts=3, window_seconds=1) is True


def test_reset_rate_limit_clears_history():
    key = "test-key-reset"
    for _ in range(3):
        check_rate_limit(key, max_attempts=3, window_seconds=60)
    assert check_rate_limit(key, max_attempts=3, window_seconds=60) is False
    reset_rate_limit(key)
    assert check_rate_limit(key, max_attempts=3, window_seconds=60) is True


def test_admin_password_rate_limit_blocks_after_repeated_wrong_attempts():
    """Direct proof against the real endpoint: 10 wrong attempts in a
    row genuinely trip the limiter with a real 429, not just the
    expected 403 for each individual wrong password."""
    for _ in range(10):
        r = client.post("/api/admin/overview", json={"password": "wrong-one-off"})
        assert r.status_code == 403
    r = client.post("/api/admin/overview", json={"password": "wrong-one-off"})
    assert r.status_code == 429


def test_admin_password_rate_limit_resets_on_a_real_success():
    for _ in range(9):
        client.post("/api/admin/overview", json={"password": "wrong-again"})
    r_success = client.post("/api/admin/overview", json={"password": "test-admin-pw"})
    assert r_success.status_code == 200
    # The counter should be reset now -- confirm a fresh run of wrong
    # attempts doesn't immediately 429 from leftover history.
    r = client.post("/api/admin/overview", json={"password": "wrong-post-reset"})
    assert r.status_code == 403


def test_otp_request_rate_limit_is_scoped_per_email():
    """Real proof the limit is per-email, not global -- a different
    email is entirely unaffected by another email's attempts."""
    from unittest.mock import patch
    email_a = "ratelimited-a@example.com"
    email_b = "ratelimited-b@example.com"
    with patch("backend.api.send_otp_email"):
        for _ in range(5):
            r = client.post("/api/auth/request-otp", json={"email": email_a})
            assert r.status_code == 200
        r_blocked = client.post("/api/auth/request-otp", json={"email": email_a})
        assert r_blocked.status_code == 429

        r_other = client.post("/api/auth/request-otp", json={"email": email_b})
        assert r_other.status_code == 200


def test_otp_verify_rate_limit_blocks_brute_force_of_wrong_codes():
    from backend.auth_store import create_otp
    email = "otpverify-bruteforce@example.com"
    create_otp(email)  # a real code exists, but we deliberately guess wrong
    for _ in range(10):
        r = client.post("/api/auth/verify-otp", json={"email": email, "code": "000000"})
        assert r.status_code == 401
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": "000000"})
    assert r.status_code == 429


def test_otp_verify_rate_limit_resets_on_a_real_successful_login():
    from backend.auth_store import create_otp
    email = "otpverify-realsuccess@example.com"
    for _ in range(9):
        client.post("/api/auth/verify-otp", json={"email": email, "code": "111111"})
    real_code = create_otp(email)
    r_success = client.post("/api/auth/verify-otp", json={"email": email, "code": real_code})
    assert r_success.status_code == 200

    create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": "222222"})
    assert r.status_code == 401  # not 429 -- the counter was genuinely reset
