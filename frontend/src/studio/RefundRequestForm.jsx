import { useState } from "react";
import { studioApi } from "./studioApi";

// Matches VALID_REASON_CODES in backend/refund_store.py exactly — kept
// as a fixed list (not free text) so a request is self-classifying
// against a real refund-policy clause instead of admin having to
// interpret free-form text from scratch every time. See
// refund_request_module_spec.md section 3.
const REASON_OPTIONS = [
  { value: "report_never_generated", label: "I was charged but my report was never generated" },
  { value: "duplicate_charge", label: "I was charged more than once for the same purchase" },
  { value: "report_incorrect", label: "My report is materially incomplete or incorrect" },
  { value: "insight_addon_technical_failure", label: "The Insight Add-on didn't unlock after payment" },
  { value: "first_month_guarantee", label: "I'm unhappy with my first month (within 7 days)" },
  { value: "charged_after_cancellation", label: "I was charged after already cancelling" },
  { value: "wrong_plan_charged", label: "I was charged for the wrong plan" },
  { value: "other", label: "Something else" },
];

function RefundRequestForm({ defaultEmail = "", onClose }) {
  const [email, setEmail] = useState(defaultEmail);
  const [reasonCode, setReasonCode] = useState("");
  const [purchaseReference, setPurchaseReference] = useState("");
  const [details, setDetails] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (!email.trim() || !reasonCode) {
      setError("Email and a reason are both required.");
      return;
    }
    if (reasonCode === "other" && !details.trim()) {
      setError("Please describe the issue — there's no predefined reason to fall back on for 'Something else.'");
      return;
    }
    setSubmitting(true);
    try {
      const res = await studioApi.submitRefundRequest(email.trim(), reasonCode, details.trim() || undefined, purchaseReference.trim() || undefined);
      setSubmitted(res.request);
    } catch (err) {
      setError(err.message || "Couldn't submit your request. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="refund-request-overlay" role="dialog" aria-modal="true">
        <div className="refund-request-card">
          <h3>Request received</h3>
          <p>
            We've received your refund request. We aim to respond within 3 business days, per our{" "}
            <a href="/refund-policy.html" target="_blank" rel="noopener noreferrer">refund policy</a>.
          </p>
          <p className="refund-request-reference">Reference: {submitted.id}</p>
          <button type="button" className="terms-gate-accept" onClick={onClose}>Close</button>
        </div>
      </div>
    );
  }

  return (
    <div className="refund-request-overlay" role="dialog" aria-modal="true" aria-label="Request a refund">
      <div className="refund-request-card">
        <h3>Request a refund</h3>
        <p className="refund-request-intro">
          Pick the option closest to your situation — see our full{" "}
          <a href="/refund-policy.html" target="_blank" rel="noopener noreferrer">refund policy</a> for exact
          eligibility per product.
        </p>
        {error && <div className="refund-request-error">{error}</div>}
        <form onSubmit={handleSubmit}>
          <label className="refund-request-label">Your account email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" required />

          <label className="refund-request-label">What happened?</label>
          <select value={reasonCode} onChange={(e) => setReasonCode(e.target.value)} required>
            <option value="" disabled>Select a reason</option>
            {REASON_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>

          <label className="refund-request-label">Payment ID or order reference (if you have it)</label>
          <input type="text" value={purchaseReference} onChange={(e) => setPurchaseReference(e.target.value)} placeholder="Optional" />

          <label className="refund-request-label">
            Details {reasonCode === "other" ? "(required)" : "(optional)"}
          </label>
          <textarea value={details} onChange={(e) => setDetails(e.target.value)} rows={3} placeholder="Anything that helps us understand your situation" />

          <div className="refund-request-actions">
            <button type="button" className="terms-gate-decline" onClick={onClose}>Cancel</button>
            <button type="submit" className="terms-gate-accept" disabled={submitting}>
              {submitting ? "Submitting..." : "Submit Request"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default RefundRequestForm;
