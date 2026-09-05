import { useState } from "react";
import { studioApi, getSession, saveSession } from "./studio/studioApi";

const API_BASE = "https://propertyiq-api-q21y.onrender.com";

// Real, human-readable labels for the 10 items with no genuine
// per-area data source anywhere (confirmed by hand, not assumed) —
// each gets an honest "Search for this" link rather than a fabricated
// number, same pattern as the comparison feature's own leftover
// metrics.
const UNAVAILABLE_LABELS = {
  fuel: "Fuel",
  tolls: "Tolls",
  domestic_services: "Domestic services",
  maintenance: "Maintenance",
  water: "Water",
  electricity: "Electricity",
  local_lifestyle_cost: "Local lifestyle cost",
  parking: "Parking",
  delivery_service_accessibility: "Delivery / service accessibility",
  commute_cost: "Commute cost",
};

function searchLinkFor(label, locality) {
  return `https://www.google.com/search?q=${encodeURIComponent(`${label} cost ${locality}`)}`;
}

function formatPrice(usdAmount, fxRates) {
  const rate = fxRates?.USD || 1;
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(usdAmount * rate);
}

function CostOfLiving({ lat, lon, locality }) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [session, setSession] = useState(() => getSession());
  const [authStep, setAuthStep] = useState(null);
  const [authEmail, setAuthEmail] = useState("");
  const [authCode, setAuthCode] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState("");
  const [paywallTiers, setPaywallTiers] = useState(null);

  const loadPaywallTiers = () => {
    if (paywallTiers !== null) return;
    Promise.all([
      fetch(`${API_BASE}/api/tiers`).then((r) => r.json()),
      fetch(`${API_BASE}/api/fx-rates`).then((r) => r.json()),
    ])
      .then(([tiers, fxRates]) => {
        const qualifying = Object.entries(tiers)
          .filter(([, tier]) => (tier.features || []).includes("cost_of_living"))
          .map(([tierId, tier]) => ({ tierId, ...tier }));
        setPaywallTiers({ tiers: qualifying, fxRates });
      })
      .catch(() => setPaywallTiers({ tiers: [], fxRates: {} }));
  };

  const handleLoad = async () => {
    setError("");
    setLoading(true);
    try {
      const currentSession = getSession();
      const params = new URLSearchParams();
      if (lat != null) params.set("lat", lat);
      if (lon != null) params.set("lon", lon);
      const res = await fetch(`${API_BASE}/api/neighborhood-insights/cost-of-living?${params.toString()}`, {
        headers: currentSession?.token ? { Authorization: `Bearer ${currentSession.token}` } : {},
      });
      if (res.status === 401) {
        setAuthStep("email");
        return;
      }
      if (res.status === 403) {
        loadPaywallTiers();
        setAuthStep("paywall");
        return;
      }
      if (!res.ok) throw new Error("Couldn't load cost of living data.");
      setResult(await res.json());
    } catch (err) {
      setError(err.message || "Couldn't load cost of living data right now.");
    } finally {
      setLoading(false);
    }
  };

  const submitAuthEmail = async (e) => {
    e.preventDefault();
    if (!authEmail.trim()) return;
    setAuthError("");
    setAuthLoading(true);
    try {
      await studioApi.requestOtp(authEmail.trim());
      setAuthStep("code");
    } catch (err) {
      setAuthError(err.message || "Couldn't send the code. Please try again.");
    } finally {
      setAuthLoading(false);
    }
  };

  const submitAuthCode = async (e) => {
    e.preventDefault();
    if (!authCode.trim()) return;
    setAuthError("");
    setAuthLoading(true);
    try {
      const res = await studioApi.verifyOtp(authEmail.trim(), authCode.trim());
      saveSession(res.session_token, authEmail.trim());
      setSession(getSession());
      setAuthStep(null);
      await handleLoad();
    } catch (err) {
      setAuthError(err.message || "That code didn't work. Please try again.");
    } finally {
      setAuthLoading(false);
    }
  };

  return (
    <div className="ni-comparison-section">
      <h3>True Cost of Living Here <span className="ni-comparison-paid-badge">Studio subscribers</span></h3>
      <p className="ni-comparison-intro">
        Of the 12 real cost-of-living factors that matter for a property decision, only school and hospital access
        have a genuine, verifiable per-area data source — the rest have no free API anywhere, and are shown as
        honest search links rather than invented numbers. Signing in and an active Studio plan is needed to view this.
      </p>

      {!result && (
        <button type="button" className="ni-primary-btn" onClick={handleLoad} disabled={loading}>
          {loading ? "Loading..." : "Show cost of living factors"}
        </button>
      )}

      {error && <p className="ni-comparison-error">{error}</p>}

      {authStep === "email" && (
        <div className="ni-comparison-auth-box">
          <h4>Sign in to see this</h4>
          <p className="ni-comparison-intro">We'll email you a 6-digit code — no password needed.</p>
          <form onSubmit={submitAuthEmail}>
            {authError && <p className="ni-comparison-error">{authError}</p>}
            <input type="email" placeholder="you@example.com" value={authEmail} onChange={(e) => setAuthEmail(e.target.value)} autoFocus required />
            <button type="submit" className="ni-primary-btn" disabled={authLoading} style={{ marginTop: 10 }}>
              {authLoading ? "Sending..." : "Send code"}
            </button>
          </form>
        </div>
      )}

      {authStep === "code" && (
        <div className="ni-comparison-auth-box">
          <h4>Enter your code</h4>
          <p className="ni-comparison-intro">We sent a 6-digit code to <strong>{authEmail}</strong>.</p>
          <form onSubmit={submitAuthCode}>
            {authError && <p className="ni-comparison-error">{authError}</p>}
            <input type="text" inputMode="numeric" placeholder="123456" value={authCode} onChange={(e) => setAuthCode(e.target.value)} autoFocus required />
            <button type="submit" className="ni-primary-btn" disabled={authLoading} style={{ marginTop: 10 }}>
              {authLoading ? "Verifying..." : "Verify & continue"}
            </button>
          </form>
          <span className="ni-comparison-back-link" onClick={() => setAuthStep("email")}>← Use a different email</span>
        </div>
      )}

      {authStep === "paywall" && (
        <div className="ni-comparison-auth-box">
          <h4>Unlock cost of living{session?.email ? ` for ${session.email}` : ""}</h4>
          <p className="ni-comparison-intro">This is a Studio subscriber feature. Here's what you'd get with each plan that includes it:</p>
          {!paywallTiers && <p className="ni-comparison-intro">Loading plans...</p>}
          {paywallTiers && paywallTiers.tiers.length === 0 && (
            <p className="ni-comparison-intro">No current plan includes this yet — check back soon, or contact support.</p>
          )}
          {paywallTiers && paywallTiers.tiers.length > 0 && (
            <div className="ni-comparison-tier-cards">
              {paywallTiers.tiers.map((tier) => (
                <div key={tier.tierId} className="ni-comparison-tier-card">
                  <h5>{tier.label}</h5>
                  <div className="ni-comparison-tier-price">
                    {formatPrice(tier.price_usd, paywallTiers.fxRates)}
                    <span className="ni-comparison-tier-price-period">/mo</span>
                  </div>
                </div>
              ))}
            </div>
          )}
          <a href="https://app.propertyiqweb.com/?view=pricing" target="_blank" rel="noopener noreferrer" className="ni-primary-btn" style={{ display: "inline-block", textDecoration: "none", marginTop: 14 }}>
            View Studio plans →
          </a>
        </div>
      )}

      {result && (
        <div className="ni-extended-metrics" style={{ marginTop: 16 }}>
          <div className="ni-extended-metric-row">
            <span className="ni-extended-metric-label">School access <span className="ni-comparison-metric-label">(within 2km)</span></span>
            <span className="ni-extended-metric-value">
              {result.school_access.has_data ? `${result.school_access.count_within_2km} school(s) nearby` : "Not available"}
            </span>
          </div>
          <div className="ni-extended-metric-row">
            <span className="ni-extended-metric-label">Hospital access <span className="ni-comparison-metric-label">(within 2km)</span></span>
            <span className="ni-extended-metric-value">
              {result.hospital_access.has_data ? `${result.hospital_access.count_within_2km} hospital(s) nearby` : "Not available"}
            </span>
          </div>
          {result.unavailable_items.map((key) => (
            <div className="ni-extended-metric-row" key={key}>
              <span className="ni-extended-metric-label">{UNAVAILABLE_LABELS[key] || key}</span>
              <a className="ni-comparison-search-link" href={searchLinkFor(UNAVAILABLE_LABELS[key] || key, locality || "")} target="_blank" rel="noopener noreferrer">
                Search for this ↗
              </a>
            </div>
          ))}
          <p className="ni-comparison-honesty-note">
            Rows with a "Search for this" link have no structured, per-area data source anywhere — rather than guess a
            number, it opens a real search so you can look into it yourself.
          </p>
        </div>
      )}
    </div>
  );
}

export default CostOfLiving;
