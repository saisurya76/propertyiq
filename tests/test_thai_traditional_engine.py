from backend.thai_traditional_engine import check_thai_orientation, check_thai_traditional_full


def test_east_entrance_favorable():
    result = check_thai_orientation(entrance_direction="east")
    assert result["compliant"] is True


def test_west_entrance_unfavorable():
    result = check_thai_orientation(entrance_direction="west")
    assert result["compliant"] is False
    assert "west" in result["notes"][0].lower()


def test_north_entrance_neutral_still_compliant():
    result = check_thai_orientation(entrance_direction="north")
    assert result["compliant"] is True


def test_kitchen_bedroom_adjacency_flagged():
    rooms = [
        {"name": "Kitchen", "x": 0, "y": 0, "length": 10, "width": 10},
        {"name": "Bedroom", "x": 10, "y": 0, "length": 10, "width": 10},
    ]
    result = check_thai_traditional_full(rooms=rooms, entrance_direction="east")
    assert result["compliant"] is False
    assert any("Ruean Thai" in f["note"] or "Huean Fai" in f["note"] for f in result["findings"])


def test_shrine_bathroom_adjacency_flagged():
    rooms = [
        {"name": "Shrine Room", "x": 0, "y": 0, "length": 8, "width": 8},
        {"name": "Bathroom", "x": 8, "y": 0, "length": 6, "width": 6},
    ]
    result = check_thai_traditional_full(rooms=rooms, entrance_direction="east")
    assert result["compliant"] is False


def test_shrine_kitchen_adjacency_flagged():
    rooms = [
        {"name": "Shrine Room", "x": 0, "y": 0, "length": 8, "width": 8},
        {"name": "Kitchen", "x": 8, "y": 0, "length": 10, "width": 10},
    ]
    result = check_thai_traditional_full(rooms=rooms, entrance_direction="east")
    assert result["compliant"] is False


def test_rooms_far_apart_only_orientation_matters():
    rooms = [
        {"name": "Kitchen", "x": 0, "y": 0, "length": 10, "width": 10},
        {"name": "Bedroom", "x": 30, "y": 30, "length": 10, "width": 10},
    ]
    result = check_thai_traditional_full(rooms=rooms, entrance_direction="east")
    assert result["compliant"] is True


def test_unrecognized_room_names_skipped():
    rooms = [
        {"name": "Sunroom", "x": 0, "y": 0, "length": 10, "width": 10},
        {"name": "Study", "x": 10, "y": 0, "length": 10, "width": 10},
    ]
    result = check_thai_traditional_full(rooms=rooms, entrance_direction="east")
    assert result["compliant"] is True
    assert len(result["findings"]) == 1  # only the orientation note


def test_geometric_adjacency_corner_touch_not_counted():
    rooms = [
        {"name": "Kitchen", "x": 0, "y": 0, "length": 10, "width": 10},
        {"name": "Bedroom", "x": 10, "y": 10, "length": 10, "width": 10},
    ]
    result = check_thai_traditional_full(rooms=rooms, entrance_direction="east")
    assert result["compliant"] is True  # diagonal corner touch, not a real shared wall


def test_vastu_check_endpoint_routes_by_country():
    """Real integration point: the same /vastu-check endpoint the frontend
    already calls now routes to the Thai engine when country is Thailand,
    and preserves the exact prior India/Vastu-only behavior when country
    is omitted entirely — no breaking change for existing callers."""
    from fastapi.testclient import TestClient
    from backend.api import app
    from backend.auth_store import create_otp
    from backend.subscription_store import upsert_subscription

    client = TestClient(app)
    email = "vastu_routing_test@example.com"
    code = create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    headers = {"Authorization": f"Bearer {r.json()['session_token']}"}
    upsert_subscription(email=email, tier_id="studio_starter", dodo_subscription_id="sub_vastu_routing", status="active")

    thailand = client.post("/api/construction-studio/vastu-check", json={
        "plot_length_ft": 40, "plot_width_ft": 30,
        "rooms": [
            {"name": "Kitchen", "x": 0, "y": 0, "length": 10, "width": 10},
            {"name": "Bedroom", "x": 10, "y": 0, "length": 10, "width": 10},
        ],
        "entrance_direction": "east", "road_facing_side": "east",
        "country": "Thailand",
    }, headers=headers)
    assert thailand.status_code == 200
    assert thailand.json()["scope"] == "thai_traditional_full_check"
    assert thailand.json()["compliant"] is False

    no_country = client.post("/api/construction-studio/vastu-check", json={
        "plot_length_ft": 40, "plot_width_ft": 30,
        "rooms": [{"name": "Kitchen", "x": 0, "y": 0, "length": 10, "width": 10}],
        "entrance_direction": "north", "road_facing_side": "north",
    }, headers=headers)
    assert no_country.status_code == 200
    assert no_country.json()["scope"] == "full_multi_rule_check"


def test_vastu_check_routes_correctly_with_stale_or_missing_country():
    """Real reported bug: resuming a saved Thailand property showed Vastu
    Compliance instead of Traditional Building Compliance, because country
    stayed at its default ("India") or was missing entirely on older saved
    designs, even though region correctly said "thailand". Country and
    region are treated as equally valid triggers (neither overrides the
    other) so this class of stale/missing-country bug can't recur."""
    from fastapi.testclient import TestClient
    from backend.api import app
    from backend.auth_store import create_otp
    from backend.subscription_store import upsert_subscription

    client = TestClient(app)
    email = "vastu_stale_country_test@example.com"
    code = create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    headers = {"Authorization": f"Bearer {r.json()['session_token']}"}
    upsert_subscription(email=email, tier_id="studio_starter", dodo_subscription_id="sub_vastu_stale_country", status="active")

    def check(country, region):
        return client.post("/api/construction-studio/vastu-check", json={
            "plot_length_ft": 40, "plot_width_ft": 30,
            "rooms": [
                {"name": "Kitchen", "x": 0, "y": 0, "length": 10, "width": 10},
                {"name": "Bedroom", "x": 10, "y": 0, "length": 10, "width": 10},
            ],
            "entrance_direction": "east", "road_facing_side": "east",
            "country": country, "region": region,
        }, headers=headers).json()

    # The exact reported bug: stale country="India" but region correctly thailand
    assert check("India", "thailand")["scope"] == "thai_traditional_full_check"
    # Country correctly says Thailand
    assert check("Thailand", "thailand")["scope"] == "thai_traditional_full_check"
    # Genuinely India, both agree
    assert check("India", "india")["scope"] == "full_multi_rule_check"
    # Country says Thailand even if region is inconsistent
    assert check("Thailand", "india")["scope"] == "thai_traditional_full_check"
    # Neither set at all (a very old design) -- falls back to Vastu, the original default
    assert check("", "")["scope"] == "full_multi_rule_check"


def test_vastu_check_no_specific_tradition_for_unresearched_countries():
    """A genuine architectural decision, not an oversight: a country with
    no real researched traditional-building system (Philippines, Vietnam,
    Indonesia, or any other added later) must NOT silently fall back to
    Vastu — showing "Vastu Compliance" for a Philippines property would
    be actively misleading, not just incomplete, since Vastu is a real,
    specific Indian tradition. Backward compatibility for designs saved
    before country/region existed is preserved separately (empty
    country/region still defaults to Vastu, unchanged)."""
    from fastapi.testclient import TestClient
    from backend.api import app
    from backend.auth_store import create_otp
    from backend.subscription_store import upsert_subscription

    client = TestClient(app)
    email = "vastu_no_tradition_test@example.com"
    code = create_otp(email)
    r = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    headers = {"Authorization": f"Bearer {r.json()['session_token']}"}
    upsert_subscription(email=email, tier_id="studio_starter", dodo_subscription_id="sub_vastu_no_tradition", status="active")

    def check(country, region):
        return client.post("/api/construction-studio/vastu-check", json={
            "plot_length_ft": 40, "plot_width_ft": 30,
            "rooms": [{"name": "Kitchen", "x": 0, "y": 0, "length": 10, "width": 10}],
            "entrance_direction": "east", "road_facing_side": "east",
            "country": country, "region": region,
        }, headers=headers).json()

    for country in ("Philippines", "Vietnam", "Indonesia"):
        result = check(country, "global")
        assert result["scope"] == "no_specific_tradition"
        assert result["compliant"] is True
        assert result["findings"] == []

    # Backward compatibility unchanged: empty country/region still means Vastu
    assert check("", "")["scope"] == "full_multi_rule_check"
    assert check("India", "india")["scope"] == "full_multi_rule_check"
