import { useCallback, useEffect, useState } from "react";
import { studioApi } from "./studioApi";

// Admin tool for taking the service down: cancels every active subscription's
// renewals on Dodo in batches, emails each customer, and shows progress.
// Nothing is deleted. See the wind-down section in backend/api.py.
const MODE_TEXT = {
  period_end:
    "Planned pause (recommended): stop renewals. Customers keep access until the end of the period they paid for. No refunds.",
  immediate:
    "Immediate closure: refund each customer's latest payment in full and cancel now. Needs funds in your Dodo wallet. Also closes Quick Analysis.",
};

export default function WindDownPanel({ password, refreshTick = 0 }) {
  const [summary, setSummary] = useState(null);
  const [mode, setMode] = useState("period_end");
  const [message, setMessage] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    try {
      setSummary(await studioApi.adminWindDownStatus(password));
    } catch (err) {
      setError(err.message || "Couldn't load wind-down status.");
    }
  }, [password]);

  useEffect(() => {
    studioApi
      .adminWindDownStatus(password)
      .then(setSummary)
      .catch((err) => setError(err.message || "Couldn't load wind-down status."));
  }, [password, refreshTick]);

  const run = async (fn, doneNote) => {
    setBusy(true); setError(""); setNote("");
    try {
      const data = await fn();
      setSummary((prev) => ({ ...(prev || {}), ...data }));
      if (doneNote) setNote(doneNote(data));
      return data;
    } catch (err) {
      setError(err.message || "That didn't work.");
    } finally {
      setBusy(false);
    }
  };

  const start = async () => {
    const msg =
      `Start a ${mode === "immediate" ? "IMMEDIATE closure" : "planned pause"}?\n\n` +
      "• All subscription plans become Coming soon (no new subscriptions)\n" +
      (mode === "immediate" ? "• Quick Analysis also closes\n" : "") +
      "• Nothing is cancelled on Dodo yet: you run that in batches next\n" +
      "• Nothing is deleted";
    if (!window.confirm(msg)) return;
    await run(() => studioApi.adminWindDownStart(password, mode, confirm, message), () => "Started. Now run the batches.");
    setConfirm("");
  };

  const runAll = async () => {
    if (!window.confirm("Cancel renewals on Dodo for every pending subscriber now, 10 at a time, and email each one?")) return;
    setBusy(true); setError(""); setNote("");
    try {
      let data = await studioApi.adminWindDownStatus(password);
      while ((data.counts?.pending || 0) > 0) {
        data = await studioApi.adminWindDownRunBatch(password, 10);
        setSummary((prev) => ({ ...(prev || {}), ...data }));
        if (!data.processed) break;
      }
      const failed = data.counts?.failed || 0;
      setNote(failed ? `Done, but ${failed} failed. See the reasons below, fix them, then press Retry failed.` : "All done.");
    } catch (err) {
      setError(err.message || "Stopped by an error. Press Run all to continue where it left off.");
    } finally {
      setBusy(false);
    }
  };

  const state = summary?.state;
  const counts = summary?.counts || {};
  const items = summary?.items || [];

  return (
    <div className="admin-section admin-section-purple">
      <h3>Wind down subscriptions</h3>
      <p className="admin-section-note" style={{ marginTop: -8 }}>
        For taking the site down. Stops all future renewals on Dodo in batches, emails every customer (with links to
        the Terms, Refund Policy and Privacy Policy) and tracks progress here. Nothing is deleted. If the site comes
        back later, press Resume before a customer's period ends (their plan simply continues), then Reopen.
      </p>
      {error && <div className="studio-status-banner" style={{ background: "#fef2f2", borderColor: "#fecaca", color: "#991b1b" }}>{error}</div>}
      {note && <div className="studio-status-banner">{note}</div>}

      {!state && (
        <>
          {Object.entries(MODE_TEXT).map(([key, text]) => (
            <label key={key} className="admin-feature-checkbox" style={{ display: "block", margin: "6px 0" }}>
              <input type="radio" name="wind-mode" checked={mode === key} onChange={() => setMode(key)} /> {text}
            </label>
          ))}
          <textarea
            value={message} onChange={(e) => setMessage(e.target.value)} maxLength={500} rows={2}
            placeholder="Optional note added to every customer email and shown on the site (e.g. 'We expect to be back in January')"
            style={{ width: "100%", margin: "8px 0" }}
          />
          <input
            value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="Type WIND DOWN to confirm"
            style={{ marginRight: 8 }}
          />
          <button type="button" onClick={start} disabled={busy || confirm.trim() !== "WIND DOWN"}>Start wind-down</button>
        </>
      )}

      {state && (
        <>
          <p>
            <strong>{state.mode === "immediate" ? "Immediate closure" : "Planned pause"}</strong> started{" "}
            {new Date(state.started_at).toLocaleString()}. Pending {counts.pending || 0} · Scheduled {counts.scheduled || 0} ·
            Cancelled {counts.cancelled || 0} · Failed {counts.failed || 0} · Resumed {counts.resumed || 0} ·
            Skipped {counts.skipped || 0}
          </p>
          <button type="button" onClick={runAll} disabled={busy || !(counts.pending > 0)}>Run all pending (10 at a time)</button>{" "}
          <button
            type="button" disabled={busy || !(counts.failed > 0)}
            onClick={() => run(() => studioApi.adminWindDownRunBatch(password, 10), (d) => `Retried ${d.processed}.`)}
          >Retry failed</button>{" "}
          {state.mode === "period_end" && (
            <button
              type="button" disabled={busy || !(counts.scheduled > 0)}
              onClick={() => window.confirm("Undo the non-renewal for everyone still scheduled? Their plans continue and they are emailed.") &&
                run(() => studioApi.adminWindDownResume(password), (d) => `Resumed ${d.resumed}${d.resume_failed ? `, ${d.resume_failed} failed` : ""}.`)}
            >Resume all</button>
          )}{" "}
          <button
            type="button" disabled={busy}
            onClick={() => window.confirm("End the wind-down and reopen the plans it closed? Already-cancelled customers must subscribe again.") &&
              run(() => studioApi.adminWindDownReopen(password), () => "Reopened.")}
          >Reopen plans</button>{" "}
          <button type="button" onClick={load} disabled={busy}>Refresh</button>
          {items.length > 0 && (
            <table style={{ width: "100%", fontSize: 13, marginTop: 10 }}>
              <thead><tr><th align="left">Email</th><th align="left">Plan</th><th align="left">Status</th><th align="left">Access until</th><th align="left">Refund</th><th align="left">Emailed</th><th align="left">Problem</th></tr></thead>
              <tbody>
                {items.map((i) => (
                  <tr key={i.email}>
                    <td>{i.email}</td><td>{i.tier_id}</td><td>{i.status}</td><td>{i.access_until || "—"}</td>
                    <td>{i.refund_status === "issued" ? `${i.refund_currency || ""} ${i.refund_amount ?? ""}` : "—"}</td>
                    <td>{i.notified ? "yes" : "no"}</td><td style={{ color: "#991b1b" }}>{i.error || ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  );
}
