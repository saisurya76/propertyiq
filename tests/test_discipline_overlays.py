from backend.discipline_overlays import (
    compute_structural_overlay,
    compute_plumbing_overlay,
    compute_electrical_overlay,
    STRUCTURAL_DISCLAIMER,
    PLUMBING_DISCLAIMER,
    ELECTRICAL_DISCLAIMER,
)

SAMPLE_ROOMS = [
    {"name": "Living Room", "x": 0, "y": 0, "length": 20, "width": 15},
    {"name": "Master Bathroom", "x": 20, "y": 0, "length": 8, "width": 8},
    {"name": "Kitchen", "x": 0, "y": 15, "length": 12, "width": 10},
    {"name": "Bedroom 1", "x": 12, "y": 15, "length": 10, "width": 10},
]
PLOT_LENGTH, PLOT_WIDTH = 30, 25


def test_structural_overlay_includes_every_disclaimer_and_a_wall_per_room_plus_perimeter():
    result = compute_structural_overlay(SAMPLE_ROOMS, PLOT_LENGTH, PLOT_WIDTH)
    assert result["disclaimer"] == STRUCTURAL_DISCLAIMER
    assert "NOT a structural engineer" in result["disclaimer"]
    # 1 perimeter wall + 1 wall per real room
    assert len(result["walls"]) == 1 + len(SAMPLE_ROOMS)
    assert result["walls"][0]["kind"] == "perimeter"


def test_structural_overlay_deduplicates_shared_corners_into_single_columns():
    """A real, meaningful check: adjacent rooms sharing a corner must
    produce ONE column there, not two overlapping ones."""
    result = compute_structural_overlay(SAMPLE_ROOMS, PLOT_LENGTH, PLOT_WIDTH)
    # 4 rooms x 4 corners = 16 raw corners, but several coincide
    # (Living Room/Bathroom share one, Kitchen/Bedroom share another, etc)
    assert len(result["columns"]) < 16
    assert len(result["columns"]) == 12  # confirmed exact count for this specific layout

    coords = [(c["x"], c["y"]) for c in result["columns"]]
    assert len(coords) == len(set(coords))  # genuinely no duplicate coordinates


def test_structural_overlay_with_no_rooms_still_returns_the_perimeter():
    result = compute_structural_overlay([], PLOT_LENGTH, PLOT_WIDTH)
    assert len(result["walls"]) == 1
    assert result["columns"] == []


def test_plumbing_overlay_only_places_fixtures_in_genuinely_wet_rooms():
    result = compute_plumbing_overlay(SAMPLE_ROOMS, PLOT_LENGTH, PLOT_WIDTH)
    assert result["disclaimer"] == PLUMBING_DISCLAIMER
    fixture_rooms = {f["room_name"] for f in result["fixtures"]}
    assert fixture_rooms == {"Master Bathroom", "Kitchen"}
    assert "Living Room" not in fixture_rooms
    assert "Bedroom 1" not in fixture_rooms


def test_plumbing_overlay_creates_one_pipe_run_per_fixture_to_a_single_riser():
    result = compute_plumbing_overlay(SAMPLE_ROOMS, PLOT_LENGTH, PLOT_WIDTH)
    assert len(result["pipe_runs"]) == len(result["fixtures"])
    assert result["main_riser"] is not None
    for run in result["pipe_runs"]:
        assert run["to"]["x"] == result["main_riser"]["x"]
        assert run["to"]["y"] == result["main_riser"]["y"]


def test_plumbing_overlay_riser_snaps_to_a_real_plot_edge():
    result = compute_plumbing_overlay(SAMPLE_ROOMS, PLOT_LENGTH, PLOT_WIDTH)
    riser = result["main_riser"]
    assert riser["edge"] in ("north", "south", "east", "west")
    # Riser coordinates must genuinely sit on the claimed edge
    if riser["edge"] in ("south",):
        assert riser["y"] == 0
    if riser["edge"] == "north":
        assert riser["y"] == PLOT_WIDTH
    if riser["edge"] == "west":
        assert riser["x"] == 0
    if riser["edge"] == "east":
        assert riser["x"] == PLOT_LENGTH


def test_plumbing_overlay_with_no_wet_rooms_is_honestly_empty_not_fabricated():
    """The real honesty guarantee: no bathroom/kitchen exists in this
    plan -> no fixtures/pipes/riser invented to fill the space."""
    no_wet_rooms = [{"name": "Living Room", "x": 0, "y": 0, "length": 20, "width": 15}]
    result = compute_plumbing_overlay(no_wet_rooms, PLOT_LENGTH, PLOT_WIDTH)
    assert result["fixtures"] == []
    assert result["pipe_runs"] == []
    assert result["main_riser"] is None


def test_electrical_overlay_places_one_light_fan_and_switch_per_real_room():
    result = compute_electrical_overlay(SAMPLE_ROOMS, PLOT_LENGTH, PLOT_WIDTH)
    assert result["disclaimer"] == ELECTRICAL_DISCLAIMER
    assert len(result["lights"]) == len(SAMPLE_ROOMS)
    assert len(result["fans"]) == len(SAMPLE_ROOMS)
    assert len(result["switches"]) == len(SAMPLE_ROOMS)
    assert len(result["sockets"]) == len(SAMPLE_ROOMS) * 2


def test_electrical_overlay_fan_points_are_genuinely_at_room_centers():
    result = compute_electrical_overlay(SAMPLE_ROOMS, PLOT_LENGTH, PLOT_WIDTH)
    living_room_fan = next(f for f in result["fans"] if f["room_name"] == "Living Room")
    assert living_room_fan["x"] == 0 + 20 / 2
    assert living_room_fan["y"] == 0 + 15 / 2


def test_electrical_overlay_light_is_genuinely_offset_from_the_fan_in_the_same_room():
    """Real rooms commonly have both a fan and a light -- they must not
    render as two markers sitting exactly on top of each other."""
    result = compute_electrical_overlay(SAMPLE_ROOMS, PLOT_LENGTH, PLOT_WIDTH)
    for room in SAMPLE_ROOMS:
        light = next(l for l in result["lights"] if l["room_name"] == room["name"])
        fan = next(f for f in result["fans"] if f["room_name"] == room["name"])
        assert (light["x"], light["y"]) != (fan["x"], fan["y"])


def test_every_discrete_element_type_gets_stable_sequential_labels():
    """The real, explicit request this labeling exists for: columns as
    C1/C2/C3, and every other discrete element type similarly."""
    structural = compute_structural_overlay(SAMPLE_ROOMS, PLOT_LENGTH, PLOT_WIDTH)
    column_labels = [c["label"] for c in structural["columns"]]
    assert column_labels == [f"C{i+1}" for i in range(len(structural["columns"]))]

    plumbing = compute_plumbing_overlay(SAMPLE_ROOMS, PLOT_LENGTH, PLOT_WIDTH)
    fixture_labels = [f["label"] for f in plumbing["fixtures"]]
    assert fixture_labels == [f"FX{i+1}" for i in range(len(plumbing["fixtures"]))]
    assert plumbing["main_riser"]["label"] == "MR"

    electrical = compute_electrical_overlay(SAMPLE_ROOMS, PLOT_LENGTH, PLOT_WIDTH)
    assert [l["label"] for l in electrical["lights"]] == [f"L{i+1}" for i in range(len(electrical["lights"]))]
    assert [f["label"] for f in electrical["fans"]] == [f"FN{i+1}" for i in range(len(electrical["fans"]))]
    assert [s["label"] for s in electrical["switches"]] == [f"SW{i+1}" for i in range(len(electrical["switches"]))]
    assert [s["label"] for s in electrical["sockets"]] == [f"SO{i+1}" for i in range(len(electrical["sockets"]))]


def test_labels_are_stable_and_deterministic_across_repeated_calls():
    """The same floor plan must always produce the same labels -- a
    real requirement for the future spec-mapping phase, where a label
    needs to reliably refer to the same physical element every time."""
    result1 = compute_structural_overlay(SAMPLE_ROOMS, PLOT_LENGTH, PLOT_WIDTH)
    result2 = compute_structural_overlay(SAMPLE_ROOMS, PLOT_LENGTH, PLOT_WIDTH)
    labels1 = [(c["label"], c["x"], c["y"]) for c in result1["columns"]]
    labels2 = [(c["label"], c["x"], c["y"]) for c in result2["columns"]]
    assert labels1 == labels2


def test_all_three_overlays_ignore_rooms_with_no_name_or_zero_dimensions():
    """Rooms mid-creation in the wizard (blank name, or not yet sized)
    must never appear in any overlay -- matching the same _valid_rooms
    filter the live preview itself already applies."""
    rooms_with_junk = SAMPLE_ROOMS + [
        {"name": "", "x": 5, "y": 5, "length": 5, "width": 5},
        {"name": "Half-drawn Room", "x": 5, "y": 5, "length": 0, "width": 5},
    ]
    structural = compute_structural_overlay(rooms_with_junk, PLOT_LENGTH, PLOT_WIDTH)
    electrical = compute_electrical_overlay(rooms_with_junk, PLOT_LENGTH, PLOT_WIDTH)
    assert len(structural["walls"]) == 1 + len(SAMPLE_ROOMS)  # junk rooms excluded
    assert len(electrical["lights"]) == len(SAMPLE_ROOMS)


def test_endpoint_returns_structural_overlay_publicly():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.post("/api/construction-studio/discipline-overlay?discipline=structural", json={
        "rooms": SAMPLE_ROOMS, "plot_length_ft": PLOT_LENGTH, "plot_width_ft": PLOT_WIDTH,
    })
    assert r.status_code == 200
    assert r.json()["discipline"] == "structural"
    assert "NOT a structural engineer" in r.json()["disclaimer"]


def test_endpoint_returns_plumbing_overlay_publicly():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.post("/api/construction-studio/discipline-overlay?discipline=plumbing", json={
        "rooms": SAMPLE_ROOMS, "plot_length_ft": PLOT_LENGTH, "plot_width_ft": PLOT_WIDTH,
    })
    assert r.status_code == 200
    assert r.json()["discipline"] == "plumbing"


def test_endpoint_returns_electrical_overlay_publicly():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.post("/api/construction-studio/discipline-overlay?discipline=electrical", json={
        "rooms": SAMPLE_ROOMS, "plot_length_ft": PLOT_LENGTH, "plot_width_ft": PLOT_WIDTH,
    })
    assert r.status_code == 200
    assert r.json()["discipline"] == "electrical"


def test_endpoint_rejects_invalid_discipline():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.post("/api/construction-studio/discipline-overlay?discipline=feng_shui", json={
        "rooms": SAMPLE_ROOMS, "plot_length_ft": PLOT_LENGTH, "plot_width_ft": PLOT_WIDTH,
    })
    assert r.status_code == 400


def test_endpoint_rejects_invalid_plot_dimensions():
    from fastapi.testclient import TestClient
    from backend.api import app

    client = TestClient(app)
    r = client.post("/api/construction-studio/discipline-overlay?discipline=structural", json={
        "rooms": SAMPLE_ROOMS, "plot_length_ft": 0, "plot_width_ft": PLOT_WIDTH,
    })
    assert r.status_code == 400
