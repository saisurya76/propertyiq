// JS port of backend/adjacency_engine.py — kept deliberately in sync so
// the live drag feedback here and the server-side /adjacency-check report
// never silently disagree. Same room-type keyword matching, same
// geometric adjacency test, same universal + style-specific rules.

export const ROOM_TYPE_KEYWORDS = {
  kitchen: ["kitchen"],
  bedroom: ["bedroom"],
  bathroom: ["bathroom", "toilet", "washroom", "wc", "restroom"],
  living: ["living", "family room", "lounge"],
  dining: ["dining"],
};

// (typeA, typeB, kind, rationale) — "avoid" = real problem, "prefer" = a
// genuine benefit when present but not a violation when absent.
const UNIVERSAL_ADJACENCY_RULES = [
  ["kitchen", "bathroom", "avoid", "Kitchens and bathrooms directly adjacent raises hygiene concerns and is generally avoided in space planning."],
  ["bedroom", "kitchen", "avoid", "Bedrooms are conventionally isolated from noisy work zones like the kitchen for privacy and quiet."],
  ["bedroom", "bathroom", "prefer", "A bathroom adjoining or directly accessible from the bedroom is a well-established convenience principle."],
  ["kitchen", "dining", "prefer", "Kitchen-to-dining adjacency minimizes the distance food travels — a core space-planning efficiency principle, valid in both open and zoned layouts."],
];

const STYLE_ADJACENCY_RULES = {
  modern_open_plan: [
    ["kitchen", "living", "prefer", "Open-plan modern design treats kitchen-living adjacency as a defining feature — cooking, dining, and relaxing in one continuous space."],
  ],
  minimalist: [
    ["kitchen", "living", "prefer", "Minimalist layouts commonly favor open, uncluttered flow between kitchen and living areas, similar to open-plan modern design."],
  ],
  traditional_zoned: [],
};

export const VALID_STYLES = Object.keys(STYLE_ADJACENCY_RULES);

export const ARCHITECTURAL_STYLE_LABELS = {
  modern_open_plan: "Modern / Open-Plan",
  minimalist: "Minimalist",
  traditional_zoned: "Traditional / Zoned",
};

function roomType(room) {
  const nameLower = (room.name || "").toLowerCase();
  for (const [type, keywords] of Object.entries(ROOM_TYPE_KEYWORDS)) {
    if (keywords.some((kw) => nameLower.includes(kw))) return type;
  }
  return null;
}

export function roomsAreAdjacent(roomA, roomB, gapThresholdFt = 1.0) {
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

// Returns { compliant, findings, roomStatus } — roomStatus maps room _key
// to "good" | "warning"; a room absent from roomStatus is neutral.
export function evaluateAdjacency(rooms, style = "modern_open_plan") {
  const resolvedStyle = VALID_STYLES.includes(style) ? style : "modern_open_plan";
  const rules = [...UNIVERSAL_ADJACENCY_RULES, ...STYLE_ADJACENCY_RULES[resolvedStyle]];

  const findings = [];
  let compliant = true;
  const roomStatus = {};

  const namedRooms = rooms.filter((r) => (r.name || "").trim() && roomType(r));

  for (let i = 0; i < namedRooms.length; i++) {
    const roomA = namedRooms[i];
    const typeA = roomType(roomA);
    for (let j = i + 1; j < namedRooms.length; j++) {
      const roomB = namedRooms[j];
      const typeB = roomType(roomB);
      if (typeA === typeB) continue;
      const adjacent = roomsAreAdjacent(roomA, roomB);

      for (const [ruleTypeA, ruleTypeB, kind, rationale] of rules) {
        const matches =
          (typeA === ruleTypeA && typeB === ruleTypeB) || (typeA === ruleTypeB && typeB === ruleTypeA);
        if (!matches) continue;

        const keyA = roomA._key, keyB = roomB._key;
        if (kind === "avoid" && adjacent) {
          compliant = false;
          findings.push({ severity: "warning", rooms: [roomA.name, roomB.name], note: rationale });
          for (const k of [keyA, keyB]) {
            if (k && roomStatus[k] !== "warning") roomStatus[k] = "warning";
          }
        } else if (kind === "prefer" && adjacent) {
          findings.push({ severity: "good", rooms: [roomA.name, roomB.name], note: rationale });
          for (const k of [keyA, keyB]) {
            if (k && roomStatus[k] !== "warning") roomStatus[k] = "good";
          }
        }
      }
    }
  }

  return { style: resolvedStyle, compliant, findings, roomStatus };
}
