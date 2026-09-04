import os
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")
os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")

from fastapi.testclient import TestClient
from backend.api import app
from backend.auth_store import create_otp
from backend.subscription_store import upsert_subscription
from backend.property_store import create_property, list_properties_for_user

client = TestClient(app)


def _signin_with_tier(email, tier_id="studio_starter"):
    """Signs in and grants an active subscription directly via the store
    (not through /api/subscribe/checkout) — avoids any dependency on the
    beta-payment-bypass flag, and avoids mutating global process state
    the way an earlier version of this file incorrectly did (leaked
    PROPERTYIQ_BETA_BYPASS_PAYMENTS into the whole pytest session via
    os.environ.setdefault, breaking an unrelated test elsewhere)."""
    code = create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    headers = {"Authorization": f"Bearer {r.json()['session_token']}"}
    upsert_subscription(email=email, tier_id=tier_id, status="active", dodo_subscription_id=f"sub_{email}")
    return headers


def _base_payload(name="Test Property"):
    return {
        "name": name,
        "plot_spec": {
            "plot_size_sqft": 1200, "plot_length_ft": 40, "plot_width_ft": 30,
            "region": "india", "currency": "INR",
            "entrance_direction": "north", "road_facing_side": "north",
        },
        "selections": {}, "labor_selections": {}, "site_elements": [],
        "floors": [{"floor_number": 0, "floor_label": "Ground Floor", "rooms": []}],
    }


def test_create_and_load_multi_floor_property():

    headers = _signin_with_tier("pytest_property_multifloor@example.com")

    payload = _base_payload("Multi-floor Test")
    payload["floors"] = [
        {"floor_number": 0, "floor_label": "Ground Floor", "rooms": [{"name": "Living Room", "x": 0, "y": 0, "length": 10, "width": 10}]},
        {"floor_number": 1, "floor_label": "First Floor", "rooms": [{"name": "Bedroom", "x": 0, "y": 0, "length": 10, "width": 10}]},
    ]
    r = client.post("/api/properties", headers=headers, json=payload)
    assert r.status_code == 200
    prop = r.json()
    assert len(prop["floors"]) == 2

    r = client.get(f"/api/properties/{prop['property_id']}", headers=headers)
    assert r.status_code == 200
    assert r.json()["floors"][1]["rooms"][0]["name"] == "Bedroom"


def test_lock_blocks_edits_and_wrong_otp_stays_locked():
    headers = _signin_with_tier("pytest_property_lock@example.com")

    r = client.post("/api/properties", headers=headers, json=_base_payload())
    property_id = r.json()["property_id"]

    client.post(f"/api/properties/{property_id}/lock", headers=headers)
    assert client.get(f"/api/properties/{property_id}", headers=headers).json()["locked"] is True

    r = client.put(f"/api/properties/{property_id}", headers=headers, json={"name": "Should fail"})
    assert r.status_code == 423

    r = client.post(f"/api/properties/{property_id}/confirm-unlock", headers=headers, json={"code": "000000"})
    assert r.status_code == 401
    assert client.get(f"/api/properties/{property_id}", headers=headers).json()["locked"] is True


def test_correct_otp_unlocks_and_code_is_single_use():
    email = "pytest_property_unlock@example.com"
    headers = _signin_with_tier(email)

    r = client.post("/api/properties", headers=headers, json=_base_payload())
    property_id = r.json()["property_id"]
    client.post(f"/api/properties/{property_id}/lock", headers=headers)

    code = create_otp(email)
    r = client.post(f"/api/properties/{property_id}/confirm-unlock", headers=headers, json={"code": code})
    assert r.status_code == 200
    assert r.json()["locked"] is False

    r = client.put(f"/api/properties/{property_id}", headers=headers, json={"name": "Renamed"})
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"

    client.post(f"/api/properties/{property_id}/lock", headers=headers)
    r = client.post(f"/api/properties/{property_id}/confirm-unlock", headers=headers, json={"code": code})
    assert r.status_code == 401  # same code, already used


def test_saved_designs_quota_enforced_per_tier():
    headers = _signin_with_tier("pytest_property_quota@example.com", tier_id="studio_starter")

    statuses = []
    for i in range(3):
        r = client.post("/api/properties", headers=headers, json=_base_payload(f"Quota Test {i}"))
        statuses.append(r.status_code)
    assert statuses[0] == 200
    assert statuses[1] == 200
    assert statuses[2] == 403


def test_cannot_access_another_users_property():
    headers_a = _signin_with_tier("pytest_property_owner@example.com")
    headers_b = _signin_with_tier("pytest_property_intruder@example.com")

    r = client.post("/api/properties", headers=headers_a, json=_base_payload())
    property_id = r.json()["property_id"]

    r = client.get(f"/api/properties/{property_id}", headers=headers_b)
    assert r.status_code == 403


def test_cannot_delete_the_only_floor():
    headers = _signin_with_tier("pytest_property_lastfloor@example.com")

    r = client.post("/api/properties", headers=headers, json=_base_payload())
    prop = r.json()
    floor_id = prop["floors"][0]["floor_id"]

    r = client.delete(f"/api/properties/{prop['property_id']}/floors/{floor_id}", headers=headers)
    assert r.status_code == 400


def test_master_plan_elements_round_trip():
    headers = _signin_with_tier("pytest_property_masterplan@example.com")

    payload = _base_payload("Master Plan Test")
    payload["plot_spec"]["master_plan_elements"] = [
        {"type": "water_body", "direction": "north-east"},
        {"type": "mountain", "direction": "west"},
    ]
    r = client.post("/api/properties", headers=headers, json=payload)
    assert r.status_code == 200
    property_id = r.json()["property_id"]
    assert r.json()["plot_spec"]["master_plan_elements"] == payload["plot_spec"]["master_plan_elements"]

    r2 = client.get(f"/api/properties/{property_id}", headers=headers)
    assert r2.json()["plot_spec"]["master_plan_elements"] == payload["plot_spec"]["master_plan_elements"]


def test_sync_property_deletes_floors_omitted_from_save():
    headers = _signin_with_tier("pytest_property_sync_delete@example.com")

    payload = _base_payload("Sync Delete Test")
    payload["floors"] = [
        {"floor_number": 0, "floor_label": "Ground Floor", "rooms": []},
        {"floor_number": 1, "floor_label": "First Floor", "rooms": []},
        {"floor_number": 2, "floor_label": "Second Floor", "rooms": []},
    ]
    r = client.post("/api/properties", headers=headers, json=payload)
    prop = r.json()
    property_id = prop["property_id"]
    floor_ids = [f["floor_id"] for f in prop["floors"]]

    sync_payload = {"floors": [
        {"floor_id": floor_ids[0], "floor_number": 0, "floor_label": "Ground Floor", "rooms": [{"name": "Kitchen", "x": 0, "y": 0, "length": 10, "width": 10}]},
        {"floor_id": floor_ids[1], "floor_number": 1, "floor_label": "First Floor", "rooms": []},
    ]}
    r = client.put(f"/api/properties/{property_id}/sync", headers=headers, json=sync_payload)
    assert r.status_code == 200
    synced = r.json()
    assert len(synced["floors"]) == 2
    assert synced["floors"][0]["rooms"][0]["name"] == "Kitchen"

    # Confirm it's really gone, not just missing from THIS response
    r2 = client.get(f"/api/properties/{property_id}", headers=headers)
    assert len(r2.json()["floors"]) == 2


def test_sync_property_creates_new_floor_and_keeps_existing():
    headers = _signin_with_tier("pytest_property_sync_new@example.com")

    r = client.post("/api/properties", headers=headers, json=_base_payload())
    prop = r.json()
    property_id = prop["property_id"]
    existing_floor_id = prop["floors"][0]["floor_id"]

    sync_payload = {"name": "Renamed via sync", "floors": [
        {"floor_id": existing_floor_id, "floor_number": 0, "floor_label": "Ground Floor", "rooms": []},
        {"floor_id": None, "floor_number": 1, "floor_label": "New Floor", "rooms": []},
    ]}
    r = client.put(f"/api/properties/{property_id}/sync", headers=headers, json=sync_payload)
    assert r.status_code == 200
    synced = r.json()
    assert synced["name"] == "Renamed via sync"
    assert len(synced["floors"]) == 2
    assert synced["floors"][0]["floor_id"] == existing_floor_id  # unchanged, updated in place
    assert synced["floors"][1]["floor_id"] is not None  # brand new id assigned


def test_sync_property_locked_refuses():
    headers = _signin_with_tier("pytest_property_sync_locked@example.com")

    r = client.post("/api/properties", headers=headers, json=_base_payload())
    property_id = r.json()["property_id"]
    client.post(f"/api/properties/{property_id}/lock", headers=headers)

    r = client.put(f"/api/properties/{property_id}/sync", headers=headers, json={"floors": [
        {"floor_number": 0, "floor_label": "x", "rooms": []},
    ]})
    assert r.status_code == 423


def test_sync_property_requires_at_least_one_floor():
    headers = _signin_with_tier("pytest_property_sync_empty@example.com")

    r = client.post("/api/properties", headers=headers, json=_base_payload())
    property_id = r.json()["property_id"]

    r = client.put(f"/api/properties/{property_id}/sync", headers=headers, json={"floors": []})
    assert r.status_code == 400


def test_create_property_survives_stale_tier_config_missing_newer_field():
    """Reproduces the exact production bug: a tier_config persisted BEFORE
    saved_designs_limit existed as a field. Without config_store.get_tier()
    merging in current defaults for missing fields, this throws a real
    KeyError -> 500 (which, due to a separate Starlette gotcha, also drops
    CORS headers and shows the browser a misleading "Failed to fetch")."""
    from backend.config_store import set_tier_config, DEFAULT_TIER_CONFIG

    stale_config = {
        tier_id: {k: v for k, v in tier.items() if k != "saved_designs_limit"}
        for tier_id, tier in DEFAULT_TIER_CONFIG.items()
    }
    set_tier_config(stale_config)

    headers = _signin_with_tier("pytest_stale_config@example.com", tier_id="studio_starter")
    r = client.post("/api/properties", headers=headers, json=_base_payload())
    assert r.status_code == 200, f"stale config should not crash property creation: {r.text}"

    # Restore a full, current config so this doesn't leak into other tests
    set_tier_config(DEFAULT_TIER_CONFIG)


def test_unhandled_exception_still_returns_cors_headers():
    """The confirmed Starlette gotcha: ServerErrorMiddleware sits outside
    CORSMiddleware, so even a registered exception_handler's response
    skips CORS header injection unless set manually. Verifies the actual
    fix (headers set by hand in the handler), not just that a handler
    exists."""
    from fastapi.testclient import TestClient
    from backend.api import app
    import backend.api as api_module

    local_client = TestClient(app, raise_server_exceptions=False)
    email = "pytest_exc_cors@example.com"
    headers = _signin_with_tier(email)
    headers["Origin"] = "https://app.propertyiqweb.com"

    original = api_module.get_active_tier
    api_module.get_active_tier = lambda e: (_ for _ in ()).throw(RuntimeError("simulated"))
    try:
        r = local_client.post("/api/properties", headers=headers, json=_base_payload())
        assert r.status_code == 500
        assert r.headers.get("access-control-allow-origin") == "https://app.propertyiqweb.com"
        assert r.headers.get("access-control-allow-credentials") == "true"
        assert r.json()["detail"]  # clean JSON body, not a raw crash
    finally:
        api_module.get_active_tier = original


def test_city_and_country_persist_through_save_load():
    """Real reported bug: city was never part of PropertyPlotSpec at all,
    so it was silently discarded on every save — not a display bug, a
    genuine data-loss bug. Verifies city AND the newly-added country
    field both round-trip correctly now."""
    headers = _signin_with_tier("pytest_city_country@example.com")

    payload = _base_payload("City Country Test")
    payload["plot_spec"]["city"] = "Hyderabad"
    payload["plot_spec"]["country"] = "India"

    r = client.post("/api/properties", headers=headers, json=payload)
    assert r.status_code == 200
    assert r.json()["plot_spec"]["city"] == "Hyderabad"
    assert r.json()["plot_spec"]["country"] == "India"

    property_id = r.json()["property_id"]
    r2 = client.get(f"/api/properties/{property_id}", headers=headers)
    assert r2.json()["plot_spec"]["city"] == "Hyderabad"
    assert r2.json()["plot_spec"]["country"] == "India"


def test_list_properties_includes_country_for_cross_site_locking():
    """Real reported gap: the Studio designs list had no way to flag a
    cross-site design (belongs to a different country than the current
    site) without opening it first — cross-site locking previously only
    kicked in once a design was already resumed. The list summary now
    carries country so the frontend can show this directly on the list."""
    prop = create_property(
        user_email="pytest_list_country@example.com",
        name="Country Summary Test",
        plot_spec={
            "plot_size_sqft": 1200, "plot_length_ft": 40, "plot_width_ft": 30,
            "region": "thailand", "currency": "THB", "country": "Thailand",
            "entrance_direction": "east", "road_facing_side": "east",
        },
        selections={}, labor_selections={}, site_elements=[], floors=[],
    )
    summaries = list_properties_for_user("pytest_list_country@example.com")
    match = next(s for s in summaries if s["property_id"] == prop["property_id"])
    assert match["country"] == "Thailand"


def test_team_seats_sharing_full_http_flow():
    """Backs the team_seats tier feature end-to-end: sharing requires
    the owner's tier to include it, a shared collaborator gets full
    view/edit access without needing their own subscription, and
    account-level actions (deleting, changing who it's shared with)
    stay owner-only even for a shared collaborator."""
    from backend.api import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    def authed_headers(email):
        code = create_otp(email)
        r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
        return {"Authorization": f"Bearer {r.json()['session_token']}"}

    owner_email = "team_seats_owner@example.com"
    owner_headers = authed_headers(owner_email)

    create_resp = client.post("/api/properties", json={
        "name": "Team Test House",
        "plot_spec": {
            "plot_size_sqft": 1200, "plot_length_ft": 40, "plot_width_ft": 30,
            "region": "india", "currency": "INR",
            "entrance_direction": "north", "road_facing_side": "north",
        },
        "selections": {}, "labor_selections": {}, "site_elements": [], "floors": [],
    }, headers=owner_headers)
    assert create_resp.status_code == 403  # no active subscription yet

    upsert_subscription(email=owner_email, tier_id="studio_starter", dodo_subscription_id="sub_team_owner_starter", status="active")
    create_resp = client.post("/api/properties", json={
        "name": "Team Test House",
        "plot_spec": {
            "plot_size_sqft": 1200, "plot_length_ft": 40, "plot_width_ft": 30,
            "region": "india", "currency": "INR",
            "entrance_direction": "north", "road_facing_side": "north",
        },
        "selections": {}, "labor_selections": {}, "site_elements": [],
        "floors": [{"floor_number": 0, "floor_label": "Ground Floor", "rooms": []}],
    }, headers=owner_headers)
    assert create_resp.status_code == 200
    property_id = create_resp.json()["property_id"]

    # Starter tier does NOT include team_seats -- sharing should be blocked
    share_blocked = client.post(f"/api/properties/{property_id}/share", json={"emails": ["teammate@example.com"]}, headers=owner_headers)
    assert share_blocked.status_code == 403

    # Upgrade to Unlimited, which DOES include team_seats
    upsert_subscription(email=owner_email, tier_id="studio_unlimited", dodo_subscription_id="sub_team_owner_unlimited", status="active")
    share_resp = client.post(f"/api/properties/{property_id}/share", json={"emails": ["teammate@example.com"]}, headers=owner_headers)
    assert share_resp.status_code == 200
    assert share_resp.json()["shared_with_emails"] == ["teammate@example.com"]

    # The teammate (no subscription of their own at all) can now view and edit it
    teammate_headers = authed_headers("teammate@example.com")
    view_resp = client.get(f"/api/properties/{property_id}", headers=teammate_headers)
    assert view_resp.status_code == 200

    update_resp = client.put(f"/api/properties/{property_id}", json={"name": "Renamed by Teammate"}, headers=teammate_headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Renamed by Teammate"

    # But the teammate cannot delete it or change sharing
    delete_blocked = client.delete(f"/api/properties/{property_id}", headers=teammate_headers)
    assert delete_blocked.status_code == 403

    reshare_blocked = client.post(f"/api/properties/{property_id}/share", json={"emails": []}, headers=teammate_headers)
    assert reshare_blocked.status_code == 403

    # The teammate sees it in their "shared with me" list, correctly attributed to the owner
    shared_list = client.get("/api/properties/shared-with-me", headers=teammate_headers)
    assert shared_list.status_code == 200
    assert len(shared_list.json()["properties"]) == 1
    assert shared_list.json()["properties"][0]["owner_email"] == owner_email

    # A genuinely unrelated third party still cannot access it at all
    stranger_headers = authed_headers("random_stranger@example.com")
    stranger_resp = client.get(f"/api/properties/{property_id}", headers=stranger_headers)
    assert stranger_resp.status_code == 403


def test_supplier_preferences_persist_through_the_real_http_save_flow():
    """The real, explicit bug this fix closes: supplier-preference
    checkboxes previously lived only in React state and silently
    vanished on reload with no error shown. Confirms the full round trip
    through the actual HTTP endpoints a real save/reload uses."""
    from backend.api import app
    from fastapi.testclient import TestClient
    from backend.subscription_store import upsert_subscription

    client = TestClient(app)

    def authed_headers(email):
        code = create_otp(email)
        r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
        return {"Authorization": f"Bearer {r.json()['session_token']}"}

    email = "supplier_pref_test@example.com"
    headers = authed_headers(email)
    upsert_subscription(email=email, tier_id="studio_starter", dodo_subscription_id="sub_suppref", status="active")

    create_resp = client.post("/api/properties", json={
        "name": "Supplier Pref Test House",
        "plot_spec": {
            "plot_size_sqft": 1200, "plot_length_ft": 40, "plot_width_ft": 30,
            "region": "india", "currency": "INR",
            "entrance_direction": "north", "road_facing_side": "north",
        },
        "selections": {"flooring": "vitrified_tile"}, "labor_selections": {}, "site_elements": [],
        "floors": [{"floor_number": 1, "floor_label": "Ground", "rooms": []}],
        "supplier_preferences": {"vitrified_tile": ["Kajaria Ceramics"]},
    }, headers=headers)
    assert create_resp.status_code == 200
    assert create_resp.json()["supplier_preferences"] == {"vitrified_tile": ["Kajaria Ceramics"]}
    property_id = create_resp.json()["property_id"]
    floor_id = create_resp.json()["floors"][0]["floor_id"]

    # Simulate reloading the page -- a fresh GET must show the same preference
    get_resp = client.get(f"/api/properties/{property_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["supplier_preferences"] == {"vitrified_tile": ["Kajaria Ceramics"]}

    # Simulate the user changing their preference and hitting Save (sync)
    sync_resp = client.put(f"/api/properties/{property_id}/sync", json={
        "supplier_preferences": {"vitrified_tile": ["Kajaria Ceramics", "Somany Ceramics"]},
        "floors": [{"floor_id": floor_id, "floor_number": 1, "floor_label": "Ground", "rooms": []}],
    }, headers=headers)
    assert sync_resp.status_code == 200
    assert sync_resp.json()["supplier_preferences"] == {"vitrified_tile": ["Kajaria Ceramics", "Somany Ceramics"]}

    # Simulate reloading again -- the updated preference must still be there
    get_resp_2 = client.get(f"/api/properties/{property_id}", headers=headers)
    assert get_resp_2.json()["supplier_preferences"] == {"vitrified_tile": ["Kajaria Ceramics", "Somany Ceramics"]}


def test_property_created_without_supplier_preferences_defaults_cleanly():
    """Must never error for a request that doesn't include this field at
    all -- an omitted field is not the same as a malformed request."""
    from backend.api import app
    from fastapi.testclient import TestClient
    from backend.subscription_store import upsert_subscription

    client = TestClient(app)

    def authed_headers(email):
        code = create_otp(email)
        r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
        return {"Authorization": f"Bearer {r.json()['session_token']}"}

    email = "supplier_pref_default_test@example.com"
    headers = authed_headers(email)
    upsert_subscription(email=email, tier_id="studio_starter", dodo_subscription_id="sub_suppref2", status="active")

    create_resp = client.post("/api/properties", json={
        "name": "No Supplier Prefs House",
        "plot_spec": {
            "plot_size_sqft": 1200, "plot_length_ft": 40, "plot_width_ft": 30,
            "region": "india", "currency": "INR",
            "entrance_direction": "north", "road_facing_side": "north",
        },
        "selections": {}, "labor_selections": {}, "site_elements": [],
        "floors": [{"floor_number": 1, "floor_label": "Ground", "rooms": []}],
    }, headers=headers)
    assert create_resp.status_code == 200
    assert create_resp.json()["supplier_preferences"] == {}


def test_export_returns_a_reimportable_shape_without_server_assigned_fields():
    """Confirms the exported JSON is a real, faithful shape (matching
    what /api/properties accepts) and deliberately excludes
    server-assigned/ownership fields that shouldn't be re-imported as-is."""
    headers = _signin_with_tier("pytest_export_shape@example.com")
    payload = _base_payload("Export Shape Test")
    payload["floors"] = [{"floor_number": 0, "floor_label": "Ground Floor", "rooms": [{"name": "Kitchen", "x": 0, "y": 0, "length": 8, "width": 6}]}]
    created = client.post("/api/properties", headers=headers, json=payload).json()

    r = client.get(f"/api/properties/{created['property_id']}/export", headers=headers)
    assert r.status_code == 200
    exported = r.json()

    assert "property_id" not in exported
    assert "user_email" not in exported
    assert "locked" not in exported
    assert "shared_with_emails" not in exported
    assert exported["name"] == "Export Shape Test"
    assert exported["floors"][0]["rooms"][0]["name"] == "Kitchen"


def test_export_requires_ownership_or_shared_access():
    headers = _signin_with_tier("pytest_export_owner@example.com")
    created = client.post("/api/properties", headers=headers, json=_base_payload()).json()

    other_headers = _signin_with_tier("pytest_export_stranger@example.com")
    r = client.get(f"/api/properties/{created['property_id']}/export", headers=other_headers)
    assert r.status_code == 403


def test_full_export_then_import_round_trip_is_lossless():
    """The real, direct proof of the actual feature this was built for:
    export a design, delete it (freeing its saved_designs_limit slot),
    then import it back and confirm it's the same design."""
    headers = _signin_with_tier("pytest_roundtrip@example.com")
    payload = _base_payload("Round Trip Test")
    payload["floors"] = [
        {"floor_number": 0, "floor_label": "Ground Floor", "rooms": [{"name": "Living Room", "x": 0, "y": 0, "length": 12, "width": 10}]},
        {"floor_number": 1, "floor_label": "First Floor", "rooms": [{"name": "Bedroom", "x": 0, "y": 0, "length": 10, "width": 10}]},
    ]
    created = client.post("/api/properties", headers=headers, json=payload).json()
    exported = client.get(f"/api/properties/{created['property_id']}/export", headers=headers).json()

    client.delete(f"/api/properties/{created['property_id']}", headers=headers)
    assert client.get(f"/api/properties/{created['property_id']}", headers=headers).status_code == 404

    reimported = client.post("/api/properties/import", headers=headers, json=exported).json()
    assert reimported["property_id"] != created["property_id"]  # a genuinely new design, not the same row
    assert reimported["name"] == "Round Trip Test"
    assert len(reimported["floors"]) == 2
    assert reimported["floors"][1]["rooms"][0]["name"] == "Bedroom"


def test_import_requires_active_subscription():
    code = create_otp("pytest_import_nosub@example.com")
    r = client.post("/api/auth/verify-otp", json={"email": "pytest_import_nosub@example.com", "code": code})
    headers = {"Authorization": f"Bearer {r.json()['session_token']}"}
    r2 = client.post("/api/properties/import", headers=headers, json=_base_payload())
    assert r2.status_code == 403


def test_import_respects_saved_designs_limit():
    """Real, direct proof importing doesn't bypass the same quota a
    normal save is gated by."""
    headers = _signin_with_tier("pytest_import_limit@example.com", tier_id="studio_starter")
    payload = _base_payload("Filler")
    client.post("/api/properties", headers=headers, json=payload)
    client.post("/api/properties", headers=headers, json=payload)  # studio_starter's saved_designs_limit is 2

    r = client.post("/api/properties/import", headers=headers, json=_base_payload("One Too Many"))
    assert r.status_code == 403
    assert "saved design limit" in r.json()["detail"].lower()


def test_import_rejects_a_design_with_no_floors():
    headers = _signin_with_tier("pytest_import_nofloors@example.com")
    payload = _base_payload()
    payload["floors"] = []
    r = client.post("/api/properties/import", headers=headers, json=payload)
    assert r.status_code == 400
