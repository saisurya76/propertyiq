import { useState } from "react";
import { studioApi, getSession, saveSession } from "./studio/studioApi";
import { TIER_TAGLINES } from "./studio/tierTaglines";

const API_BASE = "https://propertyiq-api-q21y.onrender.com";
const PERIOD_OPTIONS = [3, 5, 8, 10, 15];

function formatPrice(usdAmount, currency, fxRates) {
  const rate = fxRates?.[currency] || 1;
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 0 }).format(usdAmount * rate);
  } catch {
    return `${currency} ${Math.round(usdAmount * rate).toLocaleString()}`;
  }
}

function LineChart({ points }) {
  const width = 700, height = 260, padding = 40;
  const values = points.map((p) => p.value);
  const minV = Math.min(...values), maxV = Math.max(...values);
  const range = maxV - minV || 1;
  const stepX = (width - padding * 2) / Math.max(points.length - 1, 1);

  const coords = points.map((p, i) => ({
    x: padding + i * stepX,
    y: height - padding - ((p.value - minV) / range) * (height - padding * 2),
  }));
  const path = coords.map((c, i) => `${i === 0 ? "M" : "L"} ${c.x.toFixed(1)} ${c.y.toFixed(1)}`).join(" ");

  const yTicks = [minV, minV + range / 2, maxV];
  const xLabelIndices = [0, Math.floor((points.length - 1) / 2), points.length - 1];

  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: "auto" }}>
      {yTicks.map((v, i) => {
        const y = height - padding - ((v - minV) / range) * (height - padding * 2);
        return (
          <g key={i}>
            <line x1={padding} y1={y} x2={width - padding} y2={y} stroke="#edf0f4" strokeWidth="1" />
            <text x={padding - 8} y={y + 4} fontSize="11" fill="#9ca3af" textAnchor="end">{v.toFixed(0)}</text>
          </g>
        );
      })}
      <path d={path} fill="none" stroke="#059669" strokeWidth="2.5" />
      {coords.map((c, i) => (
        <circle key={i} cx={c.x} cy={c.y} r="2.5" fill="#059669" />
      ))}
      {xLabelIndices.map((i) => (
        <text key={i} x={coords[i].x} y={height - padding + 18} fontSize="11" fill="#9ca3af" textAnchor="middle">
          {points[i].date.slice(0, 7)}
        </text>
      ))}
    </svg>
  );
}

function PriceTrends({ country, currency = "USD" }) {
  const [years, setYears] = useState(8);
  const [trend, setTrend] = useState(null);
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
          .filter(([, tier]) => (tier.features || []).includes("price_trends"))
          .map(([tierId, tier]) => ({ tierId, ...tier }));
        setPaywallTiers({ tiers: qualifying, fxRates });
      })
      .catch(() => setPaywallTiers({ tiers: [], fxRates: {} }));
  };

  const handleLoad = async (requestedYears) => {
    setError("");
    setLoading(true);
    try {
      const currentSession = getSession();
      const res = await fetch(`${API_BASE}/api/neighborhood-insights/price-trends?country=${encodeURIComponent(country)}&years=${requestedYears}`, {
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
      if (!res.ok) throw new Error("Couldn't load price trends.");
      setTrend(await res.json());
    } catch (err) {
      setError(err.message || "Couldn't load price trends right now.");
    } finally {
      setLoading(false);
    }
  };

  const handlePeriodChange = (newYears) => {
    setYears(newYears);
    if (trend?.has_data) handleLoad(newYears); // already unlocked once, refresh silently on period change
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
      await handleLoad(years);
    } catch (err) {
      setAuthError(err.message || "That code didn't work. Please try again.");
    } finally {
      setAuthLoading(false);
    }
  };

  return (
    <div className="ni-comparison-section">
      <h3>Price Trends <span className="ni-comparison-paid-badge">Studio subscribers</span></h3>
      <p className="ni-comparison-intro">
        Real, historical residential property price data — not a static snapshot — from the Bank for International
        Settlements. This is country-level data (the actual metro FRED tracks for {country}), not neighborhood-specific,
        since no real per-area historical price series exists anywhere. Signing in and an active Studio plan is needed to view it.
      </p>

      <div className="ni-comparison-actions">
        {PERIOD_OPTIONS.map((p) => (
          <button
            key={p}
            type="button"
            className={p === years ? "ni-primary-btn" : "ni-comparison-add-btn"}
            onClick={() => handlePeriodChange(p)}
          >
            {p} years
          </button>
        ))}
      </div>
      {!trend && (
        <button type="button" className="ni-primary-btn" onClick={() => handleLoad(years)} disabled={loading} style={{ marginTop: 12 }}>
          {loading ? "Loading..." : "Show price trend"}
        </button>
      )}

      {error && <p className="ni-comparison-error">{error}</p>}

      {authStep === "email" && (
        <div className="ni-comparison-auth-box">
          <h4>Sign in to see the trend</h4>
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
          <h4>Unlock price trends{session?.email ? ` for ${session.email}` : ""}</h4>
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
                    {formatPrice(tier.price_usd, currency, paywallTiers.fxRates)}
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

      {trend && trend.has_data && (
        <div style={{ marginTop: 16 }}>
          <LineChart points={trend.points} />
          <p className="ni-comparison-honesty-note">
            {trend.unit} · Source: {trend.source}
          </p>
        </div>
      )}

      {trend && !trend.has_data && trend.reason === "country_not_covered" && (
        <p className="ni-comparison-error" style={{ marginTop: 16 }}>
          No real historical price index exists for {country} in this data source — shown honestly rather than estimated.
        </p>
      )}
      {trend && !trend.has_data && trend.reason !== "country_not_covered" && (
        <p className="ni-comparison-error" style={{ marginTop: 16 }}>Couldn't load price trend data right now — please try again shortly.</p>
      )}
    </div>
  );
}

export default PriceTrends;
