import { useState } from "react";
import { getCitiesForCountry } from "../utils/citiesByCountry";
import { studioApi } from "../studio/studioApi";

// PropertyIQ "Instant Property Score" — a free, no-signup, 10-second
// score from just price + city + area, backed by real comparable-listing
// data (currently Hyderabad apartments/villas only — honestly says so
// for anything else, rather than faking a number). A lightweight funnel
// into the full assessment below, not a replacement for it — deliberately
// skips every fraud-verification field (developer track record,
// government value, etc) that the full form asks for.
function InstantScorePanel({ country }) {
  const [price, setPrice] = useState("");
  const [city, setCity] = useState("");
  const [location, setLocation] = useState("");
  const [propertyType, setPropertyType] = useState("Apartment");
  const [areaValue, setAreaValue] = useState("");
  const [areaUnit, setAreaUnit] = useState("sqft");
  const [state, setState] = useState("idle"); // "idle" | "loading" | "done" | "error"
  const [result, setResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");

  const availableCities = getCitiesForCountry(country || "India", city);

  const handleCheck = async () => {
    if (!price || !city || !areaValue) return;
    setState("loading");
    setErrorMessage("");
    try {
      const data = await studioApi.getInstantScore(Number(price), city, propertyType, Number(areaValue), areaUnit, location);
      setResult(data);
      setState("done");
    } catch (err) {
      setErrorMessage(err.message || "Couldn't calculate a score right now.");
      setState("error");
    }
  };

  const scoreColor = result?.label === "Strong" ? "#059669" : result?.label === "Investigate" ? "#d97706" : "#dc2626";
  const scoreEmoji = result?.label === "Strong" ? "🟢" : result?.label === "Investigate" ? "🟡" : "🔴";

  return (
    <div className="instant-score-panel">
      <p className="instant-score-intro">
        Just the price, location, and area — no account needed. Get a free 10-second read on
        whether this property is worth investigating further.
      </p>

      <div className="instant-score-field-grid">
        <div className="instant-score-field">
          <label>Quoted Price</label>
          <input type="number" min="0" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="e.g. 6600000" />
        </div>
        <div className="instant-score-field">
          <label>City</label>
          <select value={city} onChange={(e) => setCity(e.target.value)}>
            {availableCities.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>
        <div className="instant-score-field">
          <label>Locality (optional, for reference)</label>
          <input type="text" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="e.g. Gachibowli" title="Shown alongside your result for clarity — the score itself is calculated from citywide comparable data, not locality-specific data" />
        </div>
        <div className="instant-score-field">
          <label>Property Type</label>
          <select value={propertyType} onChange={(e) => setPropertyType(e.target.value)}>
            <option value="Apartment">Apartment</option>
            <option value="Villa">Villa</option>
            <option value="Plot">Plot</option>
            <option value="Commercial">Commercial</option>
          </select>
        </div>
        <div className="instant-score-field">
          <label>Area</label>
          <div className="instant-score-area-row">
            <input type="number" min="0" value={areaValue} onChange={(e) => setAreaValue(e.target.value)} placeholder="e.g. 1200" />
            <select value={areaUnit} onChange={(e) => setAreaUnit(e.target.value)}>
              <option value="sqft">sqft</option>
              <option value="sqm">sqm</option>
            </select>
          </div>
        </div>
      </div>

      <button
        type="button"
        className="instant-score-btn"
        onClick={handleCheck}
        disabled={state === "loading" || !price || !city || !areaValue}
      >
        {state === "loading" ? "Checking..." : "Check Score"}
      </button>

      {state === "error" && <p className="instant-score-error">{errorMessage}</p>}

      {state === "done" && result && (
        <div className="instant-score-result">
          {result.coverage === "unsupported" ? (
            <p className="instant-score-unsupported">{result.reason}</p>
          ) : (
            <>
              <div className="instant-score-badge" style={{ color: scoreColor }}>
                {scoreEmoji} {result.score}/100 — {result.label}
              </div>
              {result.location && (
                <p className="instant-score-location">📍 {result.location}, {result.city}</p>
              )}
              <p className="instant-score-reason">{result.reason}</p>
              <p className="instant-score-cta">
                Want the full picture — developer track record, government value comparison, and
                real fraud-risk analysis? Run the full PropertyIQ assessment above.
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default InstantScorePanel;
