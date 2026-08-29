import { useState } from "react";
import "./App.css";

const API_BASE = "https://propertyiq-api-q21y.onrender.com";

const CATEGORIES = ["Hospitals", "Schools", "Markets", "Banks/ATMs", "Police", "Public Transport", "Parks"];

const CHECKLIST_ITEMS = [
  "Verify the title deed and confirm a clear, marketable title with no encumbrances",
  "Check RERA registration for the project (for under-construction or recently completed properties)",
  "Confirm the occupancy certificate (OC) and completion certificate (CC) have been issued",
  "Get an encumbrance certificate covering at least the last 13-30 years",
  "Review property tax receipts to confirm they're current and in the seller's name",
  "Check for any pending litigation or disputes tied to the property or land",
  "Confirm the approved building plan matches the actual construction",
  "Verify khata/mutation records reflect the current owner correctly",
];

const AUTHORITY_CONTACTS = [
  { label: "RERA (state) helpline", detail: "Varies by state — search \"[your state] RERA helpline\"" },
  { label: "Sub-Registrar's Office", detail: "Handles registration and encumbrance certificates" },
  { label: "Municipal Corporation / Panchayat", detail: "Property tax records, building plan approvals" },
  { label: "State Consumer Helpline", detail: "1915" },
];

// Standalone page, not part of the main app's navigation, reached at
// /neighborhood-insights. Deliberately mirrors the structure of the
// sibling AccidentIQ product's own Travel Safety page (same section
// order, same standalone-tool-that-cross-sells-the-main-product
// pattern) — matched to that layout on purpose, per explicit design
// direction, with PropertyIQ's own navy/emerald theme instead of
// AccidentIQ's navy/amber.
//
// HONESTY NOTE for future maintainers: the neighborhood map, flood/
// waterlogging risk, and upcoming-infrastructure sections need a real
// Google Places API key this app does not currently have configured.
// They are built here as complete, ready-to-wire UI in a clearly
// labeled "needs setup" state — never as fabricated pins or invented
// risk data standing in for the real thing. Only the resale-liquidity
// section calls a real backend endpoint today.
function NeighborhoodInsights() {
  const [address, setAddress] = useState("");
  const [city, setCity] = useState("");
  const [propertyType, setPropertyType] = useState("Apartment");
  const [submitted, setSubmitted] = useState(false);
  const [resaleSignal, setResaleSignal] = useState(null);
  const [resaleState, setResaleState] = useState("idle"); // "idle" | "loading" | "done" | "error"
  const [validationError, setValidationError] = useState("");

  const handleShowInsights = async () => {
    if (!address.trim() || !city.trim()) {
      setValidationError("Please enter both a property address/locality and a city to see neighborhood insights.");
      return;
    }
    setValidationError("");
    setSubmitted(true);
    setResaleState("loading");
    try {
      const res = await fetch(`${API_BASE}/api/neighborhood-insights/resale-signal?city=${encodeURIComponent(city)}&property_type=${encodeURIComponent(propertyType)}`);
      const data = await res.json();
      setResaleSignal(data);
      setResaleState("done");
    } catch {
      setResaleState("error");
    }
  };

  const googleMapsUrl = `https://www.google.com/maps/search/${encodeURIComponent(`${address}, ${city}`)}`;
  const shareText = `Check out this neighborhood insights tool before buying a property: https://propertyiqweb.com/neighborhood-insights.html`;

  return (
    <div className="ni-page">
      <div className="ni-top-banner">
        🏠 Ready to buy? <a href="/">Get your free Instant Property Score with PropertyIQ →</a>
      </div>

      <div className="ni-nav">
        <span className="ni-nav-brand">LivingIQ · Neighborhood Insights</span>
        <div className="ni-nav-links">
          <a href="https://livingiqweb.com">← Back to LivingIQ</a>
          <a href="/">PropertyIQ →</a>
        </div>
      </div>

      <div className="ni-hero">
        <h1>Know your neighborhood, before you buy</h1>
        <p>
          See hospitals, schools, markets, banks, and public transport near a property, plus a
          buyer's due-diligence checklist and resale demand signal — all in one place, before you decide.
        </p>
      </div>

      <div className="ni-form-card">
        <div className="ni-form-row">
          <div className="ni-form-field">
            <label>Property address or locality</label>
            <input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="e.g. Banjara Hills, Road No. 12" />
          </div>
          <div className="ni-form-field">
            <label>City</label>
            <input value={city} onChange={(e) => setCity(e.target.value)} placeholder="e.g. Hyderabad" />
          </div>
        </div>
        <div className="ni-form-row">
          <div className="ni-form-field">
            <label>Property type</label>
            <select value={propertyType} onChange={(e) => setPropertyType(e.target.value)}>
              <option>Apartment</option>
              <option>Villa</option>
              <option>Plot</option>
            </select>
          </div>
        </div>
        <button className="ni-primary-btn" onClick={handleShowInsights}>Show neighborhood insights</button>
        {validationError && <p className="ni-validation-error">{validationError}</p>}
      </div>

      {submitted && (
        <>
          <div className="ni-map-card">
            <h3>Your neighborhood</h3>
            <div className="ni-category-chips">
              {CATEGORIES.map((c) => <span key={c} className="ni-chip">{c}</span>)}
            </div>
            <div className="ni-map-placeholder">
              <p>🗺️ Neighborhood map coming soon</p>
              <p className="ni-map-placeholder-sub">This needs a Google Places API connection to show real nearby hospitals, schools, and markets — not shown here until that's set up, rather than guessing.</p>
            </div>
            <a href={googleMapsUrl} target="_blank" rel="noopener noreferrer" className="ni-text-link">Open this location in Google Maps →</a>
          </div>

          <div className="ni-card">
            <h3>☔ Flood & waterlogging risk</h3>
            <p className="ni-coming-soon">Coming soon — this needs a municipal drainage/flood-history data source this app doesn't have connected yet.</p>
          </div>

          <div className="ni-card">
            <h3>🏗️ Upcoming infrastructure</h3>
            <p className="ni-coming-soon">Coming soon — metro lines, highways, and planned commercial development near this address, once a data source is connected.</p>
          </div>

          <div className="ni-card">
            <h3>📈 Resale demand signal</h3>
            {resaleState === "loading" && <p>Checking comparable listings...</p>}
            {resaleState === "error" && <p className="ni-coming-soon">Couldn't load this right now — please try again.</p>}
            {resaleState === "done" && resaleSignal && resaleSignal.has_data && (
              <div className="ni-resale-result">
                <div className="ni-resale-stat">
                  <span className="ni-resale-number">{resaleSignal.comparable_count}</span>
                  <span className="ni-resale-label">comparable {propertyType.toLowerCase()} listing{resaleSignal.comparable_count === 1 ? "" : "s"} tracked in {city}</span>
                </div>
                <div className="ni-resale-stat">
                  <span className="ni-resale-number">₹{resaleSignal.average_price_per_sqft.toLocaleString("en-IN")}</span>
                  <span className="ni-resale-label">average price/sq ft ({resaleSignal.data_source === "live" ? "live market data" : "recent snapshot"})</span>
                </div>
              </div>
            )}
            {resaleState === "done" && resaleSignal && !resaleSignal.has_data && (
              <p className="ni-coming-soon">No comparable listing data for {city} yet — this app currently covers a growing set of cities, not all of them.</p>
            )}
          </div>

          <div className="ni-card">
            <h3>✅ Buyer's due-diligence checklist</h3>
            <ul className="ni-checklist">
              {CHECKLIST_ITEMS.map((item) => <li key={item}>{item}</li>)}
            </ul>
          </div>

          <div className="ni-card">
            <h3>📞 Local authority contacts</h3>
            <ul className="ni-contact-list">
              {AUTHORITY_CONTACTS.map((c) => (
                <li key={c.label}><strong>{c.label}:</strong> {c.detail}</li>
              ))}
            </ul>
          </div>

          <div className="ni-cta-card">
            <h3>📋 PropertyIQ — Instant Property Score</h3>
            <p>Get a full price, location, and red-flag check on this property — free, no signup needed for the first check.</p>
            <ul>
              <li>🤖 AI-powered price and location scoring in seconds</li>
              <li>🚩 Red flags checked against real comparable listings</li>
              <li>📊 Backed by the same data shown in this report</li>
            </ul>
            <a href="/" className="ni-primary-btn ni-cta-btn">Try PropertyIQ →</a>
          </div>

          <div className="ni-share-card">
            <h3>👨‍👩‍👧 Share this neighborhood report</h3>
            <p>Let your family or co-buyer see this before you decide — it takes 10 seconds.</p>
            <div className="ni-share-buttons">
              <a href={`https://wa.me/?text=${encodeURIComponent(shareText)}`} target="_blank" rel="noopener noreferrer" className="ni-share-btn">Share via WhatsApp</a>
              <a href={`sms:?body=${encodeURIComponent(shareText)}`} className="ni-share-btn">Share via SMS</a>
            </div>
          </div>
        </>
      )}

      <div className="ni-footer">
        A free tool by PropertyIQ — Know Before You Buy.
      </div>
    </div>
  );
}

export default NeighborhoodInsights;
