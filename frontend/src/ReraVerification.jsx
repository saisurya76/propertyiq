import { useEffect, useState } from "react";
import "./ReraVerification.css";
import { studioApi } from "./studio/studioApi";

const EMPTY = {
  state: "", number: "", project: "", builder: "", agent: "", possession: "", underConstruction: "",
  quoted: "", market: "", advance: "",
};

const num = (v) => (v === "" || v === null ? null : Number(v));

export default function ReraVerification({ onBack, onNeedPlan }) {
  const [states, setStates] = useState([]);
  const [disclaimer, setDisclaimer] = useState("");
  const [form, setForm] = useState(EMPTY);
  const [result, setResult] = useState(null);
  const [ticked, setTicked] = useState({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [noAccess, setNoAccess] = useState(false);

  useEffect(() => {
    let alive = true;
    studioApi.reraStates()
      .then((d) => { if (alive) { setStates(d.states || []); setDisclaimer(d.disclaimer || ""); } })
      .catch(() => { if (alive) setError("Couldn't load the state list. Please refresh."); });
    return () => { alive = false; };
  }, []);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const selected = states.find((s) => s.code === form.state);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (!form.state) { setError("Choose the state the project is registered in."); return; }
    if (!form.number.trim()) { setError("Enter the RERA registration number."); return; }
    setBusy(true);
    try {
      const res = await studioApi.reraCheck({
        state: form.state,
        registration_number: form.number,
        possession_date: form.possession || null,
        quoted_price_per_sqft: num(form.quoted),
        market_price_per_sqft: num(form.market),
        advance_percent: num(form.advance),
        is_under_construction: form.underConstruction === "" ? null : form.underConstruction === "yes",
        agent_registration_number: form.agent || null,
        project_name: form.project || null,
        builder_name: form.builder || null,
      });
      setResult(res);
      setTicked({});
    } catch (err) {
      if (err.status === 403) setNoAccess(true);
      else setError(err.message || "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  if (noAccess) {
    return (
      <div className="rera-page">
        <button className="rera-back" onClick={onBack}>← Back</button>
        <h1>RERA Verification</h1>
        <div className="rera-card">
          <p>This tool isn't open on your account right now.</p>
          <button className="rera-btn" onClick={onNeedPlan}>See plans</button>
        </div>
      </div>
    );
  }

  const doneCount = result ? result.checklist.filter((_, i) => ticked[i]).length : 0;

  return (
    <div className="rera-page">
      <button className="rera-back" onClick={onBack}>← Back</button>
      <h1>RERA Verification</h1>
      <p className="rera-lead">
        Enter the RERA number you were given. We'll check it looks right, take you to your state's
        official portal, and give you a checklist of what to confirm there.
      </p>

      <form className="rera-card" onSubmit={submit}>
        <div className="rera-step">Step 1 · Project details</div>
        <div className="rera-grid">
          <label className="rera-field">State
            <select value={form.state} onChange={set("state")}>
              <option value="">Choose state…</option>
              {states.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
            </select>
          </label>
          <label className="rera-field">RERA registration number
            <input value={form.number} onChange={set("number")} maxLength={80} placeholder="As printed on the brochure" autoComplete="off" />
          </label>
          <label className="rera-field">Project name (as advertised)
            <input value={form.project} onChange={set("project")} maxLength={120} autoComplete="off" />
          </label>
          <label className="rera-field">Builder / promoter name
            <input value={form.builder} onChange={set("builder")} maxLength={120} autoComplete="off" />
          </label>
          <label className="rera-field full">Agent's RERA number (optional)
            <input value={form.agent} onChange={set("agent")} maxLength={80} autoComplete="off" />
          </label>
        </div>

        <div className="rera-step" style={{ marginTop: 18 }}>Optional · for a quick sanity check</div>
        <div className="rera-grid">
          <label className="rera-field">Promised possession date
            <input type="date" value={form.possession} onChange={set("possession")} />
          </label>
          <label className="rera-field">Is it under construction?
            <select value={form.underConstruction} onChange={set("underConstruction")}>
              <option value="">Not sure</option>
              <option value="yes">Yes</option>
              <option value="no">No, ready to move in</option>
            </select>
          </label>
          <label className="rera-field">Quoted price per sq ft
            <input type="number" min="0" inputMode="decimal" value={form.quoted} onChange={set("quoted")} />
          </label>
          <label className="rera-field">Market average per sq ft
            <input type="number" min="0" inputMode="decimal" value={form.market} onChange={set("market")} />
          </label>
          <label className="rera-field full">Advance asked before registered agreement (% of price)
            <input type="number" min="0" max="100" inputMode="decimal" value={form.advance} onChange={set("advance")} />
          </label>
        </div>

        <div className="rera-actions">
          <button className="rera-btn" type="submit" disabled={busy}>{busy ? "Checking…" : "Check"}</button>
          {selected && (
            <a className="rera-btn alt" href={selected.portal_url} target="_blank" rel="noopener noreferrer">
              Open {selected.name} portal ↗
            </a>
          )}
        </div>
        {error && <div className="rera-error" role="alert">{error}</div>}
      </form>

      {result && (
        <>
          <div className="rera-card">
            <div className="rera-step">Step 2 · Verify on the official portal</div>
            <h2>{result.state.name}: {result.number}</h2>
            <div className="rera-point">
              <span className={`rera-dot ${result.format_check.level}`} />
              <span>{result.format_check.notes.join(" ")}</span>
            </div>
            <div className="rera-compare">
              <div className="rera-step">Must match what the portal shows</div>
              {[["RERA number", result.number], ["Project name", result.provided.project_name], ["Builder / promoter", result.provided.builder_name]].map(([k, v]) => (
                <div key={k} className="rera-compare-row">
                  <span>{k}</span>
                  <strong>{v || "Not entered"}</strong>
                </div>
              ))}
              <p className="rera-lead" style={{ fontSize: 13, margin: "6px 0 0" }}>
                Look up the number on the portal. If the project name or builder differs, or the number is not found, do not pay anything yet.
              </p>
            </div>
            <div className="rera-actions">
              <a className="rera-btn" href={result.state.portal_url} target="_blank" rel="noopener noreferrer">
                Open official portal ↗
              </a>
            </div>
            <p className="rera-note" style={{ marginTop: 12 }}>
              Search the number there. We can't confirm it for you, and nothing on this page means the project is verified.
            </p>
          </div>

          <div className="rera-card">
            <div className="rera-step">Step 3 · Checklist ({doneCount}/{result.checklist.length} done)</div>
            {result.checklist.map((item, i) => (
              <label key={i} className={`rera-check ${ticked[i] ? "done" : ""}`}>
                <input type="checkbox" checked={!!ticked[i]} onChange={() => setTicked((t) => ({ ...t, [i]: !t[i] }))} />
                <span>{item}</span>
              </label>
            ))}
          </div>

          <div className="rera-card">
            <h2>Quick observations</h2>
            {result.analysis.map((a, i) => (
              <div key={i} className="rera-point">
                <span className={`rera-dot ${a.level}`} />
                <span>{a.text}</span>
              </div>
            ))}
          </div>
        </>
      )}

      <p className="rera-note">{result?.disclaimer || disclaimer}</p>
    </div>
  );
}
