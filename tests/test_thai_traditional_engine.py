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

    client = TestClient(app)

    thailand = client.post("/api/construction-studio/vastu-check", json={
        "plot_length_ft": 40, "plot_width_ft": 30,
        "rooms": [
            {"name": "Kitchen", "x": 0, "y": 0, "length": 10, "width": 10},
            {"name": "Bedroom", "x": 10, "y": 0, "length": 10, "width": 10},
        ],
        "entrance_direction": "east", "road_facing_side": "east",
        "country": "Thailand",
    })
    assert thailand.status_code == 200
    assert thailand.json()["scope"] == "thai_traditional_full_check"
    assert thailand.json()["compliant"] is False

    no_country = client.post("/api/construction-studio/vastu-check", json={
        "plot_length_ft": 40, "plot_width_ft": 30,
        "rooms": [{"name": "Kitchen", "x": 0, "y": 0, "length": 10, "width": 10}],
        "entrance_direction": "north", "road_facing_side": "north",
    })
    assert no_country.status_code == 200
    assert no_country.json()["scope"] == "full_multi_rule_check"
