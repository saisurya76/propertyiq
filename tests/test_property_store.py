import os
os.environ.setdefault("ADMIN_DASHBOARD_PASSWORD", "test-admin-pw")
os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test")
os.environ.setdefault("DODO_REPORT_PRODUCT_ID", "test")

from fastapi.testclient import TestClient
from backend.api import app
from backend.auth_store import create_otp
from backend.subscription_store import upsert_subscription

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
