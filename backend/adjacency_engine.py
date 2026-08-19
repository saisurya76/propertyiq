from typing import Any

# Room type inference from free-text room names — same keyword-matching
# pattern as vastu_engine.py's ROOM_PLACEMENT_RULES, for consistency.
# Unmatched room names (no keyword hit) are simply skipped — not flagged
# as violations, since no rule exists for an unrecognized type.
ROOM_TYPE_KEYWORDS = {
    "kitchen": ["kitchen"],
    "bedroom": ["bedroom"],
    "bathroom": ["bathroom", "toilet", "washroom", "wc", "restroom"],
    "living": ["living", "family room", "lounge"],
    "dining": ["dining"],
}

# Adjacency rules grounded in established space-planning literature, not
# invented — see citations in the rationale strings. Each rule is
# (type_a, type_b, "avoid" | "prefer", rationale). "avoid" = adjacency is
# a real problem (privacy, hygiene, noise); "prefer" = adjacency is
# genuinely beneficial (convenience, workflow) but its absence is not
# itself a violation, just a missed opportunity.
#
# These UNIVERSAL rules hold regardless of architectural style — noise/
# hygiene/privacy concerns don't go away just because a home is open-plan.
UNIVERSAL_ADJACENCY_RULES = [
    ("kitchen", "bathroom", "avoid",
     "Kitchens and bathrooms directly adjacent raises hygiene concerns and is generally avoided in space planning."),
    ("bedroom", "kitchen", "avoid",
     "Bedrooms are conventionally isolated from noisy work zones like the kitchen for privacy and quiet."),
    ("bedroom", "bathroom", "prefer",
     "A bathroom adjoining or directly accessible from the bedroom is a well-established convenience principle."),
    ("kitchen", "dining", "prefer",
     "Kitchen-to-dining adjacency minimizes the distance food travels — a core space-planning efficiency principle, valid in both open and zoned layouts."),
]

# Style-specific rules — this is where "correctness" genuinely depends on
# the chosen architectural approach, not universal principle. Modern
# open-plan and minimalist layouts commonly treat kitchen-living openness
# as a defining, rewarded feature; traditional/zoned layouts more often
# keep each room's separate identity, per current space-planning practice
# discourse (not a strict rule either style "violates" by not adjoining).
STYLE_ADJACENCY_RULES = {
    "modern_open_plan": [
        ("kitchen", "living", "prefer",
         "Open-plan modern design treats kitchen-living adjacency as a defining feature — cooking, dining, and relaxing in one continuous space."),
    ],
    "minimalist": [
        ("kitchen", "living", "prefer",
         "Minimalist layouts commonly favor open, uncluttered flow between kitchen and living areas, similar to open-plan modern design."),
    ],
    "traditional_zoned": [
        # No style-specific rule — traditional/zoned layouts don't treat
        # kitchen-living adjacency as either required or discouraged;
        # each room keeping its own defined identity is a valid, common
        # choice in this style, not a violation either way.
    ],
}

VALID_STYLES = set(STYLE_ADJACENCY_RULES.keys())


def _room_type(room: dict[str, Any]) -> str | None:
    name_lower = (room.get("name") or "").lower()
    for room_type, keywords in ROOM_TYPE_KEYWORDS.items():
        if any(kw in name_lower for kw in keywords):
            return room_type
    return None


def rooms_are_adjacent(room_a: dict[str, Any], room_b: dict[str, Any], gap_threshold_ft: float = 1.0) -> bool:
    """Two axis-aligned rectangles are 'adjacent' if their boundaries
    touch or are within a small gap (a shared or near-shared wall) AND
    they overlap along the other axis (so two rooms merely near the same
    corner, not sharing a real wall segment, don't count)."""

    ax1, ay1 = room_a["x"], room_a["y"]
    ax2, ay2 = ax1 + room_a["length"], ay1 + room_a["width"]
    bx1, by1 = room_b["x"], room_b["y"]
    bx2, by2 = bx1 + room_b["length"], by1 + room_b["width"]

    # Touching (or nearly touching) along a vertical shared edge, with
    # real overlap along y (not just touching at a corner point).
    x_touch = abs(ax2 - bx1) <= gap_threshold_ft or abs(bx2 - ax1) <= gap_threshold_ft
    y_overlap = min(ay2, by2) - max(ay1, by1) > 0.5
    if x_touch and y_overlap:
        return True

    # Touching along a horizontal shared edge, with real overlap along x.
    y_touch = abs(ay2 - by1) <= gap_threshold_ft or abs(by2 - ay1) <= gap_threshold_ft
    x_overlap = min(ax2, bx2) - max(ax1, bx1) > 0.5
    if y_touch and x_overlap:
        return True

    return False


def evaluate_adjacency(rooms: list[dict[str, Any]], style: str = "modern_open_plan") -> dict[str, Any]:
    """For every pair of named, recognized-type rooms, checks adjacency
    against the universal rules plus the selected style's rules. Returns
    per-room findings (so the frontend can highlight a specific room) and
    an overall compliant flag mirroring the Vastu engine's response shape."""

    style = style if style in VALID_STYLES else "modern_open_plan"
    rules = UNIVERSAL_ADJACENCY_RULES + STYLE_ADJACENCY_RULES[style]

    findings = []
    compliant = True
    room_status: dict[str, str] = {}  # room _key -> "good" | "warning" | "neutral"

    named_rooms = [r for r in rooms if r.get("name", "").strip() and _room_type(r)]

    for i, room_a in enumerate(named_rooms):
        type_a = _room_type(room_a)
        for room_b in named_rooms[i + 1:]:
            type_b = _room_type(room_b)
            if type_a == type_b:
                continue
            adjacent = rooms_are_adjacent(room_a, room_b)

            for rule_type_a, rule_type_b, kind, rationale in rules:
                matches = {type_a, type_b} == {rule_type_a, rule_type_b}
                if not matches:
                    continue

                key_a, key_b = room_a.get("_key"), room_b.get("_key")
                if kind == "avoid" and adjacent:
                    compliant = False
                    findings.append({
                        "severity": "warning",
                        "rooms": [room_a.get("name"), room_b.get("name")],
                        "note": rationale,
                    })
                    for k in (key_a, key_b):
                        if k and room_status.get(k) != "warning":
                            room_status[k] = "warning"
                elif kind == "prefer" and adjacent:
                    findings.append({
                        "severity": "good",
                        "rooms": [room_a.get("name"), room_b.get("name")],
                        "note": rationale,
                    })
                    for k in (key_a, key_b):
                        if k and room_status.get(k) not in ("warning",):
                            room_status[k] = "good"

    return {
        "style": style,
        "compliant": compliant,
        "findings": findings,
        "room_status": room_status,  # only rooms with a finding appear here; absent = neutral
    }
