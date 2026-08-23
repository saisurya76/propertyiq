import { useEffect, useState } from "react";
import { studioApi } from "./studioApi";

function StudioDesigns({ onStartNew, onResume, urlCountryContext }) {
  const [properties, setProperties] = useState(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);

  const fetchProperties = () =>
    studioApi
      .listProperties()
      .then((res) => setProperties(res.properties))
      .catch((e) => setError(e.message || "Couldn't load your saved designs."));

  // The initial load stays a plain, direct fetch call (no synchronous
  // setState calls inside the effect body itself) — the refresh button's
  // click handler below is what needs the synchronous state resets
  // (clearing the old error, showing the "Refreshing..." state), and
  // that's safe there since it's triggered by a user event, not an effect.
  useEffect(() => {
    fetchProperties();
  }, []);

  const handleRefreshClick = () => {
    setRefreshing(true);
    setError("");
    fetchProperties().finally(() => setRefreshing(false));
  };

  return (
    <div className="studio-designs">
      <div className="studio-designs-header-row">
        <div>
          <h2>Your Construction Studio</h2>
          <p className="studio-subtext">Pick up a saved design, or start a fresh one.</p>
        </div>
        <button
          type="button"
          className="page-refresh-btn"
          onClick={handleRefreshClick}
          disabled={refreshing}
          title="Refresh this list without leaving the page"
        >
          {refreshing ? "Refreshing..." : "↻ Refresh"}
        </button>
      </div>

      <button type="button" className="cs-nav-btn cs-nav-primary studio-designs-new-btn" onClick={onStartNew}>
        + Start New Design
      </button>

      {error && <div className="studio-status-banner" style={{ background: "#fef2f2", borderColor: "#fecaca", color: "#991b1b" }}>{error}</div>}

      {properties === null && !error && <p className="studio-subtext">Loading your saved designs...</p>}

      {properties && properties.length === 0 && (
        <p className="studio-subtext">No saved designs yet — start one above, and it'll show up here to pick up later.</p>
      )}

      {properties && properties.length > 0 && (
        <div className="studio-designs-grid">
          {properties.map((p) => {
            // A design belonging to a different country than the
            // current site is view-only from here — matches the same
            // rule already enforced once a design is actually opened
            // (see ConstructionStudio's cross-site lock), but a real
            // reported gap was that this list gave no indication of it
            // BEFORE clicking through. Older designs with no saved
            // country (predate the field) are treated as India, the
            // same fallback used everywhere else for that case.
            const designCountry = p.country || "India";
            const siteCountry = urlCountryContext ? urlCountryContext.name : "India";
            const crossSiteLocked = designCountry !== siteCountry;
            return (
              <div key={p.property_id} className="studio-design-card" onClick={() => onResume(p.property_id)}>
                <div className="studio-design-card-header">
                  <h4>{p.name}</h4>
                  {p.locked && <span className="studio-design-lock-badge">🔒 Locked</span>}
                  {!p.locked && crossSiteLocked && (
                    <span className="studio-design-lock-badge studio-design-cross-site-badge" title={`Created for ${designCountry} — view only on the ${siteCountry} site`}>
                      🔒 {designCountry} (view only here)
                    </span>
                  )}
                </div>
                <p className="studio-design-card-meta">
                  {p.plot_size_sqft} sqft · {p.floor_count} floor{p.floor_count === 1 ? "" : "s"}
                </p>
                <p className="studio-design-card-updated">
                  Updated {new Date(p.updated_at).toLocaleDateString()}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default StudioDesigns;
