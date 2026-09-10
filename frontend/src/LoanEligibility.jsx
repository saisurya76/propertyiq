import { useState, useEffect } from "react";
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

function LoanEligibility({ currency = "USD" }) {
  const [monthlyIncome, setMonthlyIncome] = useState("100000");
  const [existingObligations, setExistingObligations] = useState("0");
  const [propertyPrice, setPropertyPrice] = useState("9000000");
  const [downPayment, setDownPayment] = useState("2000000");
  const [age, setAge] = useState("35");
  const [creditRating, setCreditRating] = useState("good");
  const [rate, setRate] = useState("8.5");
  const [tenure, setTenure] = useState("20");
  const [result, setResult] = useState(null);
  const [thresholds, setThresholds] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [session, setSession] = useState(() => getSession());
  const [authStep, setAuthStep] = useState(null); // null | "email" | "code" | "paywall"
  const [authEmail, setAuthEmail] = useState("");
  const [authCode, setAuthCode] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState("");
  const [paywallTiers, setPaywallTiers] = useState(null);

  useEffect(() => {
    studioApi.getLoanEligibilitySettings().then(setThresholds).catch(() => {});
  }, []);

  const loadPaywallTiers = () => {
    if (paywallTiers !== null) return;
    Promise.all([
      fetch(`${API_BASE}/api/tiers`).then((r) => r.json()),
      fetch(`${API_BASE}/api/fx-rates`).then((r) => r.json()),
    ])
      .then(([tiers, fxRates]) => {
        const qualifying = Object.entries(tiers)
          .filter(([, tier]) => (tier.features || []).includes("loan_eligibility"))
          .map(([tierId, tier]) => ({ tierId, ...tier }));
        setPaywallTiers({ tiers: qualifying, fxRates });
      })
      .catch(() => setPaywallTiers({ tiers: [], fxRates: {} }));
  };

  const handleCheck = async () => {
    setError("");
    const income = parseFloat(monthlyIncome), obligations = parseFloat(existingObligations) || 0;
    const price = parseFloat(propertyPrice), down = parseFloat(downPayment) || 0;
    const ageNum = parseInt(age, 10), r = parseFloat(rate), t = parseFloat(tenure);
    if (!income || income <= 0 || !price || price <= 0 || !ageNum || ageNum <= 0 || isNaN(r) || r < 0 || !t || t <= 0) {
      setError("Enter a valid monthly income, property price, age, interest rate, and tenure.");
      return;
    }
    setLoading(true);
    try {
      const currentSession = getSession();
      const res = await fetch(`${API_BASE}/api/neighborhood-insights/loan-eligibility`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(currentSession?.token ? { Authorization: `Bearer ${currentSession.token}` } : {}),
        },
        body: JSON.stringify({
          monthly_income: income, existing_monthly_obligations: obligations, property_price: price,
          down_payment_available: down, age: ageNum, credit_rating: creditRating,
          annual_rate_percent: r, tenure_years: t,
        }),
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
        throw new Error(data.detail || "Couldn't check eligibility.");
      }
      setResult(await res.json());
    } catch (err) {
      setError(err.message || "Couldn't check eligibility right now.");
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
      await handleCheck();
    } catch (err) {
      setAuthError(err.message || "That code didn't work. Please try again.");
    } finally {
      setAuthLoading(false);
    }
  };

  return (
    <div className="ni-comparison-section">
      <h3>Loan Eligibility Check <span className="ni-comparison-paid-badge">Studio subscribers</span></h3>
      <p className="ni-comparison-intro">
        A real estimate against standard lending criteria{thresholds ? ` — max ${thresholds.max_foir_percent}% of income on debt, max ${thresholds.max_ltv_percent}% loan-to-value` : ""}.
        Not a bank's actual approval decision. Free to enter numbers below — signing in and an active Studio plan is needed to see the result.
      </p>

      <div className="ni-emi-inputs">
        <label>
          Monthly income
          <input type="number" value={monthlyIncome} onChange={(e) => setMonthlyIncome(e.target.value)} />
        </label>
        <label>
          Existing monthly obligations
          <input type="number" value={existingObligations} onChange={(e) => setExistingObligations(e.target.value)} />
        </label>
        <label>
          Property price
          <input type="number" value={propertyPrice} onChange={(e) => setPropertyPrice(e.target.value)} />
        </label>
        <label>
          Down payment available
          <input type="number" value={downPayment} onChange={(e) => setDownPayment(e.target.value)} />
        </label>
        <label>
          Your age
          <input type="number" value={age} onChange={(e) => setAge(e.target.value)} />
        </label>
        <label>
          Credit rating (self-assessed)
          <select value={creditRating} onChange={(e) => setCreditRating(e.target.value)}>
            <option value="poor">Poor</option>
            <option value="fair">Fair</option>
            <option value="good">Good</option>
            <option value="excellent">Excellent</option>
          </select>
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
      <button type="button" className="ni-primary-btn" onClick={handleCheck} disabled={loading} style={{ marginTop: 12 }}>
        {loading ? "Checking..." : "Check Eligibility"}
      </button>

      {error && <p className="ni-comparison-error">{error}</p>}

      {authStep === "email" && (
        <div className="ni-comparison-auth-box">
          <h4>Sign in to see your result</h4>
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
              {authLoading ? "Verifying..." : "Verify & check"}
            </button>
          </form>
          <span className="ni-comparison-back-link" onClick={() => setAuthStep("email")}>← Use a different email</span>
        </div>
      )}

      {authStep === "paywall" && (
        <div className="ni-comparison-auth-box">
          <h4>Unlock the loan eligibility check{session?.email ? ` for ${session.email}` : ""}</h4>
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
          <div className={`ni-loan-eligibility-verdict ${result.is_eligible ? "ni-loan-eligible" : "ni-loan-ineligible"}`}>
            {result.is_eligible ? "✓ Likely Eligible" : "✗ Likely Not Eligible"}
          </div>
          <div className="ni-loan-eligibility-checks">
            {result.checks.map((check) => (
              <div key={check.name} className="ni-extended-metric-row">
                <span className="ni-extended-metric-label">{check.pass ? "✓" : "✗"} {check.name}</span>
                <span className="ni-extended-metric-value">{check.detail}</span>
              </div>
            ))}
          </div>
          <div className="ni-extended-metric-row">
            <span className="ni-extended-metric-label">Requested loan amount</span>
            <span className="ni-extended-metric-value">{formatCurrency(result.requested_loan_amount, currency)}</span>
          </div>
          <div className="ni-extended-metric-row">
            <span className="ni-extended-metric-label">Estimated EMI</span>
            <span className="ni-extended-metric-value">{formatCurrency(result.proposed_emi, currency)}</span>
          </div>
          <div className="ni-extended-metric-row">
            <span className="ni-extended-metric-label">Max loan you'd likely qualify for</span>
            <span className="ni-extended-metric-value">{formatCurrency(result.max_eligible_loan_amount, currency)}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default LoanEligibility;
