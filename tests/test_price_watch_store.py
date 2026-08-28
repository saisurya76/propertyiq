from unittest.mock import patch

import pytest

from backend.price_watch_store import (
    initialize_price_watch_store,
    create_price_watch,
    get_price_watch,
    list_active_url_watches,
    update_watch_price,
    check_price_watch,
)


def test_create_and_retrieve_a_manual_watch():
    initialize_price_watch_store()
    watch = create_price_watch(
        email="test1@example.com", price=9500000, city="Hyderabad", property_type="Apartment",
        area_value=1200, target_price=8500000,
    )
    assert watch["status"] == "active"
    assert watch["url"] is None
    assert get_price_watch(watch["watch_id"]) == watch


def test_get_nonexistent_watch_returns_none():
    initialize_price_watch_store()
    assert get_price_watch("does-not-exist") is None


def test_rejects_invalid_input():
    initialize_price_watch_store()
    with pytest.raises(ValueError, match="greater than zero"):
        create_price_watch(email="a@b.com", price=0, city="Hyderabad", property_type="Apartment", area_value=1200, target_price=8000000)
    with pytest.raises(ValueError, match="greater than zero"):
        create_price_watch(email="a@b.com", price=9000000, city="Hyderabad", property_type="Apartment", area_value=1200, target_price=0)
    with pytest.raises(ValueError, match="valid email"):
        create_price_watch(email="not-an-email", price=9000000, city="Hyderabad", property_type="Apartment", area_value=1200, target_price=8000000)
    with pytest.raises(ValueError, match="area_unit"):
        create_price_watch(email="a@b.com", price=9000000, city="Hyderabad", property_type="Apartment", area_value=1200, target_price=8000000, area_unit="acres")


def test_manual_watch_excluded_from_active_url_watches_list():
    """A manual-entry watch has nothing to re-fetch — must never appear
    in the list the background re-checker iterates over."""
    initialize_price_watch_store()
    watch = create_price_watch(
        email="test2@example.com", price=9500000, city="Hyderabad", property_type="Apartment",
        area_value=1200, target_price=8500000,
    )
    url_watches = list_active_url_watches()
    assert watch["watch_id"] not in [w["watch_id"] for w in url_watches]


def test_url_watch_appears_in_active_url_watches_list():
    initialize_price_watch_store()
    watch = create_price_watch(
        email="test3@example.com", price=9500000, city="Hyderabad", property_type="Apartment",
        area_value=1200, target_price=8500000, url="https://example.com/listing/abc",
    )
    url_watches = list_active_url_watches()
    assert watch["watch_id"] in [w["watch_id"] for w in url_watches]


def test_check_does_not_trigger_when_price_stays_above_target():
    initialize_price_watch_store()
    watch = create_price_watch(
        email="test4@example.com", price=9500000, city="Hyderabad", property_type="Apartment",
        area_value=1200, target_price=8500000,
    )
    result = check_price_watch(watch["watch_id"], send_email_on_trigger=False)
    assert result["status"] == "active"
    assert result["last_checked_at"] is not None


def test_manual_watch_only_updates_via_explicit_price_update():
    """Core honesty guarantee: a manual-entry watch's price must never
    change on its own — only update_watch_price can change it."""
    initialize_price_watch_store()
    watch = create_price_watch(
        email="test5@example.com", price=9500000, city="Hyderabad", property_type="Apartment",
        area_value=1200, target_price=8500000,
    )
    checked = check_price_watch(watch["watch_id"], send_email_on_trigger=False)
    assert checked["price"] == 9500000  # unchanged by a mere check

    updated = update_watch_price(watch["watch_id"], 8000000)
    assert updated["price"] == 8000000
    assert updated["status"] == "triggered"  # below target, immediately re-evaluated


def test_update_price_on_nonexistent_watch_raises():
    initialize_price_watch_store()
    with pytest.raises(ValueError, match="No price watch found"):
        update_watch_price("does-not-exist", 5000000)


def test_url_watch_gets_genuinely_refetched_and_can_trigger():
    """The core value of a URL-based watch: it can discover a real price
    drop on its own via re-extraction, unlike a manual watch."""
    initialize_price_watch_store()
    watch = create_price_watch(
        email="test6@example.com", price=9500000, city="Hyderabad", property_type="Apartment",
        area_value=1200, target_price=8500000, url="https://example.com/listing/refetch-test",
    )
    with patch("backend.property_url_extract.extract_property_data", return_value={"quotedPrice": 8000000}):
        result = check_price_watch(watch["watch_id"], send_email_on_trigger=False)
    assert result["status"] == "triggered"
    assert result["price"] == 8000000


def test_url_watch_refetch_failure_does_not_crash_and_leaves_watch_active():
    """A blocked/failed re-fetch during a background check must not
    crash the whole check cycle — this watch just stays as it was,
    to be tried again next time."""
    initialize_price_watch_store()
    watch = create_price_watch(
        email="test7@example.com", price=9500000, city="Hyderabad", property_type="Apartment",
        area_value=1200, target_price=8500000, url="https://example.com/listing/blocked-test",
    )
    with patch("backend.property_url_extract.extract_property_data", side_effect=Exception("blocked")):
        result = check_price_watch(watch["watch_id"], send_email_on_trigger=False)
    assert result["status"] == "active"
    assert result["price"] == 9500000
    assert result["last_checked_at"] is not None  # still recorded as checked


def test_already_triggered_watch_is_never_rechecked_or_re_notified():
    initialize_price_watch_store()
    watch = create_price_watch(
        email="test8@example.com", price=8000000, city="Hyderabad", property_type="Apartment",
        area_value=1200, target_price=8500000,  # already below target at creation
    )
    first_check = check_price_watch(watch["watch_id"], send_email_on_trigger=False)
    assert first_check["status"] == "triggered"
    first_checked_at = first_check["last_checked_at"]

    # A second check should be a no-op -- returns immediately, doesn't
    # even touch last_checked_at again, matching the "already notified
    # once, nothing further to do" contract.
    second_check = check_price_watch(watch["watch_id"], send_email_on_trigger=False)
    assert second_check["status"] == "triggered"
    assert second_check["last_checked_at"] == first_checked_at


def test_email_is_sent_exactly_once_when_a_watch_triggers():
    initialize_price_watch_store()
    watch = create_price_watch(
        email="notify-test@example.com", price=8000000, city="Hyderabad", property_type="Apartment",
        area_value=1200, target_price=8500000,
    )
    with patch("backend.auth.send_email") as mock_send:
        check_price_watch(watch["watch_id"], send_email_on_trigger=True)
    mock_send.assert_called_once()
    call_args = mock_send.call_args[0]
    assert call_args[0] == "notify-test@example.com"
    assert "target price" in call_args[1].lower()


def test_email_failure_does_not_prevent_watch_from_being_marked_triggered():
    """The price genuinely crossed the target regardless of whether the
    notification itself succeeded — the watch's own status must reflect
    reality, not silently stay "active" just because email failed."""
    initialize_price_watch_store()
    watch = create_price_watch(
        email="notify-fail-test@example.com", price=8000000, city="Hyderabad", property_type="Apartment",
        area_value=1200, target_price=8500000,
    )
    with patch("backend.auth.send_email", side_effect=Exception("email service down")):
        result = check_price_watch(watch["watch_id"], send_email_on_trigger=True)
    assert result["status"] == "triggered"


def _authed_headers(client, email, tier_id="studio_starter"):
    from backend.auth_store import create_otp
    from backend.subscription_store import upsert_subscription
    code = create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    headers = {"Authorization": f"Bearer {r.json()['session_token']}"}
    upsert_subscription(email=email, tier_id=tier_id, dodo_subscription_id=f"sub_{email}", status="active")
    return headers


def test_endpoint_requires_auth():
    from fastapi.testclient import TestClient
    from backend.api import app

    with TestClient(app) as client:
        r = client.post("/api/price-watches", json={
            "price": 9500000, "city": "Hyderabad", "property_type": "Apartment",
            "area_value": 1200, "target_price": 8500000,
        })
        assert r.status_code == 401


def test_endpoint_requires_the_feature_to_be_enabled_on_the_users_tier():
    from fastapi.testclient import TestClient
    from backend.api import app

    with TestClient(app) as client:
        headers = _authed_headers(client, "no_feature_test@example.com")
        with patch("backend.api.has_feature", return_value=False):
            r = client.post("/api/price-watches", json={
                "price": 9500000, "city": "Hyderabad", "property_type": "Apartment",
                "area_value": 1200, "target_price": 8500000,
            }, headers=headers)
        assert r.status_code == 403
        assert "Studio subscription" in r.json()["detail"]


def test_full_flow_with_authenticated_subscribed_user():
    from fastapi.testclient import TestClient
    from backend.api import app

    with TestClient(app) as client:
        headers = _authed_headers(client, "endpointtest@example.com")
        create_resp = client.post("/api/price-watches", json={
            "price": 9500000, "city": "Hyderabad",
            "property_type": "Apartment", "area_value": 1200, "target_price": 8500000,
        }, headers=headers)
        assert create_resp.status_code == 200
        assert create_resp.json()["email"] == "endpointtest@example.com"
        watch_id = create_resp.json()["watch_id"]

        get_resp = client.get(f"/api/price-watches/{watch_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "active"

        update_resp = client.post(f"/api/price-watches/{watch_id}/update-price", json={"new_price": 8000000})
        assert update_resp.status_code == 200
        assert update_resp.json()["status"] == "triggered"


def test_get_nonexistent_watch_returns_404():
    from fastapi.testclient import TestClient
    from backend.api import app

    with TestClient(app) as client:
        r = client.get("/api/price-watches/totally-fake-id")
        assert r.status_code == 404


def test_update_price_on_nonexistent_watch_returns_404():
    from fastapi.testclient import TestClient
    from backend.api import app

    with TestClient(app) as client:
        r = client.post("/api/price-watches/totally-fake-id/update-price", json={"new_price": 5000000})
        assert r.status_code == 404


def test_create_watch_rejects_invalid_input_with_400():
    from fastapi.testclient import TestClient
    from backend.api import app

    with TestClient(app) as client:
        headers = _authed_headers(client, "invalidinputtest@example.com")
        r = client.post("/api/price-watches", json={
            "price": 9500000, "city": "Hyderabad",
            "property_type": "Apartment", "area_value": -1200, "target_price": 8500000,
        }, headers=headers)
        assert r.status_code == 400


def test_create_watch_from_url_extracts_real_initial_values():
    """The real design fix: a URL-mode watch's initial price/city/type/
    area come from actually extracting the listing, not placeholder
    values the frontend would otherwise have to guess."""
    from fastapi.testclient import TestClient
    from backend.api import app

    with TestClient(app) as client:
        headers = _authed_headers(client, "urlwatch@example.com")
        with patch("backend.api.extract_property_data", return_value={
            "propertyName": "Test Towers", "quotedPrice": 9500000, "city": "Hyderabad",
            "propertyType": "Apartment", "areaValue": 1200, "areaUnit": "sqft",
            "developerName": None, "location": None, "totalUnits": None, "monthlyRent": None,
        }):
            r = client.post("/api/price-watches", json={
                "target_price": 8500000, "url": "https://example.com/listing/watch-test",
            }, headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["price"] == 9500000
        assert body["city"] == "Hyderabad"
        assert body["property_type"] == "Apartment"
        assert body["area_value"] == 1200


def test_create_watch_from_url_fails_clearly_when_price_not_found():
    from fastapi.testclient import TestClient
    from backend.api import app

    with TestClient(app) as client:
        headers = _authed_headers(client, "urlwatch2@example.com")
        with patch("backend.api.extract_property_data", return_value={
            "propertyName": None, "quotedPrice": None, "city": None, "propertyType": None,
            "areaValue": None, "areaUnit": None, "developerName": None, "location": None,
            "totalUnits": None, "monthlyRent": None,
        }):
            r = client.post("/api/price-watches", json={
                "target_price": 8500000, "url": "https://example.com/listing/no-price-found",
            }, headers=headers)
        assert r.status_code == 422
        assert "current price" in r.json()["detail"]


def test_create_watch_from_url_fills_reasonable_defaults_for_missing_context_fields():
    """City/type/area are nice-to-have context, not required for the
    watch's core purpose -- must not block creation just because the
    extraction found a price but not, say, the city."""
    from fastapi.testclient import TestClient
    from backend.api import app

    with TestClient(app) as client:
        headers = _authed_headers(client, "urlwatch3@example.com")
        with patch("backend.api.extract_property_data", return_value={
            "propertyName": "Test Towers", "quotedPrice": 9500000, "city": None,
            "propertyType": None, "areaValue": None, "areaUnit": None,
            "developerName": None, "location": None, "totalUnits": None, "monthlyRent": None,
        }):
            r = client.post("/api/price-watches", json={
                "target_price": 8500000, "url": "https://example.com/listing/partial-data",
            }, headers=headers)
        assert r.status_code == 200
        assert r.json()["price"] == 9500000
        assert r.json()["city"] == "Unknown"


def test_create_watch_without_url_or_manual_fields_returns_clear_400():
    from fastapi.testclient import TestClient
    from backend.api import app

    with TestClient(app) as client:
        headers = _authed_headers(client, "neither@example.com")
        r = client.post("/api/price-watches", json={"target_price": 8500000}, headers=headers)
        assert r.status_code == 400
        assert "listing URL" in r.json()["detail"]


def test_max_price_watches_limit_is_enforced_per_tier():
    """The real, explicit request this whole auth shift exists for:
    alerts cannot be unlimited — an admin-configurable per-tier cap."""
    import uuid
    from fastapi.testclient import TestClient
    from backend.api import app

    with TestClient(app) as client:
        # A genuinely unique email each run — this test's assertions
        # depend on an exact count starting from zero, so reusing a
        # fixed email across repeated local test runs (the real test
        # database persists between runs, unlike a fresh in-memory DB)
        # would silently accumulate leftover watches from prior runs
        # and break this test's exact-count assumption.
        email = f"limittest-{uuid.uuid4().hex[:8]}@example.com"
        headers = _authed_headers(client, email, tier_id="studio_starter")
        # studio_starter's default max_price_watches is 2
        for i in range(2):
            r = client.post("/api/price-watches", json={
                "price": 9000000, "city": "Hyderabad", "property_type": "Apartment",
                "area_value": 1200, "target_price": 8000000,
            }, headers=headers)
            assert r.status_code == 200, f"watch {i+1} should succeed"

        r3 = client.post("/api/price-watches", json={
            "price": 9000000, "city": "Hyderabad", "property_type": "Apartment",
            "area_value": 1200, "target_price": 8000000,
        }, headers=headers)
        assert r3.status_code == 403
        assert "allows watching up to 2" in r3.json()["detail"]


def test_unlimited_tier_has_no_max_price_watches_cap():
    import uuid
    from fastapi.testclient import TestClient
    from backend.api import app

    with TestClient(app) as client:
        email = f"unlimitedtest-{uuid.uuid4().hex[:8]}@example.com"
        headers = _authed_headers(client, email, tier_id="studio_unlimited")
        for i in range(5):
            r = client.post("/api/price-watches", json={
                "price": 9000000, "city": "Hyderabad", "property_type": "Apartment",
                "area_value": 1200, "target_price": 8000000,
            }, headers=headers)
            assert r.status_code == 200, f"watch {i+1} should succeed on the unlimited tier"


def test_a_triggered_watch_does_not_count_against_the_limit():
    """A triggered watch has already served its purpose — a user should
    be able to start a new watch once an old one fires, without it
    counting against their limit forever."""
    import uuid
    from fastapi.testclient import TestClient
    from backend.api import app

    with TestClient(app) as client:
        email = f"triggeredlimittest-{uuid.uuid4().hex[:8]}@example.com"
        headers = _authed_headers(client, email, tier_id="studio_starter")
        r1 = client.post("/api/price-watches", json={
            "price": 8000000, "city": "Hyderabad", "property_type": "Apartment",
            "area_value": 1200, "target_price": 8500000,  # already at/below target -- triggers immediately on first check
        }, headers=headers)
        assert r1.status_code == 200
        watch1_id = r1.json()["watch_id"]
        client.post(f"/api/price-watches/{watch1_id}/update-price", json={"new_price": 7000000})  # forces a check, triggers

        # Two more watches should still succeed even though 1 exists total,
        # since the first is now triggered, not active
        r2 = client.post("/api/price-watches", json={
            "price": 9000000, "city": "Hyderabad", "property_type": "Apartment",
            "area_value": 1200, "target_price": 8000000,
        }, headers=headers)
        r3 = client.post("/api/price-watches", json={
            "price": 9000000, "city": "Hyderabad", "property_type": "Apartment",
            "area_value": 1200, "target_price": 8000000,
        }, headers=headers)
        assert r2.status_code == 200
        assert r3.status_code == 200


def test_endpoint_stores_manual_location():
    import uuid
    from fastapi.testclient import TestClient
    from backend.api import app

    with TestClient(app) as client:
        headers = _authed_headers(client, f"loctest_manual-{uuid.uuid4().hex[:8]}@example.com")
        r = client.post("/api/price-watches", json={
            "price": 9500000, "city": "Hyderabad", "property_type": "Apartment",
            "area_value": 1200, "target_price": 8500000, "location": "Gachibowli",
        }, headers=headers)
        assert r.status_code == 200
        assert r.json()["location"] == "Gachibowli"


def test_endpoint_extracts_location_from_url_when_not_given_manually():
    import uuid
    from fastapi.testclient import TestClient
    from backend.api import app

    with TestClient(app) as client:
        headers = _authed_headers(client, f"loctest_url-{uuid.uuid4().hex[:8]}@example.com")
        with patch("backend.api.extract_property_data", return_value={
            "quotedPrice": 9500000, "city": "Hyderabad", "propertyType": "Apartment",
            "areaValue": 1200, "areaUnit": "sqft", "location": "Kondapur",
        }):
            r = client.post("/api/price-watches", json={
                "target_price": 8500000, "url": "https://example.com/listing/loc-test",
            }, headers=headers)
        assert r.status_code == 200
        assert r.json()["location"] == "Kondapur"


def test_endpoint_prefers_manual_location_over_url_extraction():
    """If the user explicitly typed a location alongside a URL, that
    should win over whatever the extraction found."""
    import uuid
    from fastapi.testclient import TestClient
    from backend.api import app

    with TestClient(app) as client:
        headers = _authed_headers(client, f"loctest_prefer-{uuid.uuid4().hex[:8]}@example.com")
        with patch("backend.api.extract_property_data", return_value={
            "quotedPrice": 9500000, "city": "Hyderabad", "propertyType": "Apartment",
            "areaValue": 1200, "areaUnit": "sqft", "location": "Kondapur",
        }):
            r = client.post("/api/price-watches", json={
                "target_price": 8500000, "url": "https://example.com/listing/loc-test-2",
                "location": "Manually Entered Location",
            }, headers=headers)
        assert r.status_code == 200
        assert r.json()["location"] == "Manually Entered Location"


def test_rejects_empty_or_whitespace_city():
    initialize_price_watch_store()
    for bad_city in ["", "   "]:
        with pytest.raises(ValueError, match="City is required"):
            create_price_watch(email="a@b.com", price=5000000, city=bad_city, property_type="Apartment", area_value=1200, target_price=4000000)


def test_rejects_empty_or_whitespace_property_type():
    initialize_price_watch_store()
    for bad_type in ["", "   "]:
        with pytest.raises(ValueError, match="Property type is required"):
            create_price_watch(email="a@b.com", price=5000000, city="Hyderabad", property_type=bad_type, area_value=1200, target_price=4000000)
