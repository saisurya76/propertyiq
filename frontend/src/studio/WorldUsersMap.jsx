import { useEffect, useRef, useState } from "react";
import worldMapSvg from "./assets/world-map.svg?raw";

// Real, distinct colors per tier — same palette family as the rest of
// the admin panel's own stat cards, so a "Pro" dot on this map reads
// as the same "Pro" everywhere else in the dashboard.
const TIER_COLORS = {
  studio_starter: "#60A5FA", // blue
  studio_pro: "#A78BFA", // purple
  studio_unlimited: "#34D399", // green
  none: "#CBD5E1", // slate — signed in, no active subscription
};

const TIER_LABELS = {
  studio_starter: "Starter",
  studio_pro: "Pro",
  studio_unlimited: "Unlimited",
  none: "No active subscription",
};

export default function WorldUsersMap({ usersByCountry }) {
  const containerRef = useRef(null);
  const [hovered, setHovered] = useState(null);

  // Real per-country aggregation: which tier has the most real users
  // in that country (the map can only fill one color per country
  // shape), plus the real total and per-tier breakdown for the
  // tooltip — so a mixed-tier country isn't misrepresented as
  // single-tier, just colored by its real majority.
  const byCountry = {};
  for (const row of usersByCountry || []) {
    const code = (row.country_code || "").toLowerCase();
    if (!byCountry[code]) byCountry[code] = { country_name: row.country_name, total: 0, tiers: {} };
    byCountry[code].total += row.user_count;
    byCountry[code].tiers[row.tier_id] = (byCountry[code].tiers[row.tier_id] || 0) + row.user_count;
  }
  for (const code of Object.keys(byCountry)) {
    const tiers = byCountry[code].tiers;
    byCountry[code].dominantTier = Object.keys(tiers).reduce((a, b) => (tiers[a] >= tiers[b] ? a : b));
  }

  useEffect(() => {
    const svgEl = containerRef.current?.querySelector("svg");
    if (!svgEl) return;
    // Most countries are a single <path id="xx">, but some (the US,
    // and others with disconnected territory) are a <g id="xx">
    // wrapping several unnamed <path> children instead -- confirmed
    // directly by inspecting the real SVG source, not assumed. Both
    // shapes need coloring, or a country structured the second way
    // silently keeps SVG's own default black fill.
    const targets = svgEl.querySelectorAll("path[id], g[id]");
    targets.forEach((el) => {
      const code = el.id.toLowerCase();
      const data = byCountry[code];
      const fillColor = data ? TIER_COLORS[data.dominantTier] || TIER_COLORS.none : "#F1F5F9";
      const paths = el.tagName.toLowerCase() === "g" ? el.querySelectorAll("path") : [el];
      paths.forEach((path) => {
        path.style.fill = fillColor;
        path.style.stroke = "#FFFFFF";
        path.style.strokeWidth = "0.5";
        path.style.cursor = data ? "pointer" : "default";
      });
      el.onmouseenter = () => data && setHovered({ code, ...data });
      el.onmouseleave = () => setHovered(null);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [usersByCountry]);

  const totalUsers = (usersByCountry || []).reduce((sum, r) => sum + r.user_count, 0);
  const countriesCovered = Object.keys(byCountry).length;

  return (
    <div className="admin-world-map-wrap">
      {totalUsers === 0 && (
        <p className="admin-empty-note" style={{ marginBottom: 10 }}>
          No location data yet — this fills in as users sign in going forward (see the note below on how this is captured).
        </p>
      )}
      <div className="admin-world-map-svg" ref={containerRef} dangerouslySetInnerHTML={{ __html: worldMapSvg }} />
      {hovered && (
        <div className="admin-world-map-tooltip">
          <strong>{hovered.country_name}</strong> — {hovered.total} user{hovered.total === 1 ? "" : "s"}
          <ul>
            {Object.entries(hovered.tiers).map(([tierId, count]) => (
              <li key={tierId}>
                <span className="admin-tier-dot" style={{ background: TIER_COLORS[tierId] || TIER_COLORS.none }} />
                {TIER_LABELS[tierId] || tierId}: {count}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="admin-world-map-legend">
        {Object.entries(TIER_LABELS).map(([tierId, label]) => (
          <span key={tierId} className="admin-legend-item">
            <span className="admin-tier-dot" style={{ background: TIER_COLORS[tierId] }} /> {label}
          </span>
        ))}
        <span className="admin-legend-item"><span className="admin-tier-dot" style={{ background: "#F1F5F9", border: "1px solid #E2E8F0" }} /> No data yet</span>
      </div>
      <p className="admin-section-note">
        {totalUsers} user{totalUsers === 1 ? "" : "s"} with a known location, across {countriesCovered} countr{countriesCovered === 1 ? "y" : "ies"}. A country is colored by its real majority tier — hover a country for its exact breakdown.
      </p>
    </div>
  );
}
