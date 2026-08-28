from typing import Any, Optional

# Thai traditional building principles — the country-specific counterpart
# to vastu_engine.py, used when a property's country is Thailand instead
# of India. Deliberately NOT a zone-grid system like Vastu's — that
# compass-zone structure ("kitchen belongs in the SE corner") is specific
# to Vastu Shastra and isn't how Thai vernacular building tradition is
# actually documented. Thai principles found in real sources instead
# center on: (1) overall house orientation relative to the sun's path,
# and (2) which rooms should or shouldn't be near each other — the same
# "adjacency" shape adjacency_engine.py already uses, just with different,
# Thai-specific rules and rationale.
#
# Scope, stated honestly: much of real Thai building practice involves
# individualized astrological calculation (a monk or astrologer factoring
# in the household's birth dates, the specific year's "auspicious
# direction," etc.) that no general software tool can reasonably
# replicate — the same honest limitation already accepted for Vastu here,
# which likewise doesn't attempt individualized astrology. What follows
# covers the structural/spatial principles that are well-documented across
# multiple sources and translate cleanly to a layout checker: orientation,
# and kitchen/shrine placement relative to other rooms.
#
# Sources: Thailand Foundation's "Ruean Thai" overview, the Wikipedia
# "Traditional Thai house" article, and Grokipedia's traditional-house
# entry (house orientation, sun-path alignment, the Huean Fai separate
# kitchen building); shrine/altar-adjacent-to-kitchen-or-bathroom being
# discouraged is a broadly-observed convention across Buddhist
# households in the region, cited here as such rather than claimed to be
# exclusively indigenous Thai practice.

ROOM_TYPE_KEYWORDS = {
    "kitchen": ["kitchen"],
    "bedroom": ["bedroom"],
    "bathroom": ["bathroom", "toilet", "washroom", "wc", "restroom"],
    "shrine": ["shrine", "prayer", "buddha room", "spirit room", "altar"],
}

# (type_a, type_b, "avoid" | "prefer", rationale)
THAI_ADJACENCY_RULES = [
    ("kitchen", "bedroom", "avoid",
     "Traditional Thai houses (Ruean Thai) commonly kept the kitchen (Huean Fai) as a separate "
     "building from the main sleeping quarters, to keep cooking smoke and fire away from where "
     "the family slept — a bedroom directly adjoining the kitchen runs against this."),
    ("shrine", "bathroom", "avoid",
     "A household shrine or Buddha corner placed next to a bathroom is widely considered "
     "disrespectful across Buddhist households in the region — the space is regarded as impure."),
    ("shrine", "kitchen", "avoid",
     "A household shrine or Buddha corner is conventionally kept apart from the kitchen, which is "
     "considered too busy/impure an environment for a space meant for quiet reverence."),
]


def _room_type(room: dict[str, Any]) -> Optional[str]:
    name_lower = (room.get("name") or "").lower()
    for room_type, keywords in ROOM_TYPE_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return room_type
    return None


def _rooms_are_adjacent(room_a: dict[str, Any], room_b: dict[str, Any], gap_threshold_ft: float = 1.0) -> bool:
    """Same geometric test as adjacency_engine.py's rooms_are_adjacent —
    shared or near-shared wall with genuine overlap along the other axis,
    not just a touching corner."""
    ax1, ay1 = room_a["x"], room_a["y"]
    ax2, ay2 = ax1 + room_a["length"], ay1 + room_a["width"]
    bx1, by1 = room_b["x"], room_b["y"]
    bx2, by2 = bx1 + room_b["length"], by1 + room_b["width"]

    x_touch = abs(ax2 - bx1) <= gap_threshold_ft or abs(bx2 - ax1) <= gap_threshold_ft
    y_overlap = min(ay2, by2) - max(ay1, by1) > 0.5
    if x_touch and y_overlap:
        return True

    y_touch = abs(ay2 - by1) <= gap_threshold_ft or abs(by2 - ay1) <= gap_threshold_ft
    x_overlap = min(ax2, bx2) - max(ax1, bx1) > 0.5
    if y_touch and x_overlap:
        return True

    return False


THAI_FAVORABLE_ENTRANCES = {"east", "north-east", "south-east"}
THAI_UNFAVORABLE_ENTRANCES = {"west"}


def check_thai_orientation(
    *,
    entrance_direction: str,
    road_facing_side: Optional[str] = None,
) -> dict[str, Any]:
    """Overall house orientation check. East-facing is the consistently
    documented preference across sources (sunrise/renewal association);
    a west-facing long side/entrance is specifically called out as
    unfavorable. This mirrors check_vastu_basics's role — a lightweight,
    entrance-direction-only pass, not the full room-level check."""

    notes = []
    compliant = True

    entrance = (entrance_direction or "").strip().lower()

    if entrance in THAI_UNFAVORABLE_ENTRANCES:
        compliant = False
        notes.append({
            "severity": "warning",
            "text": f"Entrance/frontage facing '{entrance_direction}' is specifically discouraged in Thai "
                    "traditional building practice — a west-facing long side is associated with misfortune, "
                    "and traditionally avoided in favor of an eastward orientation.",
        })
    elif entrance in THAI_FAVORABLE_ENTRANCES:
        notes.append({
            "severity": "good",
            "text": f"Entrance/frontage facing '{entrance_direction}' aligns with the traditional Thai "
                    "preference for an eastward-facing house, associated with the sunrise and renewal.",
        })
    else:
        notes.append({
            "severity": "neutral",
            "text": f"Entrance/frontage facing '{entrance_direction}' has no strong traditional preference "
                    "either way in Thai building practice.",
        })

    return {"compliant": compliant, "notes": [n["text"] for n in notes], "notes_detailed": notes, "scope": "thai_orientation_basics"}


def check_thai_traditional_full(
    *,
    rooms: list[dict[str, Any]],
    entrance_direction: str,
    road_facing_side: Optional[str] = None,
) -> dict[str, Any]:
    """Full check: orientation (via check_thai_orientation) plus room-
    adjacency rules using each room's actual position. Only rooms whose
    name matches a known keyword get a finding — unmatched room types are
    silently skipped, same convention as vastu_engine.py and
    adjacency_engine.py."""

    orientation = check_thai_orientation(entrance_direction=entrance_direction, road_facing_side=road_facing_side)
    findings = [
        {"category": "orientation", "severity": n["severity"], "note": n["text"]}
        for n in orientation["notes_detailed"]
    ]
    compliant = orientation["compliant"]

    named_rooms = [r for r in rooms if r.get("name", "").strip() and _room_type(r)]

    for i, room_a in enumerate(named_rooms):
        type_a = _room_type(room_a)
        for room_b in named_rooms[i + 1:]:
            type_b = _room_type(room_b)
            if type_a == type_b:
                continue
            adjacent = _rooms_are_adjacent(room_a, room_b)
            if not adjacent:
                continue

            for rule_type_a, rule_type_b, kind, rationale in THAI_ADJACENCY_RULES:
                matches = {type_a, type_b} == {rule_type_a, rule_type_b}
                if not matches or kind != "avoid":
                    continue
                compliant = False
                findings.append({
                    "category": "room_adjacency",
                    "severity": "warning",
                    "rooms": [room_a.get("name"), room_b.get("name")],
                    "note": rationale,
                })

    return {"compliant": compliant, "findings": findings, "scope": "thai_traditional_full_check"}
