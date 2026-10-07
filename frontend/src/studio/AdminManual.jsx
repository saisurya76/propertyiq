import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { studioApi } from "./studioApi";
import "./adminManual.css";

// The admin user manual. The text comes from the password-gated
// /api/admin/manual endpoint, so it is never part of the public site.

// Setting names (ALL_CAPS_WITH_UNDERSCORES) and site paths read as code.
const CODE = /(\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b|(?<![\w.])\/(?:admin|api|terms-of-service\.html|refund-policy\.html|privacy-policy\.html)[\w\-./]*)/g;

const escapeRe = (t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

function Marked({ text, query }) {
  if (!query) return text;
  const parts = text.split(new RegExp(`(${escapeRe(query)})`, "gi"));
  return parts.map((p, i) =>
    i % 2 === 1 ? <mark key={i}>{p}</mark> : <Fragment key={i}>{p}</Fragment>
  );
}

function Rich({ text, query }) {
  return text.split(CODE).map((part, i) =>
    i % 2 === 1 ? (
      <code key={i}><Marked text={part} query={query} /></code>
    ) : (
      <Marked key={i} text={part} query={query} />
    )
  );
}

function Block({ block, query }) {
  if (block.type === "ul")
    return <ul className="manual-list">{block.items.map((t) => <li key={t}><Rich text={t} query={query} /></li>)}</ul>;
  if (block.type === "ol")
    return <ol className="manual-steps">{block.items.map((t) => <li key={t}><div><Rich text={t} query={query} /></div></li>)}</ol>;
  if (block.type === "warn")
    return (
      <aside className="manual-callout manual-callout-warn" role="note">
        <strong>Careful</strong>
        <p><Rich text={block.text} query={query} /></p>
      </aside>
    );
  if (block.type === "tip")
    return (
      <aside className="manual-callout manual-callout-tip" role="note">
        <strong>Tip</strong>
        <p><Rich text={block.text} query={query} /></p>
      </aside>
    );
  return <p className="manual-p"><Rich text={block.text} query={query} /></p>;
}

const textOf = (s) =>
  [s.title, ...s.blocks.flatMap((b) => (b.items ? b.items : [b.text]))].join(" ").toLowerCase();
const plainTitle = (t) => t.replace(/^\d+\.\s*/, "");

export default function AdminManual({ password }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(null);
  const chapterRefs = useRef({});

  useEffect(() => {
    studioApi
      .adminManual(password)
      .then(setData)
      .catch((err) => setError(err.message || "Couldn't load the manual."));
  }, [password]);

  const q = query.trim();
  const shown = useMemo(() => {
    if (!data) return [];
    return q ? data.sections.filter((s) => textOf(s).includes(q.toLowerCase())) : data.sections;
  }, [data, q]);

  // Highlight the chapter being read in the contents list.
  useEffect(() => {
    if (!shown.length || typeof IntersectionObserver === "undefined") return undefined;
    const obs = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.dataset.id);
      },
      { rootMargin: "-10% 0px -70% 0px" }
    );
    Object.values(chapterRefs.current).forEach((el) => el && obs.observe(el));
    return () => obs.disconnect();
  }, [shown]);

  const go = (id) => {
    setQuery("");
    setTimeout(() => {
      const el = document.getElementById(`manual-${id}`);
      if (el) {
        el.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
        setActive(id);
      }
    }, 0);
  };

  if (error) return <div className="studio-status-banner" style={{ background: "#fef2f2", borderColor: "#fecaca", color: "#991b1b" }}>{error}</div>;
  if (!data) return <p className="manual-loading">Loading the manual…</p>;

  const all = data.sections;
  return (
    <div className="manual">
      <header className="manual-head">
        <div>
          <h1 className="manual-title">User manual</h1>
          <p className="manual-lede">
            How each admin screen works, the steps for the jobs you do rarely, and what to check when something looks wrong.
            Only visible with the admin password.
          </p>
        </div>
        <button type="button" className="manual-print" onClick={() => window.print()}>Print or save as PDF</button>
      </header>

      {!q && data.quick?.length > 0 && (
        <section className="manual-quick" aria-label="Find a fix fast">
          <h2>Something needs doing now</h2>
          <ul>
            {data.quick.map((item) => (
              <li key={item.label}>
                <button type="button" onClick={() => go(item.target)}>{item.label}</button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="manual-body">
        <aside className="manual-rail">
          <label className="manual-search">
            <span className="manual-sr">Search the manual</span>
            <input type="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search: refund, webhook, wind-down" />
          </label>
          {q && <p className="manual-count" aria-live="polite">{shown.length} of {all.length} chapters match</p>}
          <nav aria-label="Chapters">
            <ol>
              {all.map((s, i) => {
                const hit = shown.includes(s);
                return (
                  <li key={s.id}>
                    <a
                      href={`#manual-${s.id}`}
                      className={`${active === s.id ? "is-active" : ""} ${q && !hit ? "is-dim" : ""}`}
                      aria-current={active === s.id ? "true" : undefined}
                      onClick={(e) => { e.preventDefault(); if (hit || !q) go(s.id); }}
                    >
                      <span className="manual-num">{i + 1}</span>
                      <span>{plainTitle(s.title)}</span>
                    </a>
                  </li>
                );
              })}
            </ol>
          </nav>
        </aside>

        <main className="manual-main">
          {shown.length === 0 && (
            <p className="manual-empty">
              No chapter mentions "{q}". Try one word, such as refund, webhook, quota or password.
            </p>
          )}
          {shown.map((s) => (
            <article
              key={s.id} id={`manual-${s.id}`} data-id={s.id} className="manual-chapter"
              ref={(el) => { chapterRefs.current[s.id] = el; }}
            >
              <h2><span className="manual-chapter-num">{all.indexOf(s) + 1}</span>{plainTitle(s.title)}</h2>
              {s.blocks.map((b, i) => <Block key={i} block={b} query={q} />)}
            </article>
          ))}
        </main>
      </div>
    </div>
  );
}
