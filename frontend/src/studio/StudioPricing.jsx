import { useEffect, useState } from "react";
import { studioApi, getSession } from "./studioApi";

const TIER_ORDER = ["insight_addon", "studio_starter", "studio_pro", "studio_unlimited"];

function formatQuota(quota) {
  if (quota === null || quota === undefined) return "Unlimited designs/month";
  if (quota === 0) return "One-time report unlock";
  return `${quota} design${quota === 1 ? "" : "s"}/month`;
}

function formatPrice(usdAmount, currency, fxRates) {
  const rate = fxRates?.[currency];
  // Fall back to plain USD if the visitor's currency isn't in our FX
  // table (rare) or rates haven't loaded yet — never show a broken price.
  if (!rate) {
    return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(usdAmount);
  }
  const converted = usdAmount * rate;
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      maximumFractionDigits: converted >= 100 ? 0 : 2,
    }).format(converted);
  } catch {
    // Intl throws on a currency code it doesn't recognize — fall back to USD.
    return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(usdAmount);
  }
}

function StudioPricing({ reportId, currency = "USD", onBack, onLaunchConstructionStudio, onSignOut }) {
  const [tiers, setTiers] = useState(null);
  const [fxRates, setFxRates] = useState(null);
  const [status, setStatus] = useState(null);
  const [loadingTierId, setLoadingTierId] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [insightUnlocked, setInsightUnlocked] = useState(false);

  const session = getSession();

  useEffect(() => {
    studioApi.getTiers().then(setTiers).catch((e) => setError(e.message));
    studioApi.getFxRates().then(setFxRates).catch(() => {}); // silent — formatPrice falls back to USD
    studioApi.getStatus().then(setStatus).catch((e) => {
      if (e.status === 401 && onSignOut) onSignOut();
    });
  }, [onSignOut]);

  const handleSubscribe = async (tierId) => {
    setError("");
    setLoadingTierId(tierId);
    try {
      const result = await studioApi.subscribeCheckout(tierId);
      if (result.checkout_url) {
        // Full-page redirect to Dodo's external hosted checkout — not a
        // React-tracked mutation, so the compiler-oriented immutability
        // check doesn't apply here.
        // eslint-disable-next-line react-hooks/immutability
        window.location.href = result.checkout_url;
        return;
      }
      // Beta bypass path — no redirect, already active
      setMessage(`You're on the ${tiers[tierId]?.label || tierId} plan — no payment required in beta.`);
      const refreshed = await studioApi.getStatus();
      setStatus(refreshed);
    } catch (err) {
      if (err.status === 401 && onSignOut) {
        onSignOut();
        return;
      }
      setError(err.message || "Couldn't start checkout. Please try again.");
    } finally {
      setLoadingTierId(null);
    }
  };

  const handleInsightBuy = async () => {
    if (!reportId) return;
    setError("");
    setLoadingTierId("insight_addon");
    try {
      const result = await studioApi.insightCheckout(reportId);
      if (result.checkout_url) {
        // Full-page redirect to Dodo's external hosted checkout.
        window.location.href = result.checkout_url;
        return;
      }
      setMessage("Similar property insights unlocked for this report.");
      setInsightUnlocked(true);
    } catch (err) {
      if (err.status === 401 && onSignOut) {
        onSignOut();
        return;
      }
      setError(err.message || "Couldn't start checkout. Please try again.");
    } finally {
      setLoadingTierId(null);
    }
  };

  if (!tiers) {
    return <div className="studio-panel"><p className="studio-subtext">Loading plans...</p></div>;
  }

  return (
    <div>
      <div className="studio-pricing-header">
        <h2>PropertyIQ Studio Plans</h2>
        <p>
          Signed in as <strong>{session?.email}</strong>. Pick what fits — unlock insights
          for this one report, or subscribe for ongoing access to Construction Studio.
        </p>
      </div>

      {message && (
        <div className="studio-status-banner">
          <div>{message}</div>
          {insightUnlocked && onBack && (
            <div className="studio-prominent-link" onClick={onBack}>
              ← Go to your report to view it
            </div>
          )}
        </div>
      )}
      {error && <div className="studio-status-banner" style={{ background: "#fef2f2", borderColor: "#fecaca", color: "#991b1b" }}>{error}</div>}

      {status?.tier_id && (
        <div className="studio-status-banner">
          Current plan: <strong>{tiers[status.tier_id]?.label || status.tier_id}</strong>
          {status.design_quota_per_month !== null && status.design_quota_per_month !== undefined && (
            <> — {status.designs_remaining ?? status.design_quota_per_month} design(s) remaining this month</>
          )}
          {onLaunchConstructionStudio && (
            <>
              {" · "}
              <span className="studio-back-link" onClick={onLaunchConstructionStudio}>
                Open Construction Studio →
              </span>
            </>
          )}
        </div>
      )}

      <div className="studio-tier-grid">
        {TIER_ORDER.filter((id) => tiers[id]).map((tierId) => {
          const tier = tiers[tierId];
          const isInsight = tier.billing === "one_time";
          const isCurrent = status?.tier_id === tierId;
          const isFeatured = tierId === "studio_pro";

          return (
            <div key={tierId} className={`studio-tier-card ${isFeatured ? "studio-tier-featured" : ""}`}>
              <div className="studio-tier-name">{tier.label}</div>
              <div className="studio-tier-price">
                {formatPrice(tier.price_usd, currency, fxRates)}
                <span>{isInsight ? " one-time" : "/mo"}</span>
              </div>
              <div className="studio-tier-quota">{formatQuota(tier.design_quota_per_month)}</div>

              <ul className="studio-tier-features">
                {tier.features.map((f) => (
                  <li key={f}>{f.replace(/_/g, " ")}</li>
                ))}
              </ul>

              {isInsight ? (
                <button
                  className="studio-tier-btn"
                  disabled={!reportId || loadingTierId === tierId || insightUnlocked}
                  onClick={handleInsightBuy}
                  title={!reportId ? "View a report first to unlock this for that report" : undefined}
                >
                  {insightUnlocked
                    ? "Unlocked ✓"
                    : loadingTierId === tierId
                    ? "Processing..."
                    : reportId
                    ? "Unlock for this report"
                    : "View a report first"}
                </button>
              ) : (
                <button
                  className="studio-tier-btn"
                  disabled={isCurrent || loadingTierId === tierId}
                  onClick={() => handleSubscribe(tierId)}
                >
                  {isCurrent ? "Current plan" : loadingTierId === tierId ? "Processing..." : "Subscribe"}
                </button>
              )}
            </div>
          );
        })}
      </div>

      <div style={{ textAlign: "center", marginTop: 24 }}>
        <span className="studio-back-link" onClick={onBack}>← Back to report</span>
      </div>
    </div>
  );
}

export default StudioPricing;
