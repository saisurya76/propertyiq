from backend.adjacency_engine import evaluate_adjacency, rooms_are_adjacent


def test_kitchen_bedroom_adjacency_flagged_universally():
    rooms = [
        {"_key": "k1", "name": "Kitchen", "x": 0, "y": 0, "length": 10, "width": 10},
        {"_key": "b1", "name": "Bedroom", "x": 10, "y": 0, "length": 10, "width": 10},
    ]
    for style in ("modern_open_plan", "traditional_zoned", "minimalist"):
        result = evaluate_adjacency(rooms, style=style)
        assert result["compliant"] is False, f"kitchen-bedroom adjacency should be flagged in {style}"
        assert result["room_status"]["k1"] == "warning"
        assert result["room_status"]["b1"] == "warning"


def test_kitchen_living_adjacency_style_dependent():
    rooms = [
        {"_key": "k1", "name": "Kitchen", "x": 0, "y": 0, "length": 10, "width": 10},
        {"_key": "l1", "name": "Living Room", "x": 10, "y": 0, "length": 10, "width": 10},
    ]
    modern = evaluate_adjacency(rooms, style="modern_open_plan")
    assert modern["room_status"]["k1"] == "good"

    traditional = evaluate_adjacency(rooms, style="traditional_zoned")
    assert "k1" not in traditional["room_status"]
    assert traditional["compliant"] is True


def test_bedroom_bathroom_adjacency_always_good():
    rooms = [
        {"_key": "b1", "name": "Bedroom", "x": 0, "y": 0, "length": 10, "width": 10},
        {"_key": "wc1", "name": "Bathroom", "x": 10, "y": 0, "length": 6, "width": 6},
    ]
    result = evaluate_adjacency(rooms, style="modern_open_plan")
    assert result["room_status"]["b1"] == "good"
    assert result["compliant"] is True


def test_unrecognized_room_names_skipped_not_flagged():
    rooms = [
        {"_key": "x1", "name": "Sunroom", "x": 0, "y": 0, "length": 10, "width": 10},
        {"_key": "x2", "name": "Mudroom", "x": 10, "y": 0, "length": 10, "width": 10},
    ]
    result = evaluate_adjacency(rooms, style="modern_open_plan")
    assert result["compliant"] is True
    assert result["findings"] == []


def test_rooms_far_apart_no_findings():
    rooms = [
        {"_key": "k1", "name": "Kitchen", "x": 0, "y": 0, "length": 10, "width": 10},
        {"_key": "b1", "name": "Bedroom", "x": 30, "y": 30, "length": 10, "width": 10},
    ]
    result = evaluate_adjacency(rooms, style="modern_open_plan")
    assert result["compliant"] is True
    assert result["room_status"] == {}


def test_geometric_adjacency_corner_touch_not_counted():
    a = {"x": 0, "y": 0, "length": 10, "width": 10}
    corner_touch = {"x": 10, "y": 10, "length": 10, "width": 10}
    assert rooms_are_adjacent(a, corner_touch) is False


def test_geometric_adjacency_shared_wall_counted():
    a = {"x": 0, "y": 0, "length": 10, "width": 10}
    shared_wall = {"x": 10, "y": 0, "length": 10, "width": 10}
    assert rooms_are_adjacent(a, shared_wall) is True


def test_invalid_style_falls_back_to_default():
    rooms = [
        {"_key": "k1", "name": "Kitchen", "x": 0, "y": 0, "length": 10, "width": 10},
        {"_key": "l1", "name": "Living Room", "x": 10, "y": 0, "length": 10, "width": 10},
    ]
    result = evaluate_adjacency(rooms, style="not_a_real_style")
    assert result["style"] == "modern_open_plan"


def test_adjacency_check_api_endpoint():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.post("/api/construction-studio/adjacency-check", json={
        "rooms": [
            {"name": "Kitchen", "x": 0, "y": 0, "length": 10, "width": 10},
            {"name": "Bedroom", "x": 10, "y": 0, "length": 10, "width": 10},
        ],
        "style": "modern_open_plan",
    })
    assert r.status_code == 200
    assert r.json()["compliant"] is False


def test_adjacency_styles_api_endpoint():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.get("/api/construction-studio/adjacency-styles")
    assert r.status_code == 200
    style_ids = {s["id"] for s in r.json()["styles"]}
    assert style_ids == {"modern_open_plan", "minimalist", "traditional_zoned"}
