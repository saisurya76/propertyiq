import { Fragment, useMemo, useState } from "react";
import { studioApi } from "./studioApi";

const TIER_ORDER = ["insight_addon", "studio_starter", "studio_pro", "studio_unlimited"];

// The menu items shown on the admin landing screen, matching
// AccidentIQ's own real admin-dashboard.html pattern exactly: a
// label, a short description, and a `screen` key the tile navigates
// to on click — clean segregation into sections, each reached by
// clicking its own tile, rather than one long page with everything
// visible at once.
const MENU_ITEMS = [
  { screen: "overview", label: "Overview & Analytics", desc: "Subscription counts, insight purchases, and estimated revenue." },
  { screen: "tiers", label: "Tier Configuration", desc: "Prices, quotas, and which features each tier includes." },
  { screen: "gemini", label: "Property URL Import — Gemini API Key", desc: "The LLM fallback key used when free structured-data extraction isn't enough." },
  { screen: "neighborhood", label: "Neighborhood Insights — Page Sections", desc: "Show or hide any section of the public Neighborhood Insights page." },
  { screen: "subscriptions", label: "Active Subscriptions", desc: "Browse current subscription records and their status." },
  { screen: "grants", label: "Insight Add-on Grants", desc: "Every Insight Add-on purchase and who it was granted to." },
];

function AdminPanel({ onBack }) {
  const [password, setPassword] = useState("");
  const [authed, setAuthed] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [screen, setScreen] = useState("menu");

  const [tierConfig, setTierConfig] = useState(null);
  const [subscriptions, setSubscriptions] = useState([]);
  const [grants, setGrants] = useState([]);
  const [saveMessage, setSaveMessage] = useState("");
  const [allFeatures, setAllFeatures] = useState([]);
  const [geminiKeyConfigured, setGeminiKeyConfigured] = useState(false);
  const [geminiKeyInput, setGeminiKeyInput] = useState("");
  const [geminiSaveMessage, setGeminiSaveMessage] = useState("");
  const [niSectionVisibility, setNiSectionVisibility] = useState(null);
  const [niVisibilitySaveMessage, setNiVisibilitySaveMessage] = useState("");

  const login = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await studioApi.adminOverview(password);
      setTierConfig(data.tier_config);
      setSubscriptions(data.subscriptions);
      setGrants(data.insight_grants);
      setAllFeatures(data.all_features || []);
      setGeminiKeyConfigured(!!data.gemini_api_key_configured);
      setNiSectionVisibility(data.ni_section_visibility || null);
      setAuthed(true);
    } catch (err) {
      setError(err.message || "Incorrect password.");
    } finally {
      setLoading(false);
    }
  };

  const updateTierField = (tierId, field, value) => {
    setTierConfig((cfg) => ({
      ...cfg,
      [tierId]: { ...cfg[tierId], [field]: value },
    }));
  };

  // Toggling here only changes in-memory state — nothing takes effect
  // system-wide until "Save Changes" below actually persists it via
  // adminUpdateTiers, same as every other tier field on this page.
  const toggleTierFeature = (tierId, feature) => {
    setTierConfig((cfg) => {
      const current = cfg[tierId].features || [];
      const next = current.includes(feature)
        ? current.filter((f) => f !== feature)
        : [...current, feature];
      return { ...cfg, [tierId]: { ...cfg[tierId], features: next } };
    });
  };

  // A real, explicit admin control: removes a feature from every tier
  // at once, matching what the report page checks to decide whether to
  // show the feature at all — "hiding" a feature IS unchecking it
  // everywhere, not a separate flag, so the per-tier checkboxes below
  // correctly show as unchecked immediately, with no separate state to
  // keep in sync. Same in-memory-until-saved convention as every other
  // field here.
  const hideFeatureEverywhere = (feature) => {
    setTierConfig((cfg) => {
      const next = { ...cfg };
      for (const tierId of Object.keys(next)) {
        next[tierId] = {
          ...next[tierId],
          features: (next[tierId].features || []).filter((f) => f !== feature),
        };
      }
      return next;
    });
  };

  const saveTiers = async () => {
    setSaveMessage("");
    setError("");
    setLoading(true);
    try {
      await studioApi.adminUpdateTiers(password, tierConfig);
      setSaveMessage("Tier config saved.");
    } catch (err) {
      setError(err.message || "Couldn't save changes.");
    } finally {
      setLoading(false);
    }
  };

  // Backs the property_url_import feature's LLM fallback (used only
  // when the free structured-data extraction path doesn't find enough)
  // — a real, explicit request: making this key admin-configurable at
  // runtime rather than only an env var, so it can be changed without a
  // redeploy. The backend never returns the actual key value back, even
  // here — only whether one is currently configured.
  const saveGeminiKey = async () => {
    setGeminiSaveMessage("");
    setError("");
    if (!geminiKeyInput.trim()) return;
    setLoading(true);
    try {
      const res = await studioApi.adminUpdateSettings(password, geminiKeyInput.trim());
      setGeminiKeyConfigured(!!res.gemini_api_key_configured);
      setGeminiKeyInput("");
      setGeminiSaveMessage("Gemini API key saved.");
    } catch (err) {
      setError(err.message || "Couldn't save the Gemini API key.");
    } finally {
      setLoading(false);
    }
  };

  // Toggling here only changes in-memory state — nothing takes effect
  // on the live page until "Save" below actually persists it, same
  // pattern as every other admin setting on this page.
  const toggleNiSection = (section) => {
    setNiSectionVisibility((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  const saveNiSectionVisibility = async () => {
    setNiVisibilitySaveMessage("");
    setError("");
    setLoading(true);
    try {
      const res = await studioApi.adminUpdateSettings(password, undefined, niSectionVisibility);
      setNiSectionVisibility(res.ni_section_visibility || niSectionVisibility);
      setNiVisibilitySaveMessage("Section visibility saved.");
    } catch (err) {
      setError(err.message || "Couldn't save section visibility.");
    } finally {
      setLoading(false);
    }
  };

  const refresh = async () => {
    try {
      const data = await studioApi.adminOverview(password);
      setTierConfig(data.tier_config);
      setSubscriptions(data.subscriptions);
      setGrants(data.insight_grants);
    } catch (err) {
      setError(err.message || "Couldn't refresh.");
    }
  };

  const activeSubCount = useMemo(
    () => subscriptions.filter((s) => s.status === "active").length,
    [subscriptions]
  );

  // Estimated revenue analytics — computed from configured list prices ×
  // real counts, same as AccidentIQ's admin analytics. This is NOT pulled
  // from live Dodo transaction data (no such integration exists), so it's
  // an estimate: it won't reflect discounts, refunds, or mid-cycle changes.
  const revenueAnalytics = useMemo(() => {
    if (!tierConfig) return null;

    const subscriptionTiers = TIER_ORDER.filter(
      (id) => tierConfig[id] && tierConfig[id].billing === "subscription"
    ).map((tierId) => {
      const activeCount = subscriptions.filter((s) => s.status === "active" && s.tier_id === tierId).length;
      const priceUsd = tierConfig[tierId].price_usd;
      return {
        tierId,
        label: tierConfig[tierId].label,
        activeCount,
        priceUsd,
        subtotalUsd: activeCount * priceUsd,
      };
    });

    const estimatedMrrUsd = subscriptionTiers.reduce((sum, t) => sum + t.subtotalUsd, 0);
    const insightPriceUsd = tierConfig.insight_addon?.price_usd || 0;
    const insightRevenueUsd = grants.length * insightPriceUsd;

    return { subscriptionTiers, estimatedMrrUsd, insightRevenueUsd, insightPriceUsd };
  }, [tierConfig, subscriptions, grants]);

  if (!authed) {
    return (
      <div className="admin-login-wrap">
        <div className="admin-login-card">
          <h2>Admin Access</h2>
          <p className="admin-login-subtitle">Enter the admin password to manage tiers and view activity.</p>
          <form onSubmit={login}>
            {error && <div className="admin-login-error">{error}</div>}
            <input
              type="password"
              placeholder="Admin password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoFocus
              required
            />
            <button className="admin-login-btn" type="submit" disabled={loading}>
              {loading ? "Checking..." : "Enter"}
            </button>
          </form>
          <span className="admin-login-back" onClick={onBack}>← Back</span>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-dashboard">
      <div className="admin-dashboard-header">
        <div>
          <div className="admin-dashboard-eyebrow">PropertyIQ Studio</div>
          <h2>{screen === "menu" ? "Admin Dashboard" : MENU_ITEMS.find((i) => i.screen === screen)?.label}</h2>
        </div>
        <span className="admin-refresh-btn" onClick={refresh}>⟳ Refresh</span>
      </div>

      {error && (
        <div className="studio-status-banner" style={{ background: "#fef2f2", borderColor: "#fecaca", color: "#991b1b" }}>
          {error}
        </div>
      )}
      {saveMessage && <div className="studio-status-banner">{saveMessage}</div>}

      {screen === "menu" && (
        <>
          <p className="admin-menu-subtitle">Choose a section.</p>
          <div className="admin-menu-grid">
            {MENU_ITEMS.map((item) => (
              <div key={item.screen} className="menu-tile" onClick={() => setScreen(item.screen)}>
                <div className="menu-tile-label">{item.label}</div>
                <div className="menu-tile-desc">{item.desc}</div>
              </div>
            ))}
          </div>
        </>
      )}

      {screen === "overview" && (
        <>
          <button type="button" className="admin-subscreen-back" onClick={() => setScreen("menu")}>← Back to menu</button>

          <div className="admin-stats-row">
            <div className="admin-stat-card admin-stat-purple">
              <div className="admin-stat-value">{activeSubCount}</div>
              <div className="admin-stat-label">Active Subscriptions</div>
            </div>
            <div className="admin-stat-card admin-stat-blue">
              <div className="admin-stat-value">{subscriptions.length}</div>
              <div className="admin-stat-label">Total Subscription Records</div>
            </div>
            <div className="admin-stat-card admin-stat-green">
              <div className="admin-stat-value">{grants.length}</div>
              <div className="admin-stat-label">Insight Add-on Purchases</div>
            </div>
            <div className="admin-stat-card admin-stat-slate">
              <div className="admin-stat-value">{TIER_ORDER.filter((id) => tierConfig?.[id]).length}</div>
              <div className="admin-stat-label">Configured Tiers</div>
            </div>
          </div>

          {revenueAnalytics && (
            <div className="admin-section admin-section-amber">
              <h3>Revenue Analytics</h3>
              <p className="admin-empty-note" style={{ marginTop: -6, marginBottom: 16 }}>
                Estimated from configured list prices × real counts — not live Dodo transaction
                data, so this won't reflect discounts, refunds, or mid-cycle plan changes.
              </p>

              <div className="admin-stats-row" style={{ marginBottom: 20 }}>
                <div className="admin-stat-card admin-stat-purple">
                  <div className="admin-stat-value">${revenueAnalytics.estimatedMrrUsd.toLocaleString()}</div>
                  <div className="admin-stat-label">Estimated MRR (subscriptions)</div>
                </div>
                <div className="admin-stat-card admin-stat-green">
                  <div className="admin-stat-value">${revenueAnalytics.insightRevenueUsd.toLocaleString()}</div>
                  <div className="admin-stat-label">Insight Add-on Revenue (one-time, all-time)</div>
                </div>
              </div>

              <div className="admin-table-scroll">
                <table className="admin-table">
                  <thead>
                    <tr><th>Tier</th><th>Active Subscribers</th><th>Price (USD/mo)</th><th>Subtotal (USD/mo)</th></tr>
                  </thead>
                  <tbody>
                    {revenueAnalytics.subscriptionTiers.map((t) => (
                      <tr key={t.tierId}>
                        <td>{t.label}</td>
                        <td>{t.activeCount}</td>
                        <td>${t.priceUsd}</td>
                        <td>${t.subtotalUsd.toLocaleString()}</td>
                      </tr>
                    ))}
                    <tr>
                      <td><strong>Insight Add-on</strong></td>
                      <td>{grants.length} purchase{grants.length === 1 ? "" : "s"}</td>
                      <td>${revenueAnalytics.insightPriceUsd}</td>
                      <td>${revenueAnalytics.insightRevenueUsd.toLocaleString()}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {screen === "tiers" && (
        <>
          <button type="button" className="admin-subscreen-back" onClick={() => setScreen("menu")}>← Back to menu</button>

          <div className="admin-section admin-section-purple">
            <h3>Tier Configuration</h3>
            <div className="admin-tier-row admin-tier-row-header">
              <span>Tier</span><span>Price (from Dodo)</span><span>Generate/mo (blank = unlimited, 0 = one-time)</span><span>Saved designs (blank = unlimited)</span><span>Max price watches (blank = unlimited)</span><span>Label</span>
            </div>
            <p className="admin-section-note" style={{ marginTop: -8 }}>
              Price is read directly from Dodo Payments — the real, actual amount a customer is
              charged — and can't be edited here. Change it in the Dodo dashboard instead; editing a
              locally-stored number here could never actually change what anyone pays, since checkout
              only ever sends Dodo a product ID, not a price.
            </p>
            {TIER_ORDER.filter((id) => tierConfig?.[id]).map((tierId) => {
              const tier = tierConfig[tierId];
              return (
                <Fragment key={tierId}>
                  <div className="admin-tier-row">
                    <span className="admin-tier-row-name">{tierId}</span>
                    <span title={tier.price_source === "dodo" ? "Live value from Dodo Payments" : "Dodo price unavailable right now — showing the last known/local fallback value"}>
                      <input
                        type="text"
                        disabled
                        value={`$${tier.price_usd}${tier.price_source === "dodo" ? "" : " (fallback)"}`}
                      />
                    </span>
                    <input
                      type="number"
                      value={tier.design_quota_per_month ?? ""}
                      placeholder="unlimited"
                      onChange={(e) =>
                        updateTierField(tierId, "design_quota_per_month", e.target.value === "" ? null : Number(e.target.value))
                      }
                    />
                    <input
                      type="number"
                      value={tier.saved_designs_limit ?? ""}
                      placeholder="unlimited"
                      onChange={(e) =>
                        updateTierField(tierId, "saved_designs_limit", e.target.value === "" ? null : Number(e.target.value))
                      }
                    />
                    <input
                      type="number"
                      value={tier.max_price_watches ?? ""}
                      placeholder="unlimited watches"
                      title="Max active Price Drop Alert watches this tier can have at once — leave blank for unlimited"
                      onChange={(e) =>
                        updateTierField(tierId, "max_price_watches", e.target.value === "" ? null : Number(e.target.value))
                      }
                    />
                    <input
                      type="text"
                      placeholder="Label"
                      value={tier.label}
                      onChange={(e) => updateTierField(tierId, "label", e.target.value)}
                    />
                  </div>
                  <div className="admin-tier-features-row">
                    <span className="admin-tier-features-label">Features:</span>
                    {allFeatures.map((feature) => (
                      <label key={feature} className="admin-feature-checkbox" title={`Toggle ${feature} for this tier — takes effect immediately everywhere once saved`}>
                        <input
                          type="checkbox"
                          checked={(tier.features || []).includes(feature)}
                          onChange={() => toggleTierFeature(tierId, feature)}
                        />
                        {feature}
                      </label>
                    ))}
                  </div>
                  {tierId === "insight_addon" && (
                    <div className="admin-tier-features-row" title="Free: similar-property suggestions are available to everyone, no purchase — the buy button disappears. Paid: the current behavior — a purchase or active subscription is required, and the panel stays hidden until unlocked.">
                      <span className="admin-tier-features-label">Mode:</span>
                      <label className="admin-feature-checkbox">
                        <input
                          type="radio"
                          name="insight-addon-mode"
                          checked={(tier.mode ?? "paid") === "paid"}
                          onChange={() => updateTierField(tierId, "mode", "paid")}
                        />
                        Paid (default — requires purchase or subscription)
                      </label>
                      <label className="admin-feature-checkbox">
                        <input
                          type="radio"
                          name="insight-addon-mode"
                          checked={tier.mode === "free"}
                          onChange={() => updateTierField(tierId, "mode", "free")}
                        />
                        Free (available to everyone, no purchase)
                      </label>
                    </div>
                  )}
                </Fragment>
              );
            })}
            <div className="admin-tier-features-row" style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--grey-200, #d6e4ec)" }}>
              <span className="admin-tier-features-label">Hide from main page (all tiers):</span>
              {allFeatures.map((feature) => (
                <button
                  key={feature}
                  type="button"
                  className="admin-feature-hide-btn"
                  title={`Removes ${feature} from every tier at once, hiding it from the main page entirely — same as unchecking it above on each tier, just in one click. Requires Save Changes below to take effect.`}
                  onClick={() => hideFeatureEverywhere(feature)}
                >
                  Hide {feature}
                </button>
              ))}
            </div>
            <button className="cs-nav-btn cs-nav-primary" style={{ marginTop: 16 }} onClick={saveTiers} disabled={loading}>
              {loading ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </>
      )}

      {screen === "gemini" && (
        <>
          <button type="button" className="admin-subscreen-back" onClick={() => setScreen("menu")}>← Back to menu</button>

          <div className="admin-section admin-section-purple">
            <h3>Property URL Import — Gemini API Key</h3>
            <p className="admin-section-note">
              Used only as a fallback when the free structured-data extraction path (schema.org / Open Graph
              metadata already on the page) doesn't find enough — many imports cost nothing at all beyond this.
              Status: <strong>{geminiKeyConfigured ? "Configured" : "Not set"}</strong> (the key itself is never
              shown back once saved, for security).
            </p>
            <div className="admin-tier-row" style={{ gridTemplateColumns: "1fr auto" }}>
              <input
                type="password"
                placeholder={geminiKeyConfigured ? "Enter a new key to replace the current one" : "Enter your Gemini API key"}
                value={geminiKeyInput}
                onChange={(e) => setGeminiKeyInput(e.target.value)}
              />
              <button className="cs-nav-btn cs-nav-primary" onClick={saveGeminiKey} disabled={loading || !geminiKeyInput.trim()}>
                {loading ? "Saving..." : "Save Key"}
              </button>
            </div>
            {geminiSaveMessage && <div className="studio-status-banner">{geminiSaveMessage}</div>}
          </div>
        </>
      )}

      {screen === "neighborhood" && (
        <>
          <button type="button" className="admin-subscreen-back" onClick={() => setScreen("menu")}>← Back to menu</button>

          <div className="admin-section">
            <h3>Neighborhood Insights — Page Sections</h3>
            <p className="admin-section-note">
              Show or hide any section of the public Neighborhood Insights page without a code change or
              redeploy — useful for temporarily hiding a section (e.g. Infrastructure) while sorting out an
              issue with it, without taking the whole page down.
            </p>
            {niSectionVisibility ? (
              <>
                {[
                  { key: "map", label: "Neighborhood map (nearby places)" },
                  { key: "flood_risk", label: "Flood & waterlogging risk" },
                  { key: "infrastructure", label: "Upcoming infrastructure" },
                  { key: "resale_signal", label: "Resale demand signal" },
                  { key: "checklist", label: "Buyer's due-diligence checklist" },
                  { key: "authority_contacts", label: "Local authority contacts" },
                  { key: "cross_sell", label: "PropertyIQ cross-sell card" },
                  { key: "share", label: "Share this report" },
                ].map(({ key, label }) => (
                  <div key={key} className="admin-toggle-row">
                    <label htmlFor={`ni-toggle-${key}`}>{label}</label>
                    <span className="admin-switch">
                      <input
                        id={`ni-toggle-${key}`}
                        type="checkbox"
                        checked={!!niSectionVisibility[key]}
                        onChange={() => toggleNiSection(key)}
                      />
                      <span className="admin-slider"></span>
                    </span>
                  </div>
                ))}
                <button className="cs-nav-btn cs-nav-primary" style={{ marginTop: 16 }} onClick={saveNiSectionVisibility} disabled={loading}>
                  {loading ? "Saving..." : "Save"}
                </button>
                {niVisibilitySaveMessage && <div className="studio-status-banner">{niVisibilitySaveMessage}</div>}
              </>
            ) : (
              <p className="admin-empty-note">Loading...</p>
            )}
          </div>
        </>
      )}

      {screen === "subscriptions" && (
        <>
          <button type="button" className="admin-subscreen-back" onClick={() => setScreen("menu")}>← Back to menu</button>

          <div className="admin-section admin-section-blue">
            <h3>Active Subscriptions ({subscriptions.length})</h3>
            {subscriptions.length === 0 ? (
              <p className="admin-empty-note">No subscriptions yet.</p>
            ) : (
              <div className="admin-table-scroll">
                <table className="admin-table">
                  <thead>
                    <tr><th>Email</th><th>Tier</th><th>Status</th><th>Updated</th></tr>
                  </thead>
                  <tbody>
                    {subscriptions.map((s) => (
                      <tr key={s.email}>
                        <td>{s.email}</td>
                        <td>{s.tier_id}</td>
                        <td>
                          <span className={`admin-status-badge ${s.status === "active" ? "admin-status-active" : "admin-status-other"}`}>
                            {s.status}
                          </span>
                        </td>
                        <td>{new Date(s.updated_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {screen === "grants" && (
        <>
          <button type="button" className="admin-subscreen-back" onClick={() => setScreen("menu")}>← Back to menu</button>

          <div className="admin-section admin-section-green">
            <h3>Insight Add-on Grants ({grants.length})</h3>
            {grants.length === 0 ? (
              <p className="admin-empty-note">No Insight purchases yet.</p>
            ) : (
              <div className="admin-table-scroll">
                <table className="admin-table">
                  <thead>
                    <tr><th>Report ID</th><th>Email</th><th>Granted</th></tr>
                  </thead>
                  <tbody>
                    {grants.map((g, i) => (
                      <tr key={i}>
                        <td>{g.report_id}</td>
                        <td>{g.user_email}</td>
                        <td>{new Date(g.granted_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      <span className="studio-back-link" onClick={onBack}>← Back to site</span>
    </div>
  );
}

export default AdminPanel;
