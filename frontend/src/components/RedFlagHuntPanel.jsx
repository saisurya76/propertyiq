import { useState } from "react";
import { getCitiesForCountry } from "../utils/citiesByCountry";
import { studioApi } from "../studio/studioApi";

const CATEGORIES = ["Price", "Area", "Builder", "Location", "Amenities", "Other"];

// PropertyIQ "Red Flag Hunt" — an interactive quiz. User guesses which
// category is most suspicious, then gets an honest verdict: a genuine
// correct/false-alarm judgment for Price/Area (backed by real
// comparables data), or an honest "this quick check can't verify that"
// for categories with no real basis to judge — never a fabricated
// verdict about something with zero actual data behind it.
function RedFlagHuntPanel({ country }) {
  const [price, setPrice] = useState("");
  const [city, setCity] = useState("");
  const [propertyLocation, setPropertyLocation] = useState("");
  const [propertyType, setPropertyType] = useState("Apartment");
  const [areaValue, setAreaValue] = useState("");
  const [areaUnit, setAreaUnit] = useState("sqft");
  const [step, setStep] = useState("input"); // "input" | "guessing" | "result" | "error"
  const [guessedCategory, setGuessedCategory] = useState(null);
  const [result, setResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");

  const availableCities = getCitiesForCountry(country || "India", city);

  const handleStart = () => {
    if (!price || !city || !areaValue) return;
    setStep("guessing");
  };

  const handleGuess = async (category) => {
    setGuessedCategory(category);
    setErrorMessage("");
    try {
      const data = await studioApi.getRedFlagVerdict(Number(price), city, propertyType, Number(areaValue), areaUnit, category, propertyLocation);
      setResult(data);
      setStep("result");
    } catch (err) {
      setErrorMessage(err.message || "Couldn't check that guess right now.");
      setStep("error");
    }
  };

  const verdictIcon = result?.verdict === "correct" ? "✅" : result?.verdict === "false_alarm" ? "❌" : "🔍";
  const verdictLabel = result?.verdict === "correct" ? "Correct concern" : result?.verdict === "false_alarm" ? "False alarm" : "Can't verify from this quick check";

  return (
    <div className="red-flag-hunt-panel">
      <p className="red-flag-hunt-intro">
        Think you can spot a bad property deal? Enter a property, guess what's suspicious about
        it, and see if you're right. Free, no account needed.
      </p>

      {step === "input" && (
        <>
          <div className="red-flag-hunt-field-grid">
            <div className="red-flag-hunt-field">
              <label>Quoted Price</label>
              <input type="number" min="0" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="e.g. 6600000" />
            </div>
            <div className="red-flag-hunt-field">
              <label>City</label>
              <select value={city} onChange={(e) => setCity(e.target.value)}>
                {availableCities.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
            <div className="red-flag-hunt-field">
              <label>Locality (optional, for reference)</label>
              <input type="text" value={propertyLocation} onChange={(e) => setPropertyLocation(e.target.value)} placeholder="e.g. Gachibowli" title="Shown alongside your result for clarity — the verdict is calculated from citywide comparable data, not locality-specific data" />
            </div>
            <div className="red-flag-hunt-field">
              <label>Property Type</label>
              <select value={propertyType} onChange={(e) => setPropertyType(e.target.value)}>
                <option value="Apartment">Apartment</option>
                <option value="Villa">Villa</option>
                <option value="Plot">Plot</option>
                <option value="Commercial">Commercial</option>
              </select>
            </div>
            <div className="red-flag-hunt-field">
              <label>Area</label>
              <div className="red-flag-hunt-area-row">
                <input type="number" min="0" value={areaValue} onChange={(e) => setAreaValue(e.target.value)} placeholder="e.g. 1200" />
                <select value={areaUnit} onChange={(e) => setAreaUnit(e.target.value)}>
                  <option value="sqft">sqft</option>
                  <option value="sqm">sqm</option>
                </select>
              </div>
            </div>
          </div>
          <button type="button" className="red-flag-hunt-btn" onClick={handleStart} disabled={!price || !city || !areaValue}>
            Can you spot the red flags?
          </button>
        </>
      )}

      {step === "guessing" && (
        <div className="red-flag-hunt-guess-section">
          <p className="red-flag-hunt-question">What do you think is most suspicious about this property?</p>
          <div className="red-flag-hunt-category-grid">
            {CATEGORIES.map((category) => (
              <button
                key={category}
                type="button"
                className="red-flag-hunt-category-btn"
                onClick={() => handleGuess(category)}
              >
                {category}
              </button>
            ))}
          </div>
        </div>
      )}

      {step === "error" && <p className="red-flag-hunt-error">{errorMessage}</p>}

      {step === "result" && result && (
        <div className="red-flag-hunt-result">
          {result.location && (
            <p className="red-flag-hunt-location">📍 {result.location}, {city}</p>
          )}
          <div className="red-flag-hunt-verdict">
            {verdictIcon} You guessed "{guessedCategory}" — {verdictLabel}
          </div>
          <p className="red-flag-hunt-verdict-detail">{result.verdict_detail}</p>

          {result.additional_findings.length > 0 && (
            <>
              <p className="red-flag-hunt-more-heading">
                PropertyIQ found {result.additional_findings.length} more thing{result.additional_findings.length === 1 ? "" : "s"} you should investigate:
              </p>
              {result.additional_findings.map((finding, i) => (
                <div key={i} className="red-flag-hunt-finding">
                  <div className="red-flag-hunt-finding-title">{finding.icon} {finding.title}</div>
                  <p className="red-flag-hunt-finding-detail">{finding.detail}</p>
                </div>
              ))}
            </>
          )}

          <p className="red-flag-hunt-cta">
            Run the full PropertyIQ assessment above for complete developer track record, government
            value comparison, and real fraud-risk analysis.
          </p>
        </div>
      )}
    </div>
  );
}

export default RedFlagHuntPanel;
