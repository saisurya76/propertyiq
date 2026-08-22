// JS port of backend/thai_traditional_engine.py — kept deliberately in
// sync so live canvas feedback and the server-side /vastu-check report
// (which routes to the Thai engine for Thailand properties) never
// silently disagree. Same room-type keyword matching, same geometric
// adjacency test, same orientation + adjacency rules. Mirrors
// adjacencyEngine.js's own established pattern for this exact purpose.

export const THAI_ROOM_TYPE_KEYWORDS = {
  kitchen: ["kitchen"],
  bedroom: ["bedroom"],
  bathroom: ["bathroom", "toilet", "washroom", "wc", "restroom"],
  shrine: ["shrine", "prayer", "buddha room", "spirit room", "altar"],
};

// (typeA, typeB, kind, rationale) — Thai engine only has "avoid" rules
// currently (no "prefer" positive findings were well-documented enough
// to encode yet, unlike adjacency_engine.py's kitchen-dining/bedroom-
// bathroom "prefer" rules).
const THAI_ADJACENCY_RULES = [
  ["kitchen", "bedroom", "avoid",
   "Traditional Thai houses (Ruean Thai) commonly kept the kitchen (Huean Fai) as a separate " +
   "building from the main sleeping quarters, to keep cooking smoke and fire away from where " +
   "the family slept — a bedroom directly adjoining the kitchen runs against this."],
  ["shrine", "bathroom", "avoid",
   "A household shrine or Buddha corner placed next to a bathroom is widely considered " +
   "disrespectful across Buddhist households in the region — the space is regarded as impure."],
  ["shrine", "kitchen", "avoid",
   "A household shrine or Buddha corner is conventionally kept apart from the kitchen, which is " +
   "considered too busy/impure an environment for a space meant for quiet reverence."],
];

function thaiRoomType(room) {
  const nameLower = (room.name || "").toLowerCase();
  for (const [type, keywords] of Object.entries(THAI_ROOM_TYPE_KEYWORDS)) {
    if (keywords.some((kw) => nameLower.includes(kw))) return type;
  }
  return null;
}

// Same geometric test as adjacencyEngine.js's roomsAreAdjacent — shared
// or near-shared wall with genuine overlap along the other axis, not
// just a touching corner.
export function thaiRoomsAreAdjacent(roomA, roomB, gapThresholdFt = 1.0) {
  const ax1 = roomA.x, ay1 = roomA.y;
  const ax2 = ax1 + roomA.length, ay2 = ay1 + roomA.width;
  const bx1 = roomB.x, by1 = roomB.y;
  const bx2 = bx1 + roomB.length, by2 = by1 + roomB.width;

  const xTouch = Math.abs(ax2 - bx1) <= gapThresholdFt || Math.abs(bx2 - ax1) <= gapThresholdFt;
  const yOverlap = Math.min(ay2, by2) - Math.max(ay1, by1) > 0.5;
  if (xTouch && yOverlap) return true;

  const yTouch = Math.abs(ay2 - by1) <= gapThresholdFt || Math.abs(by2 - ay1) <= gapThresholdFt;
  const xOverlap = Math.min(ax2, bx2) - Math.max(ax1, bx1) > 0.5;
  if (yTouch && xOverlap) return true;

  return false;
}

export function checkThaiOrientation(entranceDirection) {
  const favorable = ["east", "north-east", "south-east"];
  const unfavorable = ["west"];
  const entrance = (entranceDirection || "").trim().toLowerCase();

  if (unfavorable.includes(entrance)) {
    return {
      severity: "warning",
      text: `Entrance/frontage facing '${entranceDirection}' is specifically discouraged in Thai ` +
            "traditional building practice — a west-facing long side is associated with misfortune, " +
            "and traditionally avoided in favor of an eastward orientation.",
    };
  }
  if (favorable.includes(entrance)) {
    return {
      severity: "good",
      text: `Entrance/frontage facing '${entranceDirection}' aligns with the traditional Thai ` +
            "preference for an eastward-facing house, associated with the sunrise and renewal.",
    };
  }
  return {
    severity: "neutral",
    text: `Entrance/frontage facing '${entranceDirection}' has no strong traditional preference ` +
          "either way in Thai building practice.",
  };
}

// Returns { compliant, findings, roomStatus } — same output shape as
// evaluateAdjacency() so the same rendering code path can be reused for
// either engine's result on the frontend.
export function evaluateThaiTraditional(rooms, entranceDirection) {
  const orientation = checkThaiOrientation(entranceDirection);
  const findings = [{ category: "orientation", severity: orientation.severity, note: orientation.text }];
  let compliant = orientation.severity !== "warning";
  const roomStatus = {};

  const namedRooms = rooms.filter((r) => (r.name || "").trim() && thaiRoomType(r));

  for (let i = 0; i < namedRooms.length; i++) {
    const roomA = namedRooms[i];
    const typeA = thaiRoomType(roomA);
    for (let j = i + 1; j < namedRooms.length; j++) {
      const roomB = namedRooms[j];
      const typeB = thaiRoomType(roomB);
      if (typeA === typeB) continue;
      if (!thaiRoomsAreAdjacent(roomA, roomB)) continue;

      for (const [ruleTypeA, ruleTypeB, kind, rationale] of THAI_ADJACENCY_RULES) {
        const matches =
          (typeA === ruleTypeA && typeB === ruleTypeB) || (typeA === ruleTypeB && typeB === ruleTypeA);
        if (!matches || kind !== "avoid") continue;

        compliant = false;
        findings.push({ category: "room_adjacency", severity: "warning", rooms: [roomA.name, roomB.name], note: rationale });
        const keyA = roomA._key, keyB = roomB._key;
        for (const k of [keyA, keyB]) {
          if (k) roomStatus[k] = "warning";
        }
      }
    }
  }

  return { compliant, findings, roomStatus, scope: "thai_traditional_full_check" };
}
