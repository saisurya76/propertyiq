import { useState } from "react";
import { getCitiesForCountry } from "../utils/citiesByCountry";
import { studioApi } from "../studio/studioApi";

// PropertyIQ "Should I Buy This?" Challenge — creator side. Builds a
// shareable link (no account needed to create or view) that anyone can
// open, guess a price on, and see how their guess compares to
// PropertyIQ's real fair value. The recipient's experience lives at
// /challenge/{id}, a completely separate standalone page — see
// ChallengeView.jsx — not part of this app's normal navigation.
function ChallengeCreatePanel({ country }) {
  const [price, setPrice] = useState("");
  const [city, setCity] = useState("");
  const [location, setLocation] = useState("");
  const [propertyType, setPropertyType] = useState("Apartment");
  const [areaValue, setAreaValue] = useState("");
  const [areaUnit, setAreaUnit] = useState("sqft");
  const [state, setState] = useState("idle"); // "idle" | "loading" | "done" | "error"
  const [shareUrl, setShareUrl] = useState("");
  const [copied, setCopied] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const availableCities = getCitiesForCountry(country || "India", city);

  const handleCreate = async () => {
    if (!price || !city || !areaValue) return;
    setState("loading");
    setErrorMessage("");
    setCopied(false);
    try {
      const data = await studioApi.createChallenge(Number(price), city, propertyType, Number(areaValue), areaUnit, location);
      const url = `${window.location.origin}/challenge/${data.challenge_id}`;
      setShareUrl(url);
      setState("done");
    } catch (err) {
      setErrorMessage(err.message || "Couldn't create a challenge right now.");
      setState("error");
    }
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access can fail (permissions, insecure context) — the
      // link is still shown and selectable, so this isn't a hard failure.
    }
  };

  return (
    <div className="challenge-create-panel">
      <p className="challenge-create-intro">
        Create a shareable link for any property — friends guess the price with no account
        needed, then see how close they got to PropertyIQ's real fair value.
      </p>

      {state !== "done" && (
        <>
          <div className="challenge-create-field-grid">
            <div className="challenge-create-field">
              <label>Quoted Price</label>
              <input type="number" min="0" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="e.g. 6600000" />
            </div>
            <div className="challenge-create-field">
              <label>City</label>
              <select value={city} onChange={(e) => setCity(e.target.value)}>
                {availableCities.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </div>
            <div className="challenge-create-field">
              <label>Locality (optional, for reference)</label>
              <input type="text" value={location} onChange={(e) => setLocation(e.target.value)} placeholder="e.g. Gachibowli" />
            </div>
            <div className="challenge-create-field">
              <label>Property Type</label>
              <select value={propertyType} onChange={(e) => setPropertyType(e.target.value)}>
                <option value="Apartment">Apartment</option>
                <option value="Villa">Villa</option>
                <option value="Plot">Plot</option>
                <option value="Commercial">Commercial</option>
              </select>
            </div>
            <div className="challenge-create-field">
              <label>Area</label>
              <div className="challenge-create-area-row">
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
            className="challenge-create-btn"
            onClick={handleCreate}
            disabled={state === "loading" || !price || !city || !areaValue}
          >
            {state === "loading" ? "Creating..." : "Create Challenge Link"}
          </button>
          {state === "error" && <p className="challenge-create-error">{errorMessage}</p>}
        </>
      )}

      {state === "done" && (
        <div className="challenge-create-result">
          <p className="challenge-create-success">Your challenge is ready to share!</p>
          <div className="challenge-create-link-row">
            <input type="text" readOnly value={shareUrl} className="challenge-create-link-input" />
            <button type="button" className="challenge-create-copy-btn" onClick={handleCopy}>
              {copied ? "Copied!" : "Copy Link"}
            </button>
          </div>
          <p className="challenge-create-share-hint">
            Share it on WhatsApp, Instagram, LinkedIn, or X — whoever opens it can guess the
            price with no account needed.
          </p>
          <button
            type="button"
            className="challenge-create-another-btn"
            onClick={() => { setState("idle"); setPrice(""); setAreaValue(""); }}
          >
            Create another challenge
          </button>
        </div>
      )}
    </div>
  );
}

export default ChallengeCreatePanel;
