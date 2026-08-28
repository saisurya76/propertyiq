"""Computes schematic Structural/Plumbing/Electrical overlay elements
drawn over the exact same room footprint as the live floor plan preview
and DXF export.

CRITICAL HONESTY BOUNDARY, stated here and surfaced directly to the user
in every response this module produces: these are SCHEMATIC, rule-of-
thumb placements for visualization — a starting point to discuss with a
real engineer — NOT a licensed structural/plumbing/electrical engineer's
calculated design. Genuine structural design depends on real loads, soil
bearing capacity, and seismic zone; genuine plumbing/electrical design
depends on real fixture counts, pipe/wire sizing calculations, and local
code compliance — none of which this app has any way to know. Presenting
placements like these as construction-ready engineering would be
actively dangerous, not just inaccurate, so every function here returns
an explicit `disclaimer` field alongside its computed elements, and nothing
in this module should ever be described to the user as "your structural/
plumbing/electrical design" without that qualifier attached.

Every discrete point/component element (never linear connectors like
walls or pipe runs, which read naturally as unlabeled lines between
labeled points) carries a stable, sequential `label` — e.g. "C1", "C2"
for columns — assigned in a fixed, deterministic order (by position,
not by whatever order Python happens to iterate rooms in) so the same
floor plan always gets the same labels across repeated calls. These
labels are the real hook this module is being built toward: a future
phase will let the user map a real material/spec to a specific labeled
element (e.g. "C3 is a 9x9 inch column, 4-bar reinforcement").
"""

from typing import Any

STRUCTURAL_DISCLAIMER = (
    "Schematic column/wall placement for visualization only, using a common rule-of-thumb "
    "grid (columns at wall intersections/corners). This is NOT a structural engineer's "
    "calculated design — real column sizing and placement depends on actual loads, soil "
    "bearing capacity, and seismic zone. Have a licensed structural engineer review before construction."
)

PLUMBING_DISCLAIMER = (
    "Schematic fixture and pipe-run placement for visualization only, based on room names "
    "(bathroom/kitchen/utility). This is NOT a licensed plumber's or engineer's calculated "
    "design — real pipe sizing, venting, and routing depends on fixture counts, local code, "
    "and the actual plumbing main's location. Have a licensed plumber review before construction."
)

ELECTRICAL_DISCLAIMER = (
    "Schematic light/fan/switch/socket point placement for visualization only, one set per "
    "room using common conventions. This is NOT a licensed electrician's or engineer's "
    "calculated design — real circuit design, wire gauge, and panel sizing depends on actual "
    "electrical load calculations and local code. Have a licensed electrician review before construction."
)

# Keyword matching for room type detection — same lightweight, honest
# approach as adjacency_engine.py already uses elsewhere in this app
# (substring match on the room's own name, not a strict enum), since
# rooms are free-text named by the user, not selected from a fixed list.
_WET_ROOM_KEYWORDS = ["bathroom", "toilet", "washroom", "kitchen", "utility"]


def _is_wet_room(room_name: str) -> bool:
    name = (room_name or "").strip().lower()
    return any(keyword in name for keyword in _WET_ROOM_KEYWORDS)


def _valid_rooms(rooms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in rooms if r.get("name", "").strip() and r.get("length", 0) > 0 and r.get("width", 0) > 0]


def _label_elements(elements: list[dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
    """Assigns a stable, sequential label to each element, in a fixed
    order (sorted by y then x — top-to-bottom, left-to-right in plan
    view — rather than whatever incidental order they were computed in),
    so the same floor plan always produces the same labels across
    repeated calls. Returns new dicts; never mutates the input."""
    ordered = sorted(elements, key=lambda e: (round(e["y"], 2), round(e["x"], 2)))
    return [{**el, "label": f"{prefix}{i + 1}"} for i, el in enumerate(ordered)]


def compute_structural_overlay(rooms: list[dict[str, Any]], plot_length_ft: float, plot_width_ft: float) -> dict[str, Any]:
    """Walls: every room's own boundary (already known, drawn as a
    thicker line to distinguish from the base floor plan) plus the
    plot's own perimeter. Columns: a schematic rule-of-thumb grid at
    every room corner (deduplicated where corners coincide) — the most
    commonly taught convention for a simple RCC-frame residential
    structure, not a calculated design (see STRUCTURAL_DISCLAIMER).
    Columns are labeled C1, C2, ...; walls are unlabeled linear
    connectors, consistent with every discipline in this module."""
    valid = _valid_rooms(rooms)

    walls = [{"x": 0, "y": 0, "length": plot_length_ft, "width": plot_width_ft, "kind": "perimeter"}]
    for room in valid:
        walls.append({"x": room["x"], "y": room["y"], "length": room["length"], "width": room["width"], "kind": "partition"})

    seen_columns = set()
    columns_raw = []
    for room in valid:
        corners = [
            (room["x"], room["y"]),
            (room["x"] + room["length"], room["y"]),
            (room["x"], room["y"] + room["width"]),
            (room["x"] + room["length"], room["y"] + room["width"]),
        ]
        for cx, cy in corners:
            key = (round(cx, 1), round(cy, 1))
            if key not in seen_columns:
                seen_columns.add(key)
                columns_raw.append({"x": cx, "y": cy})

    return {
        "discipline": "structural",
        "walls": walls,
        "columns": _label_elements(columns_raw, "C"),
        "disclaimer": STRUCTURAL_DISCLAIMER,
    }


def compute_plumbing_overlay(rooms: list[dict[str, Any]], plot_length_ft: float, plot_width_ft: float) -> dict[str, Any]:
    """Fixture markers in every room whose name suggests plumbing needs
    (bathroom/kitchen/utility — see _is_wet_room), each connected by a
    schematic pipe-run line to a single main riser point placed at the
    plot's own edge closest to the average of those rooms — an honest,
    simple convention, not a real plumbing engineer's routing (see
    PLUMBING_DISCLAIMER). A plan with no wet rooms honestly returns an
    empty fixture/pipe list rather than inventing placements. Fixtures
    are labeled FX1, FX2, ...; the main riser is labeled MR (there is
    only ever one); pipe runs are unlabeled linear connectors."""
    wet_rooms = [r for r in _valid_rooms(rooms) if _is_wet_room(r["name"])]

    if not wet_rooms:
        return {"discipline": "plumbing", "fixtures": [], "pipe_runs": [], "main_riser": None, "disclaimer": PLUMBING_DISCLAIMER}

    fixtures_raw = []
    for room in wet_rooms:
        center_x = room["x"] + room["length"] / 2
        center_y = room["y"] + room["width"] / 2
        fixtures_raw.append({"room_name": room["name"], "x": center_x, "y": center_y})

    fixtures = _label_elements(fixtures_raw, "FX")

    avg_x = sum(f["x"] for f in fixtures) / len(fixtures)
    avg_y = sum(f["y"] for f in fixtures) / len(fixtures)

    # Snap the riser to whichever plot edge is genuinely closest to the
    # average fixture position — a simple, defensible convention for a
    # schematic diagram, not a claim about where the real municipal
    # connection is (this app has no way to know that).
    distances_to_edges = {
        "south": avg_y,
        "north": plot_width_ft - avg_y,
        "west": avg_x,
        "east": plot_length_ft - avg_x,
    }
    closest_edge = min(distances_to_edges, key=distances_to_edges.get)
    riser_position = {
        "south": {"x": avg_x, "y": 0},
        "north": {"x": avg_x, "y": plot_width_ft},
        "west": {"x": 0, "y": avg_y},
        "east": {"x": plot_length_ft, "y": avg_y},
    }[closest_edge]
    main_riser = {"x": riser_position["x"], "y": riser_position["y"], "edge": closest_edge, "label": "MR"}

    pipe_runs = [{"from": {"x": f["x"], "y": f["y"]}, "to": {"x": main_riser["x"], "y": main_riser["y"]}} for f in fixtures]

    return {
        "discipline": "plumbing",
        "fixtures": fixtures,
        "pipe_runs": pipe_runs,
        "main_riser": main_riser,
        "disclaimer": PLUMBING_DISCLAIMER,
    }


def compute_electrical_overlay(rooms: list[dict[str, Any]], plot_length_ft: float, plot_width_ft: float) -> dict[str, Any]:
    """Every room gets one light point (room center), one ceiling fan
    point (offset slightly from the light so the two don't sit exactly
    on top of each other — real rooms commonly have both, not one or
    the other), one switch point (schematically placed just inside the
    corner nearest the plot's own entry-facing edge, a common convention
    absent any real door-position data this app doesn't track), and
    socket points along two walls — all a visualization convention, not
    a calculated circuit design (see ELECTRICAL_DISCLAIMER). Lights are
    labeled L1, L2, ...; fans FN1, FN2, ...; switches SW1, SW2, ...;
    sockets SO1, SO2, ... — each element type labeled independently."""
    valid = _valid_rooms(rooms)

    lights_raw = []
    fans_raw = []
    switches_raw = []
    sockets_raw = []

    for room in valid:
        center_x = room["x"] + room["length"] / 2
        center_y = room["y"] + room["width"] / 2
        # Fan sits at the true room center (the conventional ceiling-fan
        # position); the light is offset slightly so its marker doesn't
        # sit exactly on top of the fan's on the drawing.
        fans_raw.append({"room_name": room["name"], "x": center_x, "y": center_y})
        light_offset = min(1.5, room["length"] / 6, room["width"] / 6)
        lights_raw.append({"room_name": room["name"], "x": center_x + light_offset, "y": center_y})

        # Switch: just inside the room's own corner nearest the plot
        # origin — a simple, consistent convention (no real door-position
        # data exists to place this more specifically).
        switch_x = room["x"] + min(1.0, room["length"] / 4)
        switch_y = room["y"] + min(1.0, room["width"] / 4)
        switches_raw.append({"room_name": room["name"], "x": switch_x, "y": switch_y})

        # Sockets: two per room, along the room's two longer walls at
        # roughly the 1/3 and 2/3 points — a common, simple convention.
        sockets_raw.append({"room_name": room["name"], "x": room["x"] + room["length"] * 0.33, "y": room["y"] + 0.3})
        sockets_raw.append({"room_name": room["name"], "x": room["x"] + room["length"] * 0.67, "y": room["y"] + room["width"] - 0.3})

    return {
        "discipline": "electrical",
        "lights": _label_elements(lights_raw, "L"),
        "fans": _label_elements(fans_raw, "FN"),
        "switches": _label_elements(switches_raw, "SW"),
        "sockets": _label_elements(sockets_raw, "SO"),
        "disclaimer": ELECTRICAL_DISCLAIMER,
    }
