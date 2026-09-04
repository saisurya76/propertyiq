import { useState } from "react";
import { studioApi, getSession, saveSession } from "./studio/studioApi";

const API_BASE = "https://propertyiq-api-q21y.onrender.com";

function formatCurrency(amount, currency) {
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);
  } catch {
    return `${currency} ${Math.round(amount).toLocaleString()}`;
  }
}

function AmortizationProjector({ currency = "USD" }) {
  const [principal, setPrincipal] = useState("5000000");
  const [rate, setRate] = useState("8.5");
  const [tenure, setTenure] = useState("20");
  const [schedule, setSchedule] = useState(null);
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
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
          .filter(([, tier]) => (tier.features || []).includes("amortization_projector"))
          .map(([tierId, tier]) => ({ tierId, ...tier }));
        setPaywallTiers({ tiers: qualifying, fxRates });
      })
      .catch(() => setPaywallTiers({ tiers: [], fxRates: {} }));
  };

  const validInputs = () => {
    const p = parseFloat(principal), r = parseFloat(rate), t = parseFloat(tenure);
    if (!p || p <= 0 || isNaN(r) || r < 0 || !t || t <= 0) return null;
    return { p, r, t };
  };

  const handleGenerate = async () => {
    setError("");
    const nums = validInputs();
    if (!nums) {
      setError("Enter a valid loan amount, interest rate, and tenure.");
      return;
    }
    setLoading(true);
    try {
      const currentSession = getSession();
      const res = await fetch(`${API_BASE}/api/neighborhood-insights/amortization-schedule`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(currentSession?.token ? { Authorization: `Bearer ${currentSession.token}` } : {}),
        },
        body: JSON.stringify({ principal: nums.p, annual_rate_percent: nums.r, tenure_years: nums.t }),
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
        throw new Error(data.detail || "Couldn't build the schedule.");
      }
      const data = await res.json();
      setSchedule(data.schedule);
    } catch (err) {
      setError(err.message || "Couldn't build the schedule right now.");
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async () => {
    const nums = validInputs();
    if (!nums) {
      setError("Enter a valid loan amount, interest rate, and tenure before exporting.");
      return;
    }
    setExporting(true);
    setError("");
    try {
      const currentSession = getSession();
      const params = new URLSearchParams({ principal: nums.p, annual_rate_percent: nums.r, tenure_years: nums.t });
      const res = await fetch(`${API_BASE}/api/neighborhood-insights/amortization-schedule/export?${params.toString()}`, {
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
      if (!res.ok) throw new Error("Couldn't export the schedule.");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "amortization_schedule.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message || "Couldn't export the schedule right now.");
    } finally {
      setExporting(false);
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
      await handleGenerate();
    } catch (err) {
      setAuthError(err.message || "That code didn't work. Please try again.");
    } finally {
      setAuthLoading(false);
    }
  };

  return (
    <div className="ni-comparison-section">
      <h3>Amortization Projector <span className="ni-comparison-paid-badge">Studio subscribers</span></h3>
      <p className="ni-comparison-intro">
        See the full month-by-month breakdown of principal vs. interest over the life of your loan, with a CSV export
        you can open in Excel or Sheets. Free to enter numbers below — signing in and an active Studio plan is needed
        to see the schedule.
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
      <div className="ni-comparison-actions" style={{ marginTop: 12 }}>
        <button type="button" className="ni-primary-btn" onClick={handleGenerate} disabled={loading}>
          {loading ? "Building..." : "Build schedule"}
        </button>
        <button type="button" className="ni-comparison-refresh-btn" onClick={handleExport} disabled={exporting}>
          {exporting ? "Exporting..." : "⬇ Export as CSV"}
        </button>
      </div>

      {error && <p className="ni-comparison-error">{error}</p>}

      {authStep === "email" && (
        <div className="ni-comparison-auth-box">
          <h4>Sign in to see your schedule</h4>
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
          <h4>Unlock the amortization projector{session?.email ? ` for ${session.email}` : ""}</h4>
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

      {schedule && (
        <div className="ni-comparison-table-scroll" style={{ marginTop: 16 }}>
          <table className="ni-comparison-table">
            <thead>
              <tr>
                <th>Month</th>
                <th>Payment</th>
                <th>Principal</th>
                <th>Interest</th>
                <th>Balance</th>
              </tr>
            </thead>
            <tbody>
              {schedule.filter((_, i) => i % 12 === 0 || i === schedule.length - 1).map((row) => (
                <tr key={row.month}>
                  <td>{row.month}</td>
                  <td>{formatCurrency(row.payment, currency)}</td>
                  <td>{formatCurrency(row.principal_component, currency)}</td>
                  <td>{formatCurrency(row.interest_component, currency)}</td>
                  <td>{formatCurrency(row.remaining_balance, currency)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="ni-comparison-honesty-note">
            Showing one row per year for readability — export the CSV above for the full month-by-month schedule.
          </p>
        </div>
      )}
    </div>
  );
}

export default AmortizationProjector;
