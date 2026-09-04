import { useEffect, useRef, useState } from "react";

const API_BASE = "https://propertyiq-api-q21y.onrender.com";
const MAX_AREAS = 5;

// Requested but honestly not buildable today: no genuine free,
// real, per-area (not just country-level) API exists for any of
// these worldwide — shown as explicit "Not available" rows rather
// than fabricated numbers, which would be actively misleading in a
// tool people use to make a real property decision.
const NOT_YET_AVAILABLE_METRICS = [
  "Traffic congestion",
  "Ease of living",
  "Food safety",
  "Municipality rankings",
];
const STORAGE_KEY = "propertyiq_ni_comparison_id";

function emptyArea() {
  return { city: "", country: "", locality: "", lat: null, lon: null, addressQuery: "", suggestions: [] };
}

function NeighborhoodComparison() {
  const [areas, setAreas] = useState([emptyArea(), emptyArea()]);
  const [comparisonId, setComparisonId] = useState(null);
  const [results, setResults] = useState(null);
  const [monitoring, setMonitoring] = useState(false);
  const [lastRefreshedAt, setLastRefreshedAt] = useState(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const debounceRefs = useRef({});

  // Ready when the page loads: a previously-created comparison (this
  // browser's own, via localStorage — the whole page is public/no-
  // login, so there's no account to attach this to instead) loads its
  // already-fetched, cached results immediately, no waiting on a live
  // fetch — refreshed in the background by the hourly monitoring loop
  // if the visitor turned that on, not by this page load itself.
  useEffect(() => {
    const savedId = localStorage.getItem(STORAGE_KEY);
    if (!savedId) return;
    fetch(`${API_BASE}/api/neighborhood-insights/compare/${savedId}`)
      .then((res) => { if (!res.ok) throw new Error("not found"); return res.json(); })
      .then((data) => {
        setComparisonId(data.comparison_id);
        setResults(data.results);
        setMonitoring(data.monitoring);
        setLastRefreshedAt(data.last_refreshed_at);
      })
      .catch(() => localStorage.removeItem(STORAGE_KEY));
  }, []);

  const updateArea = (index, patch) => {
    setAreas((prev) => prev.map((a, i) => (i === index ? { ...a, ...patch } : a)));
  };

  const handleAddressInput = (index, value) => {
    updateArea(index, { addressQuery: value, city: "", locality: "", lat: null, lon: null });
    clearTimeout(debounceRefs.current[index]);
    if (value.trim().length < 3) {
      updateArea(index, { suggestions: [] });
      return;
    }
    debounceRefs.current[index] = setTimeout(async () => {
      try {
        // country="" (explicitly empty) is the real, global-search
        // mode — see neighborhood_autocomplete's own docstring: this
        // feature deliberately isn't limited to the 5 sites the rest
        // of the app supports.
        const url = `${API_BASE}/api/neighborhood-insights/autocomplete?q=${encodeURIComponent(value)}&country=`;
        const res = await fetch(url);
        const data = await res.json();
        updateArea(index, { suggestions: Array.isArray(data) ? data : [] });
      } catch {
        updateArea(index, { suggestions: [] });
      }
    }, 300);
  };

  const selectSuggestion = (index, item) => {
    const label = item.display_name || item.display_place || "";
    // LocationIQ's own address breakdown — city/town/state, whatever
    // it actually has for this result — used directly rather than
    // asking the visitor to separately re-type a city that's already
    // right there in the selected suggestion.
    const addr = item.address || {};
    const city = addr.city || addr.town || addr.village || addr.county || label.split(",")[0] || "";
    const country = addr.country || "";
    updateArea(index, {
      addressQuery: label,
      city,
      country,
      locality: label,
      lat: parseFloat(item.lat),
      lon: parseFloat(item.lon),
      suggestions: [],
    });
  };

  const addAreaRow = () => {
    if (areas.length >= MAX_AREAS) return;
    setAreas((prev) => [...prev, emptyArea()]);
  };

  const removeAreaRow = (index) => {
    if (areas.length <= 2) return;
    setAreas((prev) => prev.filter((_, i) => i !== index));
  };

  const handleCompare = async () => {
    const validAreas = areas.filter((a) => a.city && a.lat !== null);
    if (validAreas.length < 2) {
      setError("Select at least 2 areas from the suggestions (each needs a real address selected, not just typed).");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/neighborhood-insights/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          areas: validAreas.map((a) => ({
            city: a.city, country: a.country || "Unknown", locality: a.locality, lat: a.lat, lon: a.lon,
          })),
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Couldn't create the comparison.");
      }
      const data = await res.json();
      setComparisonId(data.comparison_id);
      setResults(data.results);
      setMonitoring(data.monitoring);
      setLastRefreshedAt(data.last_refreshed_at);
      localStorage.setItem(STORAGE_KEY, data.comparison_id);
    } catch (err) {
      setError(err.message || "Couldn't create the comparison right now.");
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshNow = async () => {
    if (!comparisonId) return;
    setRefreshing(true);
    try {
      const res = await fetch(`${API_BASE}/api/neighborhood-insights/compare/${comparisonId}/refresh`, { method: "POST" });
      const data = await res.json();
      setResults(data.results);
      setLastRefreshedAt(data.last_refreshed_at);
    } catch {
      setError("Couldn't refresh right now — try again shortly.");
    } finally {
      setRefreshing(false);
    }
  };

  const toggleMonitoring = async () => {
    if (!comparisonId) return;
    const next = !monitoring;
    try {
      const res = await fetch(`${API_BASE}/api/neighborhood-insights/compare/${comparisonId}/monitor`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ monitoring: next }),
      });
      const data = await res.json();
      setMonitoring(data.monitoring);
    } catch {
      setError("Couldn't update monitoring right now — try again shortly.");
    }
  };

  return (
    <div className="ni-comparison-section">
      <h3>Compare Areas</h3>
      <p className="ni-comparison-intro">
        Compare up to {MAX_AREAS} areas — any city, any country — side by side on resale activity,
        upcoming infrastructure, and flood-risk proximity.
      </p>

      {areas.map((area, index) => (
        <div key={index} className="ni-comparison-area-row">
          <div className="ni-comparison-address-wrap">
            <input
              type="text"
              placeholder={`Area ${index + 1} — search any address, locality, or city`}
              value={area.addressQuery}
              onChange={(e) => handleAddressInput(index, e.target.value)}
              autoComplete="off"
            />
            {area.suggestions.length > 0 && (
              <ul className="ni-comparison-suggestions">
                {area.suggestions.map((s, i) => (
                  <li key={i} onClick={() => selectSuggestion(index, s)}>{s.display_name || s.display_place}</li>
                ))}
              </ul>
            )}
          </div>
          {areas.length > 2 && (
            <button type="button" className="ni-comparison-remove-btn" onClick={() => removeAreaRow(index)} title="Remove this area">✕</button>
          )}
        </div>
      ))}

      <div className="ni-comparison-actions">
        {areas.length < MAX_AREAS && (
          <button type="button" className="ni-comparison-add-btn" onClick={addAreaRow}>+ Add another area</button>
        )}
        <button type="button" className="ni-primary-btn" onClick={handleCompare} disabled={loading}>
          {loading ? "Comparing..." : "Compare"}
        </button>
      </div>

      {error && <p className="ni-comparison-error">{error}</p>}

      {results && (
        <>
          <div className="ni-comparison-meta">
            <span>Last refreshed: {lastRefreshedAt ? new Date(lastRefreshedAt).toLocaleString() : "—"}</span>
            <button type="button" className="ni-comparison-refresh-btn" onClick={handleRefreshNow} disabled={refreshing}>
              {refreshing ? "Refreshing..." : "↻ Refresh now"}
            </button>
            <label className="ni-comparison-monitor-toggle">
              <input type="checkbox" checked={monitoring} onChange={toggleMonitoring} />
              Keep monitoring (auto-refreshes hourly)
            </label>
          </div>

          <div className="ni-comparison-table-scroll">
            <table className="ni-comparison-table">
              <thead>
                <tr>
                  <th>Area</th>
                  {results.map((r, i) => (
                    <th key={i}>{r.city}{r.country ? `, ${r.country}` : ""}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Overall ranking</td>
                  {results.map((r, i) => (
                    <td key={i}>
                      {r.overall_ranking?.has_data
                        ? <>
                            <strong>{r.overall_ranking?.score} / 100</strong>
                            <div className="ni-comparison-resolved-note">from {r.overall_ranking?.contributors.join(", ")}</div>
                          </>
                        : "Not enough data yet"}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>Avg. price/sqft <span className="ni-comparison-metric-label">(appreciation / resale value proxy)</span></td>
                  {results.map((r, i) => (
                    <td key={i}>
                      {r.resale_signal?.has_data
                        ? <>
                            {r.resale_signal?.currency} {r.resale_signal?.average_price_per_sqft.toLocaleString()}
                            {r.resale_signal?.resolved_city && (
                              <div className="ni-comparison-resolved-note">via {r.resale_signal?.resolved_city} city data</div>
                            )}
                          </>
                        : "No data"}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>Comparable listings</td>
                  {results.map((r, i) => (
                    <td key={i}>{r.resale_signal?.has_data ? r.resale_signal?.comparable_count : "—"}</td>
                  ))}
                </tr>
                <tr>
                  <td>Air pollution index</td>
                  {results.map((r, i) => (
                    <td key={i}>
                      {r.air_quality?.has_data
                        ? <>
                            {r.air_quality?.aqi_label} ({r.air_quality?.aqi}/5)
                            <div className="ni-comparison-resolved-note">PM2.5: {r.air_quality?.pm2_5} · {r.air_quality?.scale}</div>
                          </>
                        : "Not available"}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>Nearby water bodies <span className="ni-comparison-metric-label">(flood-risk proxy)</span></td>
                  {results.map((r, i) => (
                    <td key={i}>{r.flood_risk?.has_data ? r.flood_risk?.nearby_water_count : "—"}</td>
                  ))}
                </tr>
                <tr>
                  <td>Infrastructure news</td>
                  {results.map((r, i) => (
                    <td key={i} className="ni-comparison-summary-cell">
                      {r.infrastructure?.has_data ? r.infrastructure?.summary : "No recent news found"}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>Job prospects <span className="ni-comparison-metric-label">(country-level unemployment rate)</span></td>
                  {results.map((r, i) => (
                    <td key={i}>
                      {r.world_bank?.has_data && r.world_bank?.unemployment_rate
                        ? `${r.world_bank.unemployment_rate.value.toFixed(1)}% (${r.world_bank.unemployment_rate.year})`
                        : "Not available"}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>Business environment <span className="ni-comparison-metric-label">(country-level GDP growth)</span></td>
                  {results.map((r, i) => (
                    <td key={i}>
                      {r.world_bank?.has_data && r.world_bank?.gdp_growth
                        ? `${r.world_bank.gdp_growth.value.toFixed(1)}% (${r.world_bank.gdp_growth.year})`
                        : "Not available"}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>Tourism index <span className="ni-comparison-metric-label">(country-level annual arrivals)</span></td>
                  {results.map((r, i) => (
                    <td key={i}>
                      {r.world_bank?.has_data && r.world_bank?.tourist_arrivals
                        ? `${Math.round(r.world_bank.tourist_arrivals.value / 1000000)}M/yr (${r.world_bank.tourist_arrivals.year})`
                        : "Not available"}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td>Diseases <span className="ni-comparison-metric-label">(country-level life expectancy proxy)</span></td>
                  {results.map((r, i) => (
                    <td key={i}>
                      {r.world_bank?.has_data && r.world_bank?.life_expectancy
                        ? `${r.world_bank.life_expectancy.value.toFixed(1)} yrs (${r.world_bank.life_expectancy.year})`
                        : "Not available"}
                    </td>
                  ))}
                </tr>
                {NOT_YET_AVAILABLE_METRICS.map((metric) => (
                  <tr key={metric} className="ni-comparison-unavailable-row">
                    <td>{metric}</td>
                    {results.map((_, i) => (
                      <td key={i}>Not available</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="ni-comparison-honesty-note">
            "Not available" rows have no genuine free data source today — shown honestly rather than filled in with invented numbers.
            Rows marked "country-level" are real World Bank data for the whole country, not this specific area — most useful when comparing across countries, less so between two areas of the same city.
          </p>
        </>
      )}
    </div>
  );
}

export default NeighborhoodComparison;
