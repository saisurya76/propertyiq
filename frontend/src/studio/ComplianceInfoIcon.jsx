import { useState } from "react";
import { studioApi } from "./studioApi";

// A small "ⓘ" button next to the Vastu/Thai compliance title. On click,
// fetches and shows the real, complete list of rules the live check
// validates against (sourced server-side directly from the same
// constants the actual validation uses — see backend/compliance_rules.py
// — so this can never drift out of sync with what's genuinely checked).
function ComplianceInfoIcon({ tradition }) {
  const [open, setOpen] = useState(false);
  const [state, setState] = useState("idle"); // "idle" | "loading" | "done" | "error"
  const [rules, setRules] = useState(null);

  const handleOpen = async () => {
    setOpen(true);
    if (rules) return; // already fetched once, no need to refetch on reopen
    setState("loading");
    try {
      const data = await studioApi.getComplianceRules(tradition);
      setRules(data);
      setState("done");
    } catch {
      setState("error");
    }
  };

  return (
    <>
      <button
        type="button"
        className="cs-compliance-info-btn"
        onClick={handleOpen}
        aria-label={`What does this ${tradition === "thai" ? "traditional building" : "Vastu"} check validate?`}
        title="See all the rules this check validates against"
      >
        ⓘ
      </button>

      {open && (
        <div className="cs-compliance-modal-backdrop" onClick={() => setOpen(false)}>
          <div className="cs-compliance-modal" onClick={(e) => e.stopPropagation()}>
            <div className="cs-compliance-modal-header">
              <h4>{tradition === "thai" ? "Traditional Building Compliance — Full Rule List" : "Vastu Compliance — Full Rule List"}</h4>
              <button type="button" className="cs-compliance-modal-close" onClick={() => setOpen(false)} aria-label="Close">×</button>
            </div>

            {state === "loading" && <p className="studio-subtext">Loading rules...</p>}
            {state === "error" && <p className="studio-subtext">Couldn't load the rule list right now — please try again.</p>}

            {state === "done" && rules && (
              <>
                <p className="cs-compliance-scope-note">{rules.scope_note}</p>
                {rules.rules.map((rule, i) => (
                  <div key={i} className="cs-compliance-rule">
                    <div className="cs-compliance-rule-category">{rule.category}</div>
                    <div className="cs-compliance-rule-title">{rule.title}</div>
                    <p className="cs-compliance-rule-detail">{rule.detail}</p>
                  </div>
                ))}
              </>
            )}
          </div>
        </div>
      )}
    </>
  );
}

export default ComplianceInfoIcon;
