"""Human-readable rule listings for the Vastu/Thai compliance info icon.

Deliberately built by reading directly from the same constants
vastu_engine.py/thai_traditional_engine.py/construction_studio.py use for
the actual live validation (VASTU_FAVORABLE_ENTRANCES, ROOM_PLACEMENT_RULES,
THAI_ADJACENCY_RULES, etc) rather than a separately-hand-written
description of what they check — a hand-written parallel description would
drift out of sync the moment someone changes a rule in the real engine
without remembering to update the popup text too. This module has no
rules of its own; it only formats the real ones for display.
"""

from typing import Any

from backend.construction_studio import VASTU_FAVORABLE_ENTRANCES, VASTU_UNFAVORABLE_SLOPES
from backend.vastu_engine import ROOM_PLACEMENT_RULES
from backend.thai_traditional_engine import (
    THAI_FAVORABLE_ENTRANCES,
    THAI_UNFAVORABLE_ENTRANCES,
    THAI_ADJACENCY_RULES,
)


def get_vastu_rules() -> dict[str, Any]:
    rules = [
        {
            "category": "Entrance Direction",
            "title": "Favorable entrance directions",
            "detail": f"An entrance facing {', '.join(sorted(d.title() for d in VASTU_FAVORABLE_ENTRANCES))} "
                      "is considered favorable in classical Vastu.",
        },
        {
            "category": "Plot Slope",
            "title": "Unfavorable slope directions",
            "detail": f"A plot sloping toward {', '.join(sorted(d.title() for d in VASTU_UNFAVORABLE_SLOPES))} "
                      "is traditionally considered unfavorable for water drainage; a slope toward North or East "
                      "is generally preferred.",
        },
        {
            "category": "Brahmasthan (Plot Center)",
            "title": "Keep the center open",
            "detail": "Classical Vastu recommends keeping the plot's center (Brahmasthan) open/unbuilt — a room "
                      "placed directly over it is flagged.",
        },
    ]
    for keywords, preferred, avoid, rationale in ROOM_PLACEMENT_RULES:
        rules.append({
            "category": "Room Placement",
            "title": f"Rooms matching: {', '.join(keywords)}",
            "detail": f"{rationale} Preferred zone(s): {', '.join(sorted(preferred))}. "
                      f"Advised against: {', '.join(sorted(avoid))}.",
        })
    return {
        "tradition": "vastu",
        "rules": rules,
        "scope_note": "This checks widely-cited, beginner-level classical Vastu guidance — not individualized "
                      "astrological calculation involving a household's birth details, which no general software "
                      "tool can reasonably replicate.",
    }


def get_thai_rules() -> dict[str, Any]:
    rules = [
        {
            "category": "House Orientation",
            "title": "Favorable entrance/frontage directions",
            "detail": f"An entrance or frontage facing {', '.join(sorted(d.title() for d in THAI_FAVORABLE_ENTRANCES))} "
                      "aligns with the traditional Thai preference for an eastward-facing house, associated with "
                      "the sunrise and renewal.",
        },
        {
            "category": "House Orientation",
            "title": "Discouraged entrance/frontage direction",
            "detail": f"A {', '.join(sorted(d.title() for d in THAI_UNFAVORABLE_ENTRANCES))}-facing long side/entrance "
                      "is specifically discouraged, traditionally associated with misfortune.",
        },
    ]
    for type_a, type_b, relation, rationale in THAI_ADJACENCY_RULES:
        rules.append({
            "category": "Room Adjacency",
            "title": f"{type_a.title()} and {type_b.title()}",
            "detail": f"{'Avoid placing these' if relation == 'avoid' else 'Placing these'} directly adjacent. {rationale}",
        })
    return {
        "tradition": "thai",
        "rules": rules,
        "scope_note": "This checks well-documented structural/spatial principles from real sources (Thailand "
                      "Foundation's Ruean Thai overview, the Wikipedia Traditional Thai house article, and "
                      "similar) — not individualized astrological calculation involving a household's birth "
                      "dates or a given year's auspicious direction, which no general software tool can "
                      "reasonably replicate.",
    }
