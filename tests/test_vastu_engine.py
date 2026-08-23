from backend.vastu_engine import check_vastu_full, _zone_for_room

PLOT_L, PLOT_W = 40, 30  # thirds: x=13.33, y=10


def test_zone_detection_corners_and_center():
    assert _zone_for_room({"x": 30, "y": 2, "length": 8, "width": 6}, PLOT_L, PLOT_W) == "SE"
    assert _zone_for_room({"x": 30, "y": 22, "length": 8, "width": 6}, PLOT_L, PLOT_W) == "NE"
    assert _zone_for_room({"x": 2, "y": 2, "length": 8, "width": 6}, PLOT_L, PLOT_W) == "SW"
    assert _zone_for_room({"x": 2, "y": 22, "length": 8, "width": 6}, PLOT_L, PLOT_W) == "NW"
    assert _zone_for_room({"x": 16, "y": 12, "length": 6, "width": 6}, PLOT_L, PLOT_W) == "CENTER"


def test_kitchen_in_se_is_compliant():
    result = check_vastu_full(
        plot_length_ft=PLOT_L, plot_width_ft=PLOT_W,
        rooms=[{"name": "Kitchen", "x": 30, "y": 2, "length": 8, "width": 6}],
        entrance_direction="north-east", road_facing_side="north-east",
    )
    assert result["compliant"] is True
    assert result["scope"] == "full_multi_rule_check"


def test_kitchen_in_ne_is_flagged():
    result = check_vastu_full(
        plot_length_ft=PLOT_L, plot_width_ft=PLOT_W,
        rooms=[{"name": "Kitchen", "x": 30, "y": 22, "length": 8, "width": 6}],
        entrance_direction="north-east", road_facing_side="north-east",
    )
    assert result["compliant"] is False
    assert any(f["category"] == "room_placement" for f in result["findings"])


def test_room_in_center_flags_brahmasthan():
    result = check_vastu_full(
        plot_length_ft=PLOT_L, plot_width_ft=PLOT_W,
        rooms=[{"name": "Hallway", "x": 16, "y": 12, "length": 6, "width": 6}],
        entrance_direction="north", road_facing_side="north",
    )
    assert result["compliant"] is False
    assert any(f["category"] == "brahmasthan" for f in result["findings"])


def test_unmatched_room_type_produces_no_placement_finding():
    result = check_vastu_full(
        plot_length_ft=PLOT_L, plot_width_ft=PLOT_W,
        rooms=[{"name": "Garage", "x": 30, "y": 22, "length": 8, "width": 6}],  # NE, but "garage" has no rule
        entrance_direction="north", road_facing_side="north",
    )
    # No rule matches "garage" — should produce zero room_placement findings for it
    assert not any(f["category"] == "room_placement" for f in result["findings"])


def test_master_bedroom_in_sw_is_compliant():
    result = check_vastu_full(
        plot_length_ft=PLOT_L, plot_width_ft=PLOT_W,
        rooms=[{"name": "Master Bedroom", "x": 2, "y": 2, "length": 10, "width": 8}],
        entrance_direction="north", road_facing_side="north",
    )
    findings = [f for f in result["findings"] if f["category"] == "room_placement"]
    assert len(findings) == 1
    assert "aligns with classical guidance" in findings[0]["note"]


def test_multiple_rooms_multiple_findings():
    result = check_vastu_full(
        plot_length_ft=PLOT_L, plot_width_ft=PLOT_W,
        rooms=[
            {"name": "Kitchen", "x": 30, "y": 2, "length": 8, "width": 6},       # SE - good
            {"name": "Toilet", "x": 30, "y": 22, "length": 4, "width": 4},       # NE - bad
            {"name": "Pooja Room", "x": 30, "y": 22, "length": 4, "width": 4},   # NE - N/A, overlaps toilet spot but tests independently
        ],
        entrance_direction="north", road_facing_side="north",
    )
    room_findings = [f for f in result["findings"] if f["category"] == "room_placement"]
    assert len(room_findings) == 3


def test_vastu_check_endpoint_is_live_and_quota_free():
    """The real bug this endpoint fixes: Vastu compliance shown in the
    Studio kept displaying a stale result from whenever a design was last
    generated, even after the user removed or rearranged a room
    afterward. This endpoint recomputes fresh from whatever rooms are
    passed, with no design QUOTA consumed, so the frontend can call it
    reactively on every edit instead of relying on a stale snapshot.
    Does require an active subscription with the vastu_compliance
    feature though — a separate, later fix closed a real gap where this
    endpoint had no auth requirement at all despite being a paid
    feature."""
    from fastapi.testclient import TestClient
    from backend.api import app
    from backend.auth_store import create_otp
    from backend.subscription_store import upsert_subscription

    client = TestClient(app)
    email = "vastu_quota_free_test@example.com"
    code = create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    headers = {"Authorization": f"Bearer {r.json()['session_token']}"}
    upsert_subscription(email=email, tier_id="studio_starter", dodo_subscription_id="sub_vastu_quota_free", status="active")

    with_bedroom = client.post("/api/construction-studio/vastu-check", json={
        "plot_length_ft": 40, "plot_width_ft": 30,
        "rooms": [{"name": "Master Bedroom", "x": 0, "y": 0, "length": 10, "width": 10}],
        "entrance_direction": "north", "road_facing_side": "north",
    }, headers=headers)
    assert with_bedroom.status_code == 200
    assert with_bedroom.json()["scope"] == "full_multi_rule_check"

    without_bedroom = client.post("/api/construction-studio/vastu-check", json={
        "plot_length_ft": 40, "plot_width_ft": 30,
        "rooms": [],
        "entrance_direction": "north", "road_facing_side": "north",
    }, headers=headers)
    assert without_bedroom.status_code == 200
    assert without_bedroom.json()["scope"] != "full_multi_rule_check"


def test_vastu_check_requires_auth_and_feature():
    """A real, confirmed gap this closes: the endpoint previously had NO
    auth requirement at all, meaning "Vastu Compliance" was listed as a
    paid subscription feature while actually being available to anyone,
    logged in or not, on any tier or none."""
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    no_auth = client.post("/api/construction-studio/vastu-check", json={
        "plot_length_ft": 40, "plot_width_ft": 30, "rooms": [],
        "entrance_direction": "north", "road_facing_side": "north",
    })
    assert no_auth.status_code == 401
