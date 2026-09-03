import { useEffect, useState } from "react";
import { studioApi } from "./studioApi";

function ProfilePanel({ onClose, onUpgrade, onSignedOut }) {
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [actionMessage, setActionMessage] = useState("");
  const [cancelReason, setCancelReason] = useState("");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleteConfirmEmail, setDeleteConfirmEmail] = useState("");
  const [deleteReason, setDeleteReason] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    studioApi.getProfile()
      .then(setProfile)
      .catch((err) => setError(err.message || "Couldn't load your profile."))
      .finally(() => setLoading(false));
  }, []);

  const handleCancelSubscription = async () => {
    if (!window.confirm("Cancel your subscription? You'll keep access until the end of your current billing period, then it won't renew.")) return;
    setBusy(true);
    setActionMessage("");
    setError("");
    try {
      await studioApi.cancelSubscription(cancelReason.trim() || undefined);
      setActionMessage("Your subscription is set to cancel at the end of this billing period.");
      const refreshed = await studioApi.getProfile();
      setProfile(refreshed);
    } catch (err) {
      setError(err.message || "Couldn't cancel your subscription.");
    } finally {
      setBusy(false);
    }
  };

  const handleDeleteAccount = async () => {
    setError("");
    if (deleteConfirmEmail.trim().toLowerCase() !== profile.email.toLowerCase()) {
      setError("The email you typed doesn't match your account email.");
      return;
    }
    if (!window.confirm("This permanently deletes your account and saved designs. This cannot be undone. Continue?")) return;
    setBusy(true);
    try {
      await studioApi.deleteAccount(deleteConfirmEmail.trim(), deleteReason.trim() || undefined);
      if (onSignedOut) onSignedOut();
    } catch (err) {
      setError(err.message || "Couldn't delete your account.");
      setBusy(false);
    }
  };

  return (
    <div className="refund-request-overlay" role="dialog" aria-modal="true" aria-label="Your profile">
      <div className="refund-request-card" style={{ maxWidth: 560 }}>
        <h3>Your Account</h3>

        {loading && <p className="refund-request-intro">Loading...</p>}
        {error && <div className="refund-request-error">{error}</div>}
        {actionMessage && <div className="terms-gate-body" style={{ background: "#ecfdf5", padding: 10, borderRadius: 8 }}>{actionMessage}</div>}

        {profile && (
          <>
            <p className="refund-request-intro"><strong>{profile.email}</strong></p>

            {/* 1. Tier details */}
            <h4 style={{ marginBottom: 4 }}>Plan</h4>
            <p className="refund-request-intro">
              {profile.tier.tier_id
                ? `${profile.tier.label} — $${profile.tier.price_usd}/mo (${profile.tier.status})`
                : "No active plan."}
            </p>

            {/* 2. Remaining designs */}
            <h4 style={{ marginBottom: 4 }}>Designs</h4>
            <p className="refund-request-intro">
              {profile.quota.design_quota_per_month === null
                ? "Unlimited designs this month."
                : `${profile.quota.designs_remaining} of ${profile.quota.design_quota_per_month} remaining this month.`}
              <br />
              {profile.quota.saved_designs_limit === null
                ? `${profile.quota.saved_designs_count} saved (unlimited).`
                : `${profile.quota.saved_designs_count} of ${profile.quota.saved_designs_limit} saved designs used.`}
            </p>

            {/* 3. Notifications */}
            <h4 style={{ marginBottom: 4 }}>Notifications</h4>
            {profile.notifications.length === 0 ? (
              <p className="refund-request-intro">Nothing new.</p>
            ) : (
              <ul style={{ fontSize: 14, color: "#475569", paddingLeft: 18, marginTop: 0 }}>
                {profile.notifications.map((n, i) => (
                  <li key={i}>{n.message} <span style={{ color: "#94a3b8" }}>— {new Date(n.at).toLocaleDateString()}</span></li>
                ))}
              </ul>
            )}

            {/* 4. Payment details record */}
            <h4 style={{ marginBottom: 4 }}>Payment History</h4>
            {profile.payments.length === 0 ? (
              <p className="refund-request-intro">{profile.payments_note || "No payments yet."}</p>
            ) : (
              <table className="admin-table" style={{ marginBottom: 8 }}>
                <thead><tr><th>Date</th><th>Amount</th><th>Status</th></tr></thead>
                <tbody>
                  {profile.payments.map((p) => (
                    <tr key={p.payment_id}>
                      <td>{p.created_at ? new Date(p.created_at).toLocaleDateString() : "—"}</td>
                      <td>${p.amount_usd} {p.currency?.toUpperCase()}</td>
                      <td>{p.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {/* 5. Tier upgrade */}
            <div className="refund-request-actions" style={{ justifyContent: "flex-start", marginTop: 8, marginBottom: 20 }}>
              <button type="button" className="terms-gate-accept" onClick={onUpgrade}>
                {profile.tier.tier_id ? "Change Plan" : "View Plans"}
              </button>
            </div>

            {/* 6. Disable account / stop subscription */}
            {profile.tier.tier_id && profile.tier.status === "active" && (
              <>
                <h4 style={{ marginBottom: 4 }}>Cancel Subscription</h4>
                <p className="refund-request-intro">Stops future billing. You keep access until your current period ends. Your account and data stay intact.</p>
                <input
                  type="text"
                  placeholder="Reason (optional)"
                  value={cancelReason}
                  onChange={(e) => setCancelReason(e.target.value)}
                  style={{ marginBottom: 8 }}
                />
                <div className="refund-request-actions" style={{ justifyContent: "flex-start", marginBottom: 20 }}>
                  <button type="button" className="terms-gate-decline" onClick={handleCancelSubscription} disabled={busy}>
                    Cancel Subscription
                  </button>
                </div>
              </>
            )}

            {/* 7. Delete account */}
            <h4 style={{ marginBottom: 4, color: "#c0392b" }}>Delete Account</h4>
            {!showDeleteConfirm ? (
              <div className="refund-request-actions" style={{ justifyContent: "flex-start", marginBottom: 8 }}>
                <button type="button" className="terms-gate-decline" style={{ borderColor: "#f5c6c1", color: "#c0392b" }} onClick={() => setShowDeleteConfirm(true)}>
                  Delete My Account
                </button>
              </div>
            ) : (
              <>
                <p className="refund-request-intro">
                  This permanently deletes your account and saved designs. Type your email to confirm.
                  For security, this email can't be used to create a new account for 7 days afterward.
                </p>
                <input
                  type="email"
                  placeholder={profile.email}
                  value={deleteConfirmEmail}
                  onChange={(e) => setDeleteConfirmEmail(e.target.value)}
                  style={{ marginBottom: 8 }}
                />
                <input
                  type="text"
                  placeholder="Reason (optional)"
                  value={deleteReason}
                  onChange={(e) => setDeleteReason(e.target.value)}
                  style={{ marginBottom: 8 }}
                />
                <div className="refund-request-actions" style={{ justifyContent: "flex-start", marginBottom: 8 }}>
                  <button type="button" className="terms-gate-decline" onClick={() => setShowDeleteConfirm(false)}>Cancel</button>
                  <button type="button" className="terms-gate-decline" style={{ background: "#c0392b", color: "white", borderColor: "#c0392b" }} onClick={handleDeleteAccount} disabled={busy}>
                    Permanently Delete
                  </button>
                </div>
              </>
            )}
          </>
        )}

        <div className="refund-request-actions" style={{ marginTop: 12 }}>
          <button type="button" className="terms-gate-decline" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

export default ProfilePanel;
