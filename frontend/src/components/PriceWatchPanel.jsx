import { useState } from "react";
import { getCitiesForCountry } from "../utils/citiesByCountry";
import { studioApi, getSession } from "../studio/studioApi";

// PropertyIQ "Price Drop Alert" — lets a user watch a property and get
// emailed when it hits their target price. Now a real, tier-gated
// feature (like every other paid feature in this app) rather than a
// public, no-account tool — a real, explicit shift made necessary by
// the per-tier watch-count limit, which can only be meaningful if a
// watch is tied to a signed-in account rather than an arbitrary email
// string anyone could vary to bypass it. Notifications go to whichever
// email the user is signed in with — there's no separate email field
// to fill in.
//
// Honest distinction surfaced directly in the UI, not glossed over: a
// watch created from a URL gets genuinely, automatically re-checked
// every few hours by re-fetching the listing (its real starting price
// is also read from the listing itself on creation, not guessed). A
// watch created from manual entry has nothing to re-fetch — its price
// only changes when the user comes back and updates it themselves, via
// the "update my price" flow shown after creation.
function PriceWatchPanel({ country, onLaunchStudio }) {
  const [mode, setMode] = useState("manual"); // "manual" | "url"
  const [url, setUrl] = useState("");
  const [price, setPrice] = useState("");
  const [city, setCity] = useState("");
  const [propertyType, setPropertyType] = useState("Apartment");
  const [areaValue, setAreaValue] = useState("");
  const [areaUnit, setAreaUnit] = useState("sqft");
  const [targetPrice, setTargetPrice] = useState("");
  const [state, setState] = useState("idle"); // "idle" | "loading" | "done" | "error"
  const [watch, setWatch] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");

  // For the "update my price" flow on a manual watch, shown after creation
  const [updatePriceInput, setUpdatePriceInput] = useState("");
  const [updateState, setUpdateState] = useState("idle");

  const availableCities = getCitiesForCountry(country || "India", city);

  const canCreate = targetPrice && (mode === "url" ? url : (price && city && areaValue));

  const handleCreate = async () => {
    if (!canCreate) return;
    if (!getSession()) {
      onLaunchStudio?.(); // routes to sign-in first, same pattern as every other gated feature
      return;
    }
    setState("loading");
    setErrorMessage("");
    try {
      // In URL mode, price/city/propertyType/areaValue are intentionally
      // left for the backend to extract from the listing itself — never
      // guessed or sent as placeholders here.
      const data = mode === "url"
        ? await studioApi.createPriceWatch(undefined, undefined, undefined, undefined, Number(targetPrice), areaUnit, url)
        : await studioApi.createPriceWatch(Number(price), city, propertyType, Number(areaValue), Number(targetPrice), areaUnit, null);
      setWatch(data);
      setState("done");
    } catch (err) {
      setErrorMessage(err.message || "Couldn't create a price watch right now.");
      setState("error");
    }
  };

  const handleUpdatePrice = async () => {
    if (!updatePriceInput || !watch) return;
    setUpdateState("loading");
    try {
      const data = await studioApi.updateWatchPrice(watch.watch_id, Number(updatePriceInput));
      setWatch(data);
      setUpdateState("done");
      setUpdatePriceInput("");
    } catch (err) {
      setUpdateState("error");
      setErrorMessage(err.message || "Couldn't update the price right now.");
    }
  };

  return (
    <div className="price-watch-panel">
      <p className="price-watch-intro">
        Don't chase property prices — let PropertyIQ watch for you. We'll email you when a
        property hits your target price.
      </p>

      {state !== "done" && (
        <>
          <div className="price-watch-mode-toggle">
            <button
              type="button"
              className={`price-watch-mode-btn ${mode === "manual" ? "price-watch-mode-active" : ""}`}
              onClick={() => setMode("manual")}
            >
              Enter price manually
            </button>
            <button
              type="button"
              className={`price-watch-mode-btn ${mode === "url" ? "price-watch-mode-active" : ""}`}
              onClick={() => setMode("url")}
            >
              Watch a listing URL
            </button>
          </div>

          {mode === "url" ? (
            <p className="price-watch-mode-note">
              We'll automatically re-check this listing's price every few hours — no need to come back.
            </p>
          ) : (
            <p className="price-watch-mode-note">
              We have no way to automatically detect a price change without a listing URL — you'll
              need to come back and update the price yourself when it changes.
            </p>
          )}

          <div className="price-watch-field-grid">
            {mode === "url" ? (
              <div className="price-watch-field">
                <label>Listing URL</label>
                <input type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="Paste a listing URL" />
              </div>
            ) : (
              <>
                <div className="price-watch-field">
                  <label>Current Price</label>
                  <input type="number" min="0" value={price} onChange={(e) => setPrice(e.target.value)} placeholder="e.g. 9500000" />
                </div>
                <div className="price-watch-field">
                  <label>City</label>
                  <select value={city} onChange={(e) => setCity(e.target.value)}>
                    {availableCities.map(([value, label]) => (
                      <option key={value} value={value}>{label}</option>
                    ))}
                  </select>
                </div>
                <div className="price-watch-field">
                  <label>Property Type</label>
                  <select value={propertyType} onChange={(e) => setPropertyType(e.target.value)}>
                    <option value="Apartment">Apartment</option>
                    <option value="Villa">Villa</option>
                    <option value="Plot">Plot</option>
                    <option value="Commercial">Commercial</option>
                  </select>
                </div>
                <div className="price-watch-field">
                  <label>Area</label>
                  <div className="price-watch-area-row">
                    <input type="number" min="0" value={areaValue} onChange={(e) => setAreaValue(e.target.value)} placeholder="e.g. 1200" />
                    <select value={areaUnit} onChange={(e) => setAreaUnit(e.target.value)}>
                      <option value="sqft">sqft</option>
                      <option value="sqm">sqm</option>
                    </select>
                  </div>
                </div>
              </>
            )}

            <div className="price-watch-field">
              <label>Notify me when price drops to</label>
              <input type="number" min="0" value={targetPrice} onChange={(e) => setTargetPrice(e.target.value)} placeholder="e.g. 8500000" />
            </div>
          </div>

          <button type="button" className="price-watch-btn" onClick={handleCreate} disabled={state === "loading" || !canCreate}>
            {state === "loading" ? "Setting up..." : "Watch This Property"}
          </button>
          {state === "error" && <p className="price-watch-error">{errorMessage}</p>}
        </>
      )}

      {state === "done" && watch && (
        <div className="price-watch-result">
          <p className="price-watch-success">
            ✅ PropertyIQ is watching this property for you — we'll email {watch.email} at {watch.target_price.toLocaleString()} or below.
          </p>

          {!watch.url && (
            <div className="price-watch-update-section">
              <p className="price-watch-update-label">Price changed? Update it here:</p>
              <div className="price-watch-update-row">
                <input
                  type="number"
                  min="0"
                  value={updatePriceInput}
                  onChange={(e) => setUpdatePriceInput(e.target.value)}
                  placeholder="New price"
                />
                <button type="button" className="price-watch-update-btn" onClick={handleUpdatePrice} disabled={updateState === "loading" || !updatePriceInput}>
                  {updateState === "loading" ? "Updating..." : "Update Price"}
                </button>
              </div>
              {updateState === "done" && (
                <p className={watch.status === "triggered" ? "price-watch-triggered" : "price-watch-update-confirm"}>
                  {watch.status === "triggered"
                    ? "🎉 This property just entered your Good Deal zone!"
                    : "Updated — still above your target, we'll keep this on record."}
                </p>
              )}
            </div>
          )}

          <button
            type="button"
            className="price-watch-another-btn"
            onClick={() => { setState("idle"); setWatch(null); setPrice(""); setTargetPrice(""); setUrl(""); }}
          >
            Watch another property
          </button>
        </div>
      )}
    </div>
  );
}

export default PriceWatchPanel;
