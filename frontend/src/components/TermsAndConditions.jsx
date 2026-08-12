import { useState } from "react";

function TermsAndConditions({ onAccept, onCancel }) {
  const [accepted, setAccepted] = useState(false);

  return (
    <div className="terms-overlay" role="dialog" aria-modal="true" aria-labelledby="terms-title">
      <div className="terms-card">
        <div className="terms-header">
          <div>
            <div className="terms-eyebrow">PROPERTYIQ REPORT</div>
            <h2 id="terms-title">Terms &amp; Conditions</h2>
          </div>
          <button className="terms-close" type="button" onClick={onCancel} aria-label="Close">
            ×
          </button>
        </div>

        <div className="terms-content">
          <p>
            Please review and accept the following terms before purchasing a PropertyIQ report.
          </p>

          <h3>1. Nature of the Report</h3>
          <p>
            PropertyIQ provides independent, informational property decision-support analysis based
            on the information and evidence available to the system. The report is not legal,
            financial, tax, engineering, investment, valuation-certification, or regulatory advice.
          </p>

          <h3>2. Information Provided</h3>
          <p>
            You are responsible for ensuring that the information you submit is accurate and complete.
            PropertyIQ does not independently guarantee the accuracy of user-provided information.
          </p>

          <h3>3. Fair Value</h3>
          <p>
            PropertyIQ's Fair Value is an independent analytical estimate produced using its stated
            methodology and the evidence available for the assessment. It is not a certified appraisal,
            guaranteed sale price, or representation of the property's actual market value.
          </p>

          <h3>4. Independent Verification</h3>
          <p>
            You should independently verify property ownership, title, approvals, government records,
            developer information, market conditions, and all other material facts before making a
            property decision.
          </p>

          <h3>5. Report Delivery</h3>
          <p>
            After successful payment, the purchased report will be generated and delivered to the
            email address provided during the purchase process, subject to the applicable payment
            and delivery conditions.
          </p>

          <h3>6. Acceptance Record</h3>
          <p>
            Your acceptance of these terms may be recorded together with the applicable report and
            transaction details for audit, customer-support, and legal-record purposes.
          </p>

          <h3>7. Terms Version</h3>
          <p>
            Terms version: <strong>PropertyIQ Report Terms v1.0</strong>
          </p>
        </div>

        <label className="terms-acceptance">
          <input
            type="checkbox"
            checked={accepted}
            onChange={(event) => setAccepted(event.target.checked)}
          />
          <span>I have read and accept the PropertyIQ Report Terms &amp; Conditions.</span>
        </label>

        <div className="terms-actions">
          <button className="terms-cancel-btn" type="button" onClick={onCancel}>
            Cancel
          </button>
          <button
            className="terms-buy-btn"
            type="button"
            disabled={!accepted}
            onClick={onAccept}
          >
            Buy Report
          </button>
        </div>
      </div>
    </div>
  );
}

export default TermsAndConditions;
