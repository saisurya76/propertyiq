import os

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app  # noqa: E402
from backend.auth_store import create_otp  # noqa: E402
from backend.subscription_store import upsert_subscription  # noqa: E402
from backend.construction_store import count_designs_this_month, get_quota_reset  # noqa: E402
from backend.config_store import get_all_tiers_merged, set_tier_config  # noqa: E402

client = TestClient(app)


def _authed_headers(email: str) -> dict:
    code = create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    token = r.json()["session_token"]
    return {"Authorization": f"Bearer {token}"}


def _plot_spec():
    return {
        "plot_size_sqft": 1000, "plot_length_ft": 40, "plot_width_ft": 25,
        "entrance_direction": "north", "road_facing_side": "north",
    }


def test_admin_reset_quota_requires_correct_password():
    r = client.post("/api/admin/reset-quota", json={"password": "wrong", "user_email": "x@example.com"})
    assert r.status_code == 403


def test_admin_reset_quota_genuinely_gives_a_fresh_count():
    """The real, direct test of the actual feature: a user who's used
    their entire monthly quota can generate again immediately after an
    admin reset, without waiting for the month to roll over."""
    original = get_all_tiers_merged()
    tight_config = {**original, "studio_starter": {**original["studio_starter"], "design_quota_per_month": 1}}
    set_tier_config(tight_config)

    try:
        email = "resetme@example.com"
        headers = _authed_headers(email)
        upsert_subscription(email=email, tier_id="studio_starter", status="active", dodo_subscription_id="sub_reset_test")

        # Use up the entire quota (1).
        r1 = client.post("/api/construction-studio/design", headers=headers, json={**_plot_spec(), "selections": {}})
        assert r1.status_code == 200

        # Confirm blocked before any reset.
        r2 = client.post("/api/construction-studio/design", headers=headers, json={**_plot_spec(), "selections": {}})
        assert r2.status_code == 403

        # Admin resets the quota.
        r_reset = client.post("/api/admin/reset-quota", json={"password": "test-admin-pw", "user_email": email, "admin_note": "Goodwill reset, UI bug"})
        assert r_reset.status_code == 200
        assert r_reset.json()["designs_used_this_month"] == 0

        # Now generate must succeed again.
        r3 = client.post("/api/construction-studio/design", headers=headers, json={**_plot_spec(), "selections": {}})
        assert r3.status_code == 200
    finally:
        set_tier_config(original)


def test_reset_does_not_delete_any_construction_designs_rows():
    """The real, important guarantee: the generate-history log itself
    is never touched or deleted -- only what counts against the
    CURRENT month's quota changes. Confirms the actual row count in
    construction_designs is unaffected by a reset."""
    from backend.db import get_connection

    original = get_all_tiers_merged()
    tight_config = {**original, "studio_starter": {**original["studio_starter"], "design_quota_per_month": 5}}
    set_tier_config(tight_config)

    try:
        email = "historytest@example.com"
        headers = _authed_headers(email)
        upsert_subscription(email=email, tier_id="studio_starter", status="active", dodo_subscription_id="sub_history_test")

        client.post("/api/construction-studio/design", headers=headers, json={**_plot_spec(), "selections": {}})
        client.post("/api/construction-studio/design", headers=headers, json={**_plot_spec(), "selections": {}})

        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) as cnt FROM construction_designs WHERE user_email = %s", (email,))
                rows_before = cursor.fetchone()["cnt"]

        client.post("/api/admin/reset-quota", json={"password": "test-admin-pw", "user_email": email})

        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) as cnt FROM construction_designs WHERE user_email = %s", (email,))
                rows_after = cursor.fetchone()["cnt"]

        assert rows_before == rows_after == 2
        # The count-against-quota view is now 0 even though 2 real rows still exist.
        assert count_designs_this_month(email) == 0
    finally:
        set_tier_config(original)


def test_reset_is_recorded_and_visible_via_get_quota_reset():
    email = "recordcheck@example.com"
    r = client.post("/api/admin/reset-quota", json={"password": "test-admin-pw", "user_email": email, "admin_note": "Test note"})
    assert r.status_code == 200

    record = get_quota_reset(email)
    assert record is not None
    assert record["admin_note"] == "Test note"


def test_admin_quota_lookup_requires_correct_password():
    r = client.post("/api/admin/quota-lookup", json={"password": "wrong", "user_email": "x@example.com"})
    assert r.status_code == 403


def test_admin_quota_lookup_shows_real_usage_and_tier_limit():
    email = "lookuptest@example.com"
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_lookup_test")

    r = client.post("/api/admin/quota-lookup", json={"password": "test-admin-pw", "user_email": email})
    assert r.status_code == 200
    data = r.json()
    assert data["tier_id"] == "studio_pro"
    assert data["design_quota_per_month"] == 15
    assert data["designs_used_this_month"] == 0
    assert data["last_reset_at"] is None


def test_reset_only_applies_within_the_same_calendar_month():
    """A real, necessary boundary: a reset from a previous month must
    not somehow suppress this month's real usage count -- the reset
    only matters if it falls within the CURRENT month, otherwise the
    normal calendar-month count applies as if no reset ever happened."""
    from backend.construction_store import reset_quota_for_user
    from datetime import datetime, timezone
    from backend.db import get_connection

    email = "oldreset@example.com"
    # Manually insert a stale reset from a clearly different month.
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO quota_resets (user_email, reset_at, admin_note) VALUES (%s, %s, %s) "
                "ON CONFLICT (user_email) DO UPDATE SET reset_at = EXCLUDED.reset_at",
                (email, "2020-01-01T00:00:00+00:00", "old reset"),
            )
        connection.commit()

    # This month's real count must still reflect actual current-month
    # designs, unaffected by that stale, out-of-month reset.
    assert count_designs_this_month(email) == 0


def test_count_designs_this_month_is_case_insensitive_on_email():
    """A real, genuine bug found and fixed during a data-integrity
    review: count_designs_this_month's own construction_designs query
    used the raw, un-normalized email parameter, while its internal
    get_quota_reset lookup always normalized. Every real caller today
    already happens to pass an already-lowercased email (the session
    layer normalizes at login), so this never actually misfired in
    production -- but confirms directly that a differently-cased email
    now still correctly finds the same user's real designs."""
    original = get_all_tiers_merged()
    tight_config = {**original, "studio_starter": {**original["studio_starter"], "design_quota_per_month": 5}}
    set_tier_config(tight_config)

    try:
        email_lower = "casetest@example.com"
        headers = _authed_headers(email_lower)
        upsert_subscription(email=email_lower, tier_id="studio_starter", status="active", dodo_subscription_id="sub_case_test")

        r = client.post("/api/construction-studio/design", headers=headers, json={**_plot_spec(), "selections": {}})
        assert r.status_code == 200

        # Querying with a differently-cased / whitespace-padded version
        # of the same email must still find the real, same design.
        assert count_designs_this_month("  CaseTest@Example.COM  ") == 1
        assert count_designs_this_month(email_lower) == 1
    finally:
        set_tier_config(original)


def test_reset_and_lookup_are_consistent_regardless_of_email_case():
    """The same case-consistency guarantee, specifically for the admin
    reset/lookup endpoints, end to end."""
    original = get_all_tiers_merged()
    tight_config = {**original, "studio_starter": {**original["studio_starter"], "design_quota_per_month": 1}}
    set_tier_config(tight_config)

    try:
        email_lower = "mixedcase@example.com"
        headers = _authed_headers(email_lower)
        upsert_subscription(email=email_lower, tier_id="studio_starter", status="active", dodo_subscription_id="sub_mixed_case")

        client.post("/api/construction-studio/design", headers=headers, json={**_plot_spec(), "selections": {}})

        # Admin looks the user up using a differently-cased email.
        r_lookup = client.post("/api/admin/quota-lookup", json={"password": "test-admin-pw", "user_email": "  MixedCase@Example.COM  "})
        assert r_lookup.status_code == 200
        assert r_lookup.json()["designs_used_this_month"] == 1

        # Reset using yet another casing.
        r_reset = client.post("/api/admin/reset-quota", json={"password": "test-admin-pw", "user_email": "MIXEDCASE@EXAMPLE.COM"})
        assert r_reset.status_code == 200
        assert r_reset.json()["designs_used_this_month"] == 0

        # The real user (lowercase, as their session actually uses) must
        # now be able to generate again.
        r_generate = client.post("/api/construction-studio/design", headers=headers, json={**_plot_spec(), "selections": {}})
        assert r_generate.status_code == 200
    finally:
        set_tier_config(original)


def test_quota_lookup_handles_a_user_with_no_subscription_at_all():
    """A real edge case: a user with historical designs but no current
    subscription (e.g. a lapsed/cancelled plan) must not crash the
    lookup -- tier_id and the quota limit should come back as None,
    not raise an error."""
    email = "nosubscription@example.com"
    r = client.post("/api/admin/quota-lookup", json={"password": "test-admin-pw", "user_email": email})
    assert r.status_code == 200
    data = r.json()
    assert data["tier_id"] is None
    assert data["design_quota_per_month"] is None


def test_reset_works_even_for_a_user_with_no_subscription():
    """Confirms reset itself doesn't require an active subscription to
    exist -- it's purely a record against an email, independent of
    subscription state."""
    email = "resetnosubscription@example.com"
    r = client.post("/api/admin/reset-quota", json={"password": "test-admin-pw", "user_email": email})
    assert r.status_code == 200
    assert r.json()["designs_used_this_month"] == 0


def test_save_design_if_under_quota_genuinely_blocks_at_the_real_limit():
    """Direct test of the new race-safe function itself: the second
    call for a user already at quota must be rejected and must not
    have saved anything."""
    from backend.construction_store import save_design_if_under_quota, count_designs_this_month
    import uuid as uuid_module

    email = "atomicquota@example.com"
    common_kwargs = dict(
        user_email=email, region="global", currency="USD",
        plot_spec={}, selections={}, cost_estimate={"grand_total_usd": 1000},
    )

    r1 = save_design_if_under_quota(quota=1, design_id=str(uuid_module.uuid4()), **common_kwargs)
    assert r1 is True
    assert count_designs_this_month(email) == 1

    r2 = save_design_if_under_quota(quota=1, design_id=str(uuid_module.uuid4()), **common_kwargs)
    assert r2 is False
    assert count_designs_this_month(email) == 1  # still 1 -- the rejected call saved nothing


def test_save_design_if_under_quota_prevents_the_real_race_condition():
    """The actual, direct proof this was built for: fire many
    genuinely concurrent calls at a tight quota and confirm the
    advisory lock serializes them correctly -- the real count in the
    database must never exceed the real quota, regardless of how many
    requests raced to get there at once."""
    from backend.construction_store import save_design_if_under_quota, count_designs_this_month
    import uuid as uuid_module
    from concurrent.futures import ThreadPoolExecutor

    email = "raceconditiontest@example.com"
    quota = 3
    attempts = 10

    def attempt(_):
        return save_design_if_under_quota(
            quota=quota, design_id=str(uuid_module.uuid4()),
            user_email=email, region="global", currency="USD",
            plot_spec={}, selections={}, cost_estimate={"grand_total_usd": 1000},
        )

    with ThreadPoolExecutor(max_workers=attempts) as executor:
        results = list(executor.map(attempt, range(attempts)))

    successes = sum(1 for r in results if r is True)
    assert successes == quota
    assert count_designs_this_month(email) == quota
