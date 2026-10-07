import { useEffect, useMemo, useState } from "react";
import { studioApi } from "./studioApi";

// The admin user manual. The text comes from the password-gated
// /api/admin/manual endpoint, so it is never part of the public site.
function Block({ block }) {
  if (block.type === "ul") return <ul>{block.items.map((t) => <li key={t}>{t}</li>)}</ul>;
  if (block.type === "ol") return <ol>{block.items.map((t) => <li key={t}>{t}</li>)}</ol>;
  if (block.type === "warn")
    return <div className="studio-status-banner" style={{ background: "#fef2f2", borderColor: "#fecaca", color: "#991b1b" }}>⚠ {block.text}</div>;
  if (block.type === "tip") return <div className="studio-status-banner">💡 {block.text}</div>;
  return <p>{block.text}</p>;
}

const textOf = (section) =>
  [section.title, ...section.blocks.flatMap((b) => (b.items ? b.items : [b.text]))].join(" ").toLowerCase();

export default function AdminManual({ password }) {
  const [sections, setSections] = useState(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");

  useEffect(() => {
    studioApi
      .adminManual(password)
      .then((d) => setSections(d.sections))
      .catch((err) => setError(err.message || "Couldn't load the manual."));
  }, [password]);

  const shown = useMemo(() => {
    if (!sections) return [];
    const q = query.trim().toLowerCase();
    return q ? sections.filter((s) => textOf(s).includes(q)) : sections;
  }, [sections, query]);

  if (error) return <div className="studio-status-banner" style={{ background: "#fef2f2", borderColor: "#fecaca", color: "#991b1b" }}>{error}</div>;
  if (!sections) return <p>Loading the manual...</p>;

  return (
    <div className="admin-manual">
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
        <input
          type="search" value={query} onChange={(e) => setQuery(e.target.value)}
          placeholder="Search the manual (e.g. refund, webhook, wind-down)" style={{ flex: "1 1 260px" }}
        />
        <button type="button" onClick={() => window.print()}>Print / save as PDF</button>
      </div>
      <nav style={{ marginBottom: 16, fontSize: 14 }}>
        {shown.map((s) => (
          <a key={s.id} href={`#manual-${s.id}`} style={{ display: "block", padding: "2px 0" }}>{s.title}</a>
        ))}
      </nav>
      {shown.length === 0 && <p>Nothing matches "{query}".</p>}
      {shown.map((s) => (
        <div key={s.id} id={`manual-${s.id}`} className="admin-section admin-section-blue">
          <h3>{s.title}</h3>
          {s.blocks.map((b, i) => <Block key={i} block={b} />)}
        </div>
      ))}
    </div>
  );
}
