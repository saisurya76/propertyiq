import { useState } from "react";

function CollapsiblePanel({ title, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="collapsible-panel">
      <button
        type="button"
        className="collapsible-panel-header"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span>{title}</span>
        <span className={`collapsible-panel-chevron ${open ? "collapsible-panel-chevron-open" : ""}`}>
          ▾
        </span>
      </button>
      {open && <div className="collapsible-panel-body">{children}</div>}
    </div>
  );
}

export default CollapsiblePanel;
