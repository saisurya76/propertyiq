import { useEffect, useRef, useState } from "react";
import { studioApi } from "./studioApi";

function StudioDesigns({ onStartNew, onResume, urlCountryContext }) {
  const [properties, setProperties] = useState(null);
  const [error, setError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [busyPropertyId, setBusyPropertyId] = useState(null); // which card is mid-export/delete, so its own buttons show a real "working" state without blocking the rest of the list
  const [importing, setImporting] = useState(false);
  const fileInputRef = useRef(null);

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

  // A real, practical answer to a real constraint: saved_designs_limit
  // caps how many designs can be kept at once, with previously no way
  // to archive one externally and free the slot back up. Downloads the
  // exact same JSON shape a re-import accepts — a real, lossless
  // round-trip, not a display-only summary.
  const handleExport = async (e, propertyId, name) => {
    e.stopPropagation(); // the whole card is clickable to open the design -- exporting shouldn't also open it
    setBusyPropertyId(propertyId);
    setError("");
    try {
      const data = await studioApi.exportProperty(propertyId);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${name.replace(/[^a-z0-9]+/gi, "_")}.propertyiq-design.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message || "Couldn't export this design.");
    } finally {
      setBusyPropertyId(null);
    }
  };

  const handleDelete = async (e, propertyId, name) => {
    e.stopPropagation();
    if (!window.confirm(`Delete "${name}"? This can't be undone — export it first if you want to keep a copy.`)) return;
    setBusyPropertyId(propertyId);
    setError("");
    try {
      await studioApi.deleteProperty(propertyId);
      setProperties((prev) => prev.filter((p) => p.property_id !== propertyId));
    } catch (err) {
      setError(err.message || "Couldn't delete this design.");
    } finally {
      setBusyPropertyId(null);
    }
  };

  const handleImportClick = () => fileInputRef.current?.click();

  const handleImportFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = ""; // lets the same file be re-selected later if the first attempt fails
    if (!file) return;
    setImporting(true);
    setError("");
    try {
      const text = await file.text();
      const parsed = JSON.parse(text);
      await studioApi.importProperty(parsed);
      await fetchProperties();
    } catch (err) {
      setError(err.message || "Couldn't import that file — make sure it's a design exported from PropertyIQ.");
    } finally {
      setImporting(false);
    }
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

      <div className="studio-designs-actions-row">
        <button type="button" className="cs-nav-btn cs-nav-primary studio-designs-new-btn" onClick={onStartNew}>
          + Start New Design
        </button>
        <button type="button" className="cs-nav-btn" onClick={handleImportClick} disabled={importing}>
          {importing ? "Importing..." : "⬆ Import a design"}
        </button>
        <input ref={fileInputRef} type="file" accept="application/json" style={{ display: "none" }} onChange={handleImportFile} />
      </div>
      <p className="studio-subtext studio-designs-hint">
        Running low on your saved-design limit? Export a design to a file, delete it here, and import it back later when you have room.
      </p>

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
            const isBusy = busyPropertyId === p.property_id;
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
                <div className="studio-design-card-actions">
                  <button type="button" className="studio-design-card-action-btn" disabled={isBusy} onClick={(e) => handleExport(e, p.property_id, p.name)}>
                    ⬇ Export
                  </button>
                  <button type="button" className="studio-design-card-action-btn studio-design-card-delete-btn" disabled={isBusy} onClick={(e) => handleDelete(e, p.property_id, p.name)}>
                    🗑 Delete
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default StudioDesigns;
