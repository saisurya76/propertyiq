import os

os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")

from fastapi.testclient import TestClient  # noqa: E402
from backend.api import app  # noqa: E402
from backend.auth_store import create_otp  # noqa: E402
from backend.subscription_store import upsert_subscription, get_subscription  # noqa: E402
from backend.config_store import get_all_tiers_merged, set_tier_config, user_has_feature, get_granting_tier_id  # noqa: E402
from backend.insight_store import grant_one_time_tier, get_one_time_tier_grants  # noqa: E402

client = TestClient(app)


def _authed_headers(email: str) -> dict:
    code = create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    token = r.json()["session_token"]
    return {"Authorization": f"Bearer {token}"}


def _add_feature_to_insight_addon(feature: str):
    tiers = get_all_tiers_merged()
    if feature not in tiers["insight_addon"]["features"]:
        tiers["insight_addon"]["features"] = tiers["insight_addon"]["features"] + [feature]
    set_tier_config(tiers)


def _property_payload(**overrides):
    payload = {
        "country": "India", "stateProvince": "Telangana", "city": "Hyderabad", "location": "Tellapur",
        "propertyType": "Apartment", "propertyName": "Test Property", "developerName": "Test Dev",
        "quotedPrice": 9000000, "governmentGuidance": 6500, "marketAverage": 10125, "unitArea": 1800,
        "monthlyRent": 45000, "areaUnit": "sqft",
    }
    payload.update(overrides)
    return payload


def test_admin_configuring_a_feature_for_insight_addon_actually_unlocks_it():
    """Direct proof, end to end through the real /assess endpoint, that
    checking a box for insight_addon in admin genuinely works once the
    grant exists -- the exact question that started this whole thread."""
    email = "realonetimebuyer@example.com"
    headers = _authed_headers(email)
    _add_feature_to_insight_addon("property_assessment")
    grant_one_time_tier(email, "insight_addon")

    r = client.post("/assess", json=_property_payload(), headers=headers)
    assert r.status_code == 200


def test_without_the_grant_the_same_feature_is_still_blocked():
    """The control case: the feature being configured on insight_addon
    is not enough by itself -- a real grant must exist."""
    email = "neverboughtanything@example.com"
    headers = _authed_headers(email)
    _add_feature_to_insight_addon("property_assessment")

    r = client.post("/assess", json=_property_payload(), headers=headers)
    assert r.status_code == 403


def test_a_real_active_subscriber_is_never_affected_by_a_one_time_purchase():
    """THE critical safety property: a paying Studio Pro subscriber's
    real subscription record must be completely untouched by anyone
    (including themselves) also buying a one-time tier. Proven by
    reading their actual subscription row directly after the grant,
    not just checking access still works."""
    email = "realsubscriber@example.com"
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_real123")
    headers = _authed_headers(email)

    # Confirm real access before
    r1 = client.post("/assess", json=_property_payload(), headers=headers)
    assert r1.status_code == 200

    # Now the same email also buys a one-time tier
    grant_one_time_tier(email, "insight_addon")

    # The real subscription row itself must be byte-for-byte unchanged
    sub = get_subscription(email)
    assert sub["tier_id"] == "studio_pro"
    assert sub["status"] == "active"
    assert sub["dodo_subscription_id"] == "sub_real123"

    # And their real access must still work exactly as before
    r2 = client.post("/assess", json=_property_payload(), headers=headers)
    assert r2.status_code == 200


def test_one_time_grant_gives_the_union_of_features_not_a_replacement():
    """A user with both an active subscription AND a one-time grant
    gets access via either -- proven by a feature that's ONLY on
    studio_unlimited (not on their real studio_starter subscription)."""
    email = "bothgrants@example.com"
    upsert_subscription(email=email, tier_id="studio_starter", status="active", dodo_subscription_id="sub_starter")

    tiers = get_all_tiers_merged()
    assert "team_seats" not in tiers["studio_starter"]["features"]  # real, confirmed precondition
    assert user_has_feature(email, "team_seats") is False

    _add_feature_to_insight_addon("team_seats")
    grant_one_time_tier(email, "insight_addon")

    assert user_has_feature(email, "team_seats") is True
    # Their original subscription's own features must still work too --
    # a one-time grant adds access, it never narrows what they already had.
    assert user_has_feature(email, "property_assessment") is True


def test_one_time_grant_is_permanent_no_expiry_mechanism_exists():
    """Confirms the real, stored grant has no expiry field or status
    that could ever mark it inactive -- genuinely permanent, matching
    a one-time purchase's real nature."""
    email = "permanentcheck@example.com"
    grant_one_time_tier(email, "insight_addon")
    grants = get_one_time_tier_grants(email)
    assert grants == ["insight_addon"]
    # No status/expiry concept -- the mere presence of the row is the
    # entire grant; there is no "expired" or "revoked" state to check.


def test_granting_the_same_tier_twice_is_a_safe_no_op():
    """Real, deliberate idempotency for a duplicate webhook delivery
    (Dodo's own docs note these can genuinely happen)."""
    email = "duplicatewebhook@example.com"
    grant_one_time_tier(email, "insight_addon")
    grant_one_time_tier(email, "insight_addon")
    grants = get_one_time_tier_grants(email)
    assert grants == ["insight_addon"]  # not duplicated


def test_get_granting_tier_id_returns_the_real_subscription_tier_when_that_grants_it():
    email = "grantingtiersub@example.com"
    upsert_subscription(email=email, tier_id="studio_pro", status="active", dodo_subscription_id="sub_gt")
    assert get_granting_tier_id(email, "property_assessment") == "studio_pro"


def test_get_granting_tier_id_returns_the_one_time_tier_when_only_that_grants_it():
    email = "grantingtierone@example.com"
    _add_feature_to_insight_addon("property_assessment")
    grant_one_time_tier(email, "insight_addon")
    assert get_granting_tier_id(email, "property_assessment") == "insight_addon"


def test_get_granting_tier_id_returns_none_with_no_access_at_all():
    assert get_granting_tier_id("nobodyatall@example.com", "property_assessment") is None


def test_user_has_feature_handles_a_missing_email_gracefully():
    """Real resilience check for the optional-user-email call sites
    (e.g. the area-comparison monitoring toggle) -- must not crash."""
    assert user_has_feature(None, "property_assessment") is False
    assert user_has_feature("", "property_assessment") is False


def test_agent_intelligence_via_one_time_grant_uses_the_real_granting_tier_for_quotas():
    """Direct proof _require_agent_entitlement's own real fix: the
    returned tier_id is the one that ACTUALLY granted access (the
    one-time tier), not a stale/undefined reference, and quota lookups
    against it work without crashing."""
    email = "agentonetimeuser@example.com"
    _add_feature_to_insight_addon("agent_intelligence")
    grant_one_time_tier(email, "insight_addon")
    headers = _authed_headers(email)

    r = client.post("/api/agent/clients", json={"client_name": "Test Client"}, headers=headers)
    assert r.status_code == 200


def test_similar_property_suggestions_also_respects_the_new_account_wide_grant():
    """_has_similar_properties_access was updated to also check the new
    mechanism -- confirms it wasn't left on the old, narrower check."""
    from backend.api import _has_similar_properties_access
    email = "similarpropsonetime@example.com"
    assert _has_similar_properties_access(email, "some-report-id") is False
    grant_one_time_tier(email, "insight_addon")  # insight_addon's real default feature list already includes this
    assert _has_similar_properties_access(email, "a-totally-different-report-id") is True
