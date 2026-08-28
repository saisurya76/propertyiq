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
floor plan always gets the same labels across repeated calls.

SPEC FIELDS — a second, even more important honesty boundary: every
labeled element also carries a `spec` field with reference dimensions
(e.g. a column's typical depth/width and rebar) sourced from widely-
published Indian residential construction thumb rules (IS 456:2000
minimums, and the G+1/G+2/G+3 conventional sizing tables cited across
multiple civil engineering references — 230x300mm columns for G+1,
4-6 bars of 12-16mm Fe500, etc). These are the SAME published reference
numbers a contractor might use for a rough estimate before an engineer
gets involved — genuinely real, sourced figures, not invented — but
they are uniform PER ELEMENT TYPE (every column gets the same reference
spec), never varied per specific element to fake the appearance of a
real calculation that was never done. Every `spec` string explicitly
says "reference only" and "requires a structural/plumbing/electrical
engineer's verification for this specific building" — never state a
spec without that qualifier, and never let a spec's presence be read
as "this was calculated for your house."

LEGEND — colors are defined ONCE here (LEGEND entries) and consumed by
the frontend for both the swatch key and the actual drawing colors, so
the legend can never drift out of sync with what's actually drawn.
"""

from typing import Any

STRUCTURAL_DISCLAIMER = (
    "Schematic column/beam/wall placement for visualization only, using a common rule-of-thumb "
    "grid (columns at wall intersections/corners, beams along walls). This is NOT a structural "
    "engineer's calculated design — real column/beam sizing and placement depends on actual loads, "
    "soil bearing capacity, and seismic zone. Have a licensed structural engineer review before construction."
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

_SPEC_SUFFIX_STRUCTURAL = (
    " Reference figure only from published Indian residential construction thumb rules — NOT "
    "calculated for this specific building. A licensed structural engineer must verify against "
    "your actual loads, soil report, and local code before construction."
)
_SPEC_SUFFIX_PLUMBING = (
    " Reference figure only from published Indian residential construction thumb rules — NOT "
    "calculated for this specific building. A licensed plumber must verify against your actual "
    "fixture count, water pressure, and local code before construction."
)
_SPEC_SUFFIX_ELECTRICAL = (
    " Reference figure only from published Indian residential construction thumb rules — NOT "
    "calculated for this specific building. A licensed electrician must verify against your "
    "actual appliance loads and local code before construction."
)

# Reference column sizing by total floor count — sourced from widely-
# published G+1/G+2/G+3 conventional sizing (IS 456:2000 minimums plus
# common site practice: 230x300mm for G+1, 230x380mm for G+2, etc).
_COLUMN_SPEC_BY_FLOORS = {
    1: "Typical reference for a single-storey (G) building: 230mm x 230mm (9\"x9\"), M20 concrete, 4 bars of 12mm Fe500 with 8mm ties @ 150mm c/c.",
    2: "Typical reference for a G+1 building: 230mm x 300mm (9\"x12\"), M20 concrete, 4-6 bars of 12-16mm Fe500 with 8mm ties @ 150mm c/c.",
    3: "Typical reference for a G+2 building: 230mm x 380mm, M20 concrete, 6 bars of 16mm Fe500 with 8mm ties @ 150mm c/c.",
}
_COLUMN_SPEC_DEFAULT = "Typical reference for a G+3 or taller building: 300mm x 450mm, M25 concrete, 6-8 bars of 16-20mm Fe500 with 8mm ties @ 150mm c/c."


def _column_spec(total_floors: int) -> str:
    base = _COLUMN_SPEC_BY_FLOORS.get(total_floors, _COLUMN_SPEC_DEFAULT)
    return base + _SPEC_SUFFIX_STRUCTURAL


def _beam_spec(span_ft: float) -> str:
    """Depth = span/12 (a commonly published thumb rule, using the
    shorter end of the span/12-to-span/15 range so this reads as a
    conservative reference, not an optimistic one), clamped to the
    commonly cited 300mm minimum practical depth for residential work;
    width = depth/1.7 (within the standard 1.5-2x depth/width ratio
    range), clamped to the same 230mm structural minimum as columns.
    Rounded to the nearest 25mm, the standard formwork increment."""
    span_mm = span_ft * 304.8
    depth_mm = max(300, round((span_mm / 12) / 25) * 25)
    width_mm = max(230, round((depth_mm / 1.7) / 25) * 25)
    base = (
        f"Typical reference for a {span_ft:.0f}ft span: {width_mm}mm x {depth_mm}mm (width x depth), "
        "M20 concrete, 2 bars of 16mm Fe500 top and bottom with 8mm stirrups @ 150mm c/c near supports."
    )
    return base + _SPEC_SUFFIX_STRUCTURAL


_PLUMBING_FIXTURE_SPEC = (
    "Typical reference fixture connection: 15mm CPVC supply branch, 75mm PVC/SWR waste branch."
    + _SPEC_SUFFIX_PLUMBING
)
_PLUMBING_RISER_SPEC = (
    "Typical reference main line: 25mm CPVC supply main, 110mm PVC/SWR soil stack."
    + _SPEC_SUFFIX_PLUMBING
)

_ELECTRICAL_LIGHT_FAN_SPEC = (
    "Typical reference circuit: 1.5 sq mm FRLS copper wire on a shared 6A lighting/fan circuit."
    + _SPEC_SUFFIX_ELECTRICAL
)
_ELECTRICAL_SWITCH_SPEC = (
    "Typical reference: 1.5 sq mm FRLS copper wire feeding the light/fan circuit it controls."
    + _SPEC_SUFFIX_ELECTRICAL
)
_ELECTRICAL_SOCKET_SPEC = (
    "Typical reference circuit: 2.5 sq mm FRLS copper wire on a 16A general-purpose socket circuit "
    "(kitchen and other heavy-appliance sockets commonly get a dedicated, separately-fused circuit — "
    "confirm actual appliance loads with an electrician)."
    + _SPEC_SUFFIX_ELECTRICAL
)

# Colors defined ONCE here and consumed by the frontend for both the
# legend swatch and the actual drawing fill/stroke — the two can never
# drift apart since there is only one source for each color.
LEGEND = {
    "structural": [
        {"key": "perimeter_wall", "label": "Perimeter wall", "shape": "line", "color": "#dc2626"},
        {"key": "partition_wall", "label": "Partition wall", "shape": "line", "color": "#f59e0b"},
        {"key": "column", "label": "Column", "shape": "square", "color": "#dc2626"},
        {"key": "beam", "label": "Beam", "shape": "line", "color": "#7c3aed"},
    ],
    "plumbing": [
        {"key": "fixture", "label": "Fixture (bathroom/kitchen/utility)", "shape": "circle", "color": "#2563eb"},
        {"key": "pipe_run", "label": "Pipe run", "shape": "dashed_line", "color": "#2563eb"},
        {"key": "main_riser", "label": "Main riser", "shape": "square", "color": "#1e3a8a"},
    ],
    "electrical": [
        {"key": "light", "label": "Light point", "shape": "circle_outline", "color": "#d97706"},
        {"key": "fan", "label": "Ceiling fan point", "shape": "crosshair", "color": "#0891b2"},
        {"key": "switch", "label": "Switch point", "shape": "square", "color": "#d97706"},
        {"key": "socket", "label": "Socket point", "shape": "square", "color": "#059669"},
    ],
}

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


def compute_structural_overlay(
    rooms: list[dict[str, Any]],
    plot_length_ft: float,
    plot_width_ft: float,
    total_floors: int = 1,
) -> dict[str, Any]:
    """Walls: every room's own boundary (already known, drawn as a
    thicker line to distinguish from the base floor plan) plus the
    plot's own perimeter. Columns: a schematic rule-of-thumb grid at
    every room corner (deduplicated where corners coincide) — the most
    commonly taught convention for a simple RCC-frame residential
    structure, not a calculated design (see STRUCTURAL_DISCLAIMER).
    Beams: one schematic beam along each wall segment (perimeter and
    partition alike), sized by that segment's own length as a stand-in
    for its span — a real approximation, not this app pretending to
    know the actual structural grid. Columns are labeled C1, C2, ...;
    beams B1, B2, ...; walls are unlabeled linear connectors.

    `total_floors` (the building's total floor count, not just this
    one) picks which published G+1/G+2/G+3 reference column size to
    quote — see _column_spec's own sourcing comment."""
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

    column_spec = _column_spec(total_floors)
    columns = [{**c, "spec": column_spec} for c in _label_elements(columns_raw, "C")]

    # One schematic beam per room, running along its longer dimension
    # (the more structurally typical primary-span direction) — a
    # midline through the room at roof/floor-slab level, not drawn on
    # top of the wall line itself so the two remain visually distinct.
    beams_raw = []
    for room in valid:
        span_ft = max(room["length"], room["width"])
        if room["length"] >= room["width"]:
            beams_raw.append({"x": room["x"], "y": room["y"] + room["width"] / 2, "x2": room["x"] + room["length"], "y2": room["y"] + room["width"] / 2, "span_ft": span_ft})
        else:
            beams_raw.append({"x": room["x"] + room["length"] / 2, "y": room["y"], "x2": room["x"] + room["length"] / 2, "y2": room["y"] + room["width"], "span_ft": span_ft})
    beams_labeled = _label_elements(beams_raw, "B")
    beams = [{**b, "spec": _beam_spec(b["span_ft"])} for b in beams_labeled]

    return {
        "discipline": "structural",
        "walls": walls,
        "columns": columns,
        "beams": beams,
        "legend": LEGEND["structural"],
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
        return {"discipline": "plumbing", "fixtures": [], "pipe_runs": [], "main_riser": None, "legend": LEGEND["plumbing"], "disclaimer": PLUMBING_DISCLAIMER}

    fixtures_raw = []
    for room in wet_rooms:
        center_x = room["x"] + room["length"] / 2
        center_y = room["y"] + room["width"] / 2
        fixtures_raw.append({"room_name": room["name"], "x": center_x, "y": center_y})

    fixtures = [{**f, "spec": _PLUMBING_FIXTURE_SPEC} for f in _label_elements(fixtures_raw, "FX")]

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
    main_riser = {"x": riser_position["x"], "y": riser_position["y"], "edge": closest_edge, "label": "MR", "spec": _PLUMBING_RISER_SPEC}

    pipe_runs = [{"from": {"x": f["x"], "y": f["y"]}, "to": {"x": main_riser["x"], "y": main_riser["y"]}} for f in fixtures]

    return {
        "discipline": "plumbing",
        "fixtures": fixtures,
        "pipe_runs": pipe_runs,
        "main_riser": main_riser,
        "legend": LEGEND["plumbing"],
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

    lights = [{**l, "spec": _ELECTRICAL_LIGHT_FAN_SPEC} for l in _label_elements(lights_raw, "L")]
    fans = [{**f, "spec": _ELECTRICAL_LIGHT_FAN_SPEC} for f in _label_elements(fans_raw, "FN")]
    switches = [{**s, "spec": _ELECTRICAL_SWITCH_SPEC} for s in _label_elements(switches_raw, "SW")]
    sockets = [{**s, "spec": _ELECTRICAL_SOCKET_SPEC} for s in _label_elements(sockets_raw, "SO")]

    return {
        "discipline": "electrical",
        "lights": lights,
        "fans": fans,
        "switches": switches,
        "sockets": sockets,
        "legend": LEGEND["electrical"],
        "disclaimer": ELECTRICAL_DISCLAIMER,
    }
