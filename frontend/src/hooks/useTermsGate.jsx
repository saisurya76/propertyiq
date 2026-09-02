import { useCallback, useState } from "react";

// Bumped whenever the terms/policies change in a way that should
// require re-acceptance from someone who already accepted an older
// version — a plain boolean flag would never re-prompt after an
// update, silently treating stale consent as still valid forever.
const TERMS_VERSION = "2026-08-31";
const STORAGE_KEY = "propertyiq_terms_accepted_version";

function hasAcceptedCurrentTerms() {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === TERMS_VERSION;
  } catch {
    // localStorage can throw in some private-browsing modes — treat
    // as not-yet-accepted rather than crashing the gate entirely.
    return false;
  }
}

function markTermsAccepted() {
  try {
    window.localStorage.setItem(STORAGE_KEY, TERMS_VERSION);
  } catch {
    // Same private-browsing case — the gate will just re-prompt next
    // time in that scenario, which is the safe direction to fail in.
  }
}

// A reusable gate for any action that legally requires accepting
// Terms/Privacy/Refund policy first — generating a report or buying a
// tier/subscription, per the actual requirement this was built for.
// Usage: const { requireTerms, TermsGateModal } = useTermsGate();
// then call requireTerms(() => realActionFn()) instead of calling the
// real action directly, and render <TermsGateModal /> once near the
// top of the component's own JSX.
function useTermsGate() {
  const [visible, setVisible] = useState(false);
  const [pendingAction, setPendingAction] = useState(null);
  const [checked, setChecked] = useState(false);

  const requireTerms = useCallback((action) => {
    if (hasAcceptedCurrentTerms()) {
      action();
      return;
    }
    setPendingAction(() => action);
    setChecked(false);
    setVisible(true);
  }, []);

  const handleAccept = () => {
    if (!checked) return;
    markTermsAccepted();
    setVisible(false);
    const action = pendingAction;
    setPendingAction(null);
    if (action) action();
  };

  const handleDecline = () => {
    setVisible(false);
    setPendingAction(null);
  };

  const TermsGateModal = () => {
    if (!visible) return null;
    return (
      <div className="terms-gate-overlay" role="dialog" aria-modal="true" aria-label="Accept Terms to continue">
        <div className="terms-gate-card">
          <h3>Before you continue</h3>
          <p className="terms-gate-body">
            Please review and accept our policies to continue. Reports and cost estimates are informational,
            not professional advice — see our Terms for what that means and our full refund terms.
          </p>
          <ul className="terms-gate-links">
            <li><a href="/terms-of-service.html" target="_blank" rel="noopener noreferrer">Terms of Service</a></li>
            <li><a href="/privacy-policy.html" target="_blank" rel="noopener noreferrer">Privacy Policy</a></li>
            <li><a href="/refund-policy.html" target="_blank" rel="noopener noreferrer">Refund Policy</a></li>
          </ul>
          <label className="terms-gate-checkbox">
            <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} />
            I have read and accept the Terms of Service, Privacy Policy, and Refund Policy.
          </label>
          <div className="terms-gate-actions">
            <button type="button" className="terms-gate-decline" onClick={handleDecline}>Cancel</button>
            <button type="button" className="terms-gate-accept" onClick={handleAccept} disabled={!checked}>
              Accept &amp; Continue
            </button>
          </div>
        </div>
      </div>
    );
  };

  return { requireTerms, TermsGateModal };
}

export default useTermsGate;
