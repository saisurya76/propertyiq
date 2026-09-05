import { useState } from "react";
import { studioApi, getSession, saveSession } from "./studio/studioApi";
import { TIER_TAGLINES } from "./studio/tierTaglines";

const API_BASE = "https://propertyiq-api-q21y.onrender.com";

function formatCurrency(amount, currency) {
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);
  } catch {
    return `${currency} ${Math.round(amount).toLocaleString()}`;
  }
}

function EmiCalculator({ currency = "USD" }) {
  const [principal, setPrincipal] = useState("5000000");
  const [rate, setRate] = useState("8.5");
  const [tenure, setTenure] = useState("20");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [session, setSession] = useState(() => getSession());
  const [authStep, setAuthStep] = useState(null); // null | "email" | "code" | "paywall"
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
          .filter(([, tier]) => (tier.features || []).includes("emi_calculator"))
          .map(([tierId, tier]) => ({ tierId, ...tier }));
        setPaywallTiers({ tiers: qualifying, fxRates });
      })
      .catch(() => setPaywallTiers({ tiers: [], fxRates: {} }));
  };

  const handleCalculate = async () => {
    setError("");
    const p = parseFloat(principal), r = parseFloat(rate), t = parseFloat(tenure);
    if (!p || p <= 0 || isNaN(r) || r < 0 || !t || t <= 0) {
      setError("Enter a valid loan amount, interest rate, and tenure.");
      return;
    }
    setLoading(true);
    try {
      const currentSession = getSession();
      const res = await fetch(`${API_BASE}/api/neighborhood-insights/emi-calculator`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(currentSession?.token ? { Authorization: `Bearer ${currentSession.token}` } : {}),
        },
        body: JSON.stringify({ principal: p, annual_rate_percent: r, tenure_years: t }),
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
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "Couldn't calculate the EMI.");
      }
      setResult(await res.json());
    } catch (err) {
      setError(err.message || "Couldn't calculate the EMI right now.");
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
      await handleCalculate();
    } catch (err) {
      setAuthError(err.message || "That code didn't work. Please try again.");
    } finally {
      setAuthLoading(false);
    }
  };

  return (
    <div className="ni-comparison-section">
      <h3>EMI Calculator <span className="ni-comparison-paid-badge">Studio subscribers</span></h3>
      <p className="ni-comparison-intro">
        Estimate your monthly loan payment for a property purchase. Free to enter numbers below —
        signing in and an active Studio plan is needed to see the result.
      </p>

      <div className="ni-emi-inputs">
        <label>
          Loan amount
          <input type="number" value={principal} onChange={(e) => setPrincipal(e.target.value)} />
        </label>
        <label>
          Interest rate (% per year)
          <input type="number" step="0.01" value={rate} onChange={(e) => setRate(e.target.value)} />
        </label>
        <label>
          Tenure (years)
          <input type="number" value={tenure} onChange={(e) => setTenure(e.target.value)} />
        </label>
      </div>
      <button type="button" className="ni-primary-btn" onClick={handleCalculate} disabled={loading} style={{ marginTop: 12 }}>
        {loading ? "Calculating..." : "Calculate EMI"}
      </button>

      {error && <p className="ni-comparison-error">{error}</p>}

      {authStep === "email" && (
        <div className="ni-comparison-auth-box">
          <h4>Sign in to see your EMI</h4>
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
              {authLoading ? "Verifying..." : "Verify & calculate"}
            </button>
          </form>
          <span className="ni-comparison-back-link" onClick={() => setAuthStep("email")}>← Use a different email</span>
        </div>
      )}

      {authStep === "paywall" && (
        <div className="ni-comparison-auth-box">
          <h4>Unlock the EMI calculator{session?.email ? ` for ${session.email}` : ""}</h4>
          <p className="ni-comparison-intro">This is a Studio subscriber feature. Here's what you'd get with each plan that includes it:</p>
          {!paywallTiers && <p className="ni-comparison-intro">Loading plans...</p>}
          {paywallTiers && paywallTiers.tiers.length === 0 && (
            <p className="ni-comparison-intro">No current plan includes this yet — check back soon, or contact support.</p>
          )}
          {paywallTiers && paywallTiers.tiers.length > 0 && (
            <div className="ni-comparison-tier-cards">
              {paywallTiers.tiers.map((tier) => (
                <div key={tier.tierId} className="ni-comparison-tier-card">
                  <h5 className="tier-name-tooltip" data-tooltip={TIER_TAGLINES[tier.tierId] || ""} tabIndex={0}>{tier.label}</h5>
                  <div className="ni-comparison-tier-price">
                    {formatCurrency(tier.price_usd * (paywallTiers.fxRates?.[currency] || 1), currency)}
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
        <div className="ni-emi-result">
          <div className="ni-emi-result-headline">{formatCurrency(result.emi, currency)} <span className="ni-comparison-metric-label">per month</span></div>
          <div className="ni-extended-metric-row">
            <span className="ni-extended-metric-label">Total interest over {result.total_months} months</span>
            <span className="ni-extended-metric-value">{formatCurrency(result.total_interest, currency)}</span>
          </div>
          <div className="ni-extended-metric-row">
            <span className="ni-extended-metric-label">Total amount paid</span>
            <span className="ni-extended-metric-value">{formatCurrency(result.total_paid, currency)}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default EmiCalculator;
