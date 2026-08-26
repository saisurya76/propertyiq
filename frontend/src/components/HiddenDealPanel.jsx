import { useState } from "react";
import { getCitiesForCountry } from "../utils/citiesByCountry";
import { studioApi } from "../studio/studioApi";

// PropertyIQ "Hidden Deal" — a curiosity-driven staged reveal: rather
// than showing everything at once, reveals up to 3 real findings one at
// a time, each unlocked by clicking "Show me more". Same real,
// comparables-backed logic as Instant Property Score (same backend
// function underneath), just a different presentation.
function HiddenDealPanel({ country }) {
  const [price, setPrice] = useState("");
  const [city, setCity] = useState("");
  const [propertyType, setPropertyType] = useState("Apartment");
  const [areaValue, setAreaValue] = useState("");
  const [areaUnit, setAreaUnit] = useState("sqft");
  const [state, setState] = useState("idle"); // "idle" | "loading" | "done" | "error"
  const [result, setResult] = useState(null);
  const [revealedCount, setRevealedCount] = useState(0);
  const [errorMessage, setErrorMessage] = useState("");

  const availableCities = getCitiesForCountry(country || "India", city);

  const handleSearch = async () => {
    if (!price || !city || !areaValue) return;
    setState("loading");
    setErrorMessage("");
    setRevealedCount(0);
    try {
      const data = await studioApi.getHiddenDeal(Number(price), city, propertyType, Number(areaValue), areaUnit);
      setResult(data);
      setState("done");
    } catch (err) {
      setErrorMessage(err.message || "Couldn't search for findings right now.");
      setState("error");
    }
  };

  const totalFindings = result?.findings?.length || 0;
  const allRevealed = revealedCount >= totalFindings;

  return (
    <div className="hidden-deal-panel">
      <p className="hidden-deal-intro">
        We'll search for real findings about this property — pricing signals, what's still
        unknown, and negotiation angles — revealed one at a time. Free, no account needed.
      </p>

      <div className="hidden-deal-field-grid">
        <div className="hidden-deal-field">
          <label>Quoted Price</label>
          <input type="number" min="0" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="e.g. 6600000" />
        </div>
        <div className="hidden-deal-field">
          <label>City</label>
          <select value={city} onChange={(e) => setCity(e.target.value)}>
            {availableCities.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>
        <div className="hidden-deal-field">
          <label>Property Type</label>
          <select value={propertyType} onChange={(e) => setPropertyType(e.target.value)}>
            <option value="Apartment">Apartment</option>
            <option value="Villa">Villa</option>
            <option value="Plot">Plot</option>
            <option value="Commercial">Commercial</option>
          </select>
        </div>
        <div className="hidden-deal-field">
          <label>Area</label>
          <div className="hidden-deal-area-row">
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
        className="hidden-deal-btn"
        onClick={handleSearch}
        disabled={state === "loading" || !price || !city || !areaValue}
      >
        {state === "loading" ? "Searching..." : "What did PropertyIQ find?"}
      </button>

      {state === "error" && <p className="hidden-deal-error">{errorMessage}</p>}

      {state === "done" && result && (
        <div className="hidden-deal-result">
          {revealedCount === 0 && (
            <p className="hidden-deal-teaser">
              We found {totalFindings} thing{totalFindings === 1 ? "" : "s"} you should know before buying this property.
            </p>
          )}

          {result.findings.slice(0, revealedCount).map((finding, i) => (
            <div key={i} className="hidden-deal-finding">
              <div className="hidden-deal-finding-title">{finding.icon} {finding.title}</div>
              <p className="hidden-deal-finding-detail">{finding.detail}</p>
            </div>
          ))}

          {!allRevealed && (
            <button
              type="button"
              className="hidden-deal-reveal-btn"
              onClick={() => setRevealedCount((n) => n + 1)}
            >
              {revealedCount === 0 ? "Reveal first finding" : "Show me more"}
            </button>
          )}

          {allRevealed && (
            <p className="hidden-deal-cta">
              That's everything this quick check found. Run the full PropertyIQ assessment above
              for developer track record, government value comparison, and complete fraud-risk analysis.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default HiddenDealPanel;
