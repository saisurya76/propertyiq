import { useMemo, useState } from "react";
import { studioApi } from "./studioApi";

const TIER_ORDER = ["insight_addon", "studio_starter", "studio_pro", "studio_unlimited"];

function AdminPanel({ onBack }) {
  const [password, setPassword] = useState("");
  const [authed, setAuthed] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const [tierConfig, setTierConfig] = useState(null);
  const [subscriptions, setSubscriptions] = useState([]);
  const [grants, setGrants] = useState([]);
  const [saveMessage, setSaveMessage] = useState("");

  const login = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await studioApi.adminOverview(password);
      setTierConfig(data.tier_config);
      setSubscriptions(data.subscriptions);
      setGrants(data.insight_grants);
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

  if (!authed) {
    return (
      <div className="studio-panel">
        <h2>Admin Access</h2>
        <p className="studio-subtext">Enter the admin password to manage tiers and view activity.</p>
        <form onSubmit={login}>
          {error && <div className="studio-error">{error}</div>}
          <input
            type="password"
            placeholder="Admin password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoFocus
            required
          />
          <button className="studio-cta-btn" type="submit" disabled={loading} style={{ width: "100%" }}>
            {loading ? "Checking..." : "Enter"}
          </button>
        </form>
        <span className="studio-back-link" onClick={onBack}>← Back</span>
      </div>
    );
  }

  return (
    <div className="admin-dashboard">
      <div className="admin-dashboard-header">
        <div>
          <div className="admin-dashboard-eyebrow">PropertyIQ Studio</div>
          <h2>Admin Dashboard</h2>
        </div>
        <span className="admin-refresh-btn" onClick={refresh}>⟳ Refresh</span>
      </div>

      {error && (
        <div className="studio-status-banner" style={{ background: "#fef2f2", borderColor: "#fecaca", color: "#991b1b" }}>
          {error}
        </div>
      )}
      {saveMessage && <div className="studio-status-banner">{saveMessage}</div>}

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

      <div className="admin-section admin-section-purple">
        <h3>Tier Configuration</h3>
        <div className="admin-tier-row admin-tier-row-header">
          <span>Tier</span><span>Price (USD)</span><span>Quota/mo (blank = unlimited, 0 = one-time)</span><span>Label</span><span></span>
        </div>
        {TIER_ORDER.filter((id) => tierConfig?.[id]).map((tierId) => {
          const tier = tierConfig[tierId];
          return (
            <div className="admin-tier-row" key={tierId}>
              <span className="admin-tier-row-name">{tierId}</span>
              <input
                type="number"
                placeholder="Price (USD)"
                value={tier.price_usd}
                onChange={(e) => updateTierField(tierId, "price_usd", Number(e.target.value))}
              />
              <input
                type="number"
                value={tier.design_quota_per_month ?? ""}
                placeholder="unlimited"
                onChange={(e) =>
                  updateTierField(tierId, "design_quota_per_month", e.target.value === "" ? null : Number(e.target.value))
                }
              />
              <input
                type="text"
                placeholder="Label"
                value={tier.label}
                onChange={(e) => updateTierField(tierId, "label", e.target.value)}
              />
              <span />
            </div>
          );
        })}
        <button className="cs-nav-btn cs-nav-primary" style={{ marginTop: 16 }} onClick={saveTiers} disabled={loading}>
          {loading ? "Saving..." : "Save Changes"}
        </button>
      </div>

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

      <span className="studio-back-link" onClick={onBack}>← Back to site</span>
    </div>
  );
}

export default AdminPanel;
