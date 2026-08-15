from typing import Any, Optional

from backend.construction_studio import check_vastu_basics

# Classical Vastu room-placement guidance, kept to the widely-cited
# beginner-level rules (not obscure regional variants). Matched by keyword
# against the room's name (case-insensitive) since rooms only carry a free-
# text name today — an explicit room_type field can replace this later
# without changing the rule structure.
ROOM_PLACEMENT_RULES = [
    # (keywords, preferred_zones, avoid_zones, rationale)
    (["kitchen"], {"SE"}, {"NE", "CENTER", "NW"},
     "Kitchen (fire element) is traditionally placed in the South-East (Agni corner)."),
    (["master bedroom", "master_bedroom"], {"SW"}, {"NE", "CENTER"},
     "Master bedroom is traditionally placed in the South-West for stability."),
    (["pooja", "puja", "prayer"], {"NE"}, {"SW"},
     "Pooja/prayer room is traditionally placed in the North-East."),
    (["toilet", "bathroom", "washroom", "wc"], {"NW", "W"}, {"NE", "CENTER", "SW"},
     "Toilets are traditionally kept away from North-East and the center, and avoid South-West."),
    (["staircase", "stairs"], {"S", "SW", "W"}, {"NE", "CENTER"},
     "Staircases are traditionally placed away from North-East and the center."),
    (["water tank", "borewell", "well", "water_tank"], {"NE"}, {"SW"},
     "Underground water sources are traditionally placed in the North-East."),
]


def _zone_for_room(room: dict[str, Any], plot_length_ft: float, plot_width_ft: float) -> str:
    """3x3 compass-grid zone for a room's centroid, using the same axis
    convention as construction_dxf.py: x = west(-)->east(+), y = south(-)->north(+)."""

    cx = room["x"] + room["length"] / 2
    cy = room["y"] + room["width"] / 2

    x_third = plot_length_ft / 3
    y_third = plot_width_ft / 3

    if cx < x_third:
        x_zone = "W"
    elif cx > 2 * x_third:
        x_zone = "E"
    else:
        x_zone = "MID"

    if cy < y_third:
        y_zone = "S"
    elif cy > 2 * y_third:
        y_zone = "N"
    else:
        y_zone = "MID"

    if x_zone == "MID" and y_zone == "MID":
        return "CENTER"
    if x_zone == "MID":
        return y_zone  # N or S
    if y_zone == "MID":
        return x_zone  # E or W
    return f"{y_zone}{x_zone}"  # NE, NW, SE, SW


def check_vastu_full(
    *,
    plot_length_ft: float,
    plot_width_ft: float,
    rooms: list[dict[str, Any]],
    entrance_direction: str,
    road_facing_side: str,
    slope_direction: Optional[str] = None,
) -> dict[str, Any]:
    """Full multi-rule Vastu check: entrance/road/slope (via the existing
    basic check) PLUS room-placement rules using each room's actual
    position, and a Brahmasthan (center) check.

    Only rooms whose name matches a known keyword get a placement finding —
    unmatched room types are silently skipped (not flagged as violations),
    since no rule exists for them yet."""

    basics = check_vastu_basics(
        entrance_direction=entrance_direction,
        road_facing_side=road_facing_side,
        slope_direction=slope_direction,
    )

    findings = [{"category": "entrance_and_slope", "note": n} for n in basics["notes"]]
    compliant = basics["compliant"]

    for room in rooms:
        name_lower = room.get("name", "").lower()
        zone = _zone_for_room(room, plot_length_ft, plot_width_ft)

        if zone == "CENTER":
            compliant = False
            findings.append({
                "category": "brahmasthan",
                "room": room.get("name"),
                "zone": zone,
                "note": f"'{room.get('name')}' sits over the plot's center (Brahmasthan), which classical "
                        f"Vastu recommends keeping open/unbuilt.",
            })

        for keywords, preferred, avoid, rationale in ROOM_PLACEMENT_RULES:
            if not any(k in name_lower for k in keywords):
                continue

            if zone in avoid:
                compliant = False
                findings.append({
                    "category": "room_placement",
                    "room": room.get("name"),
                    "zone": zone,
                    "preferred_zones": sorted(preferred),
                    "note": f"'{room.get('name')}' is in {zone}, which classical Vastu advises against. {rationale}",
                })
            elif zone in preferred:
                findings.append({
                    "category": "room_placement",
                    "room": room.get("name"),
                    "zone": zone,
                    "preferred_zones": sorted(preferred),
                    "note": f"'{room.get('name')}' in {zone} aligns with classical guidance. {rationale}",
                })
            else:
                findings.append({
                    "category": "room_placement",
                    "room": room.get("name"),
                    "zone": zone,
                    "preferred_zones": sorted(preferred),
                    "note": f"'{room.get('name')}' is in {zone} — neither a preferred nor a specifically "
                            f"discouraged zone for this room type. {rationale}",
                })
            break  # first matching rule wins per room

    return {
        "compliant": compliant,
        "findings": findings,
        "scope": "full_multi_rule_check",
    }
