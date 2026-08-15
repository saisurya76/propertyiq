import { useEffect, useState } from "react";
import { studioApi } from "./studioApi";

const REGIONS = [
  ["india", "India"],
  ["thailand", "Thailand"],
  ["usa", "USA"],
  ["global", "Other / Global"],
];

const CURRENCIES = ["USD", "INR", "THB", "AED", "GBP", "EUR"];

const DIRECTIONS = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"];

const STEPS = ["Plot Details", "Materials", "Room Layout", "Review & Generate"];

function emptyRoom() {
  return { name: "", x: 0, y: 0, length: 10, width: 10, _key: Math.random().toString(36).slice(2) };
}

function ConstructionStudio({ onBack, onQuotaExceeded }) {
  const [step, setStep] = useState(0);

  const [plot, setPlot] = useState({
    plot_length_ft: 40,
    plot_width_ft: 30,
    region: "india",
    currency: "INR",
    city: "",
    entrance_direction: "north-east",
    road_facing_side: "north",
    slope_direction: "north",
  });

  const [catalog, setCatalog] = useState(null);
  const [selections, setSelections] = useState({});
  const [estimate, setEstimate] = useState(null);
  const [rooms, setRooms] = useState([emptyRoom()]);

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const plotSizeSqft = Math.round(plot.plot_length_ft * plot.plot_width_ft);

  // Load material catalog whenever region changes
  useEffect(() => {
    studioApi.getMaterials(plot.region).then((res) => setCatalog(res.categories)).catch(() => setCatalog(null));
  }, [plot.region]);

  // Live running total whenever selections/plot size/currency change
  useEffect(() => {
    if (Object.keys(selections).length === 0) return;
    studioApi
      .estimateCost({
        plot_size_sqft: plotSizeSqft,
        selections,
        region: plot.region,
        currency: plot.currency,
      })
      .then(setEstimate)
      .catch(() => {});
  }, [selections, plotSizeSqft, plot.region, plot.currency]);

  const updatePlotField = (field, value) => setPlot((p) => ({ ...p, [field]: value }));

  const toggleMaterial = (category, optionId) => {
    setSelections((s) => ({ ...s, [category]: optionId }));
  };

  const updateRoom = (key, field, value) => {
    setRooms((rs) => rs.map((r) => (r._key === key ? { ...r, [field]: value } : r)));
  };

  const addRoom = () => setRooms((rs) => [...rs, emptyRoom()]);
  const removeRoom = (key) => setRooms((rs) => rs.filter((r) => r._key !== key));

  const generateDesign = async () => {
    setError("");
    setLoading(true);
    try {
      const payload = {
        plot_size_sqft: plotSizeSqft,
        plot_length_ft: plot.plot_length_ft,
        plot_width_ft: plot.plot_width_ft,
        selections,
        region: plot.region,
        currency: plot.currency,
        entrance_direction: plot.entrance_direction,
        road_facing_side: plot.road_facing_side,
        slope_direction: plot.slope_direction,
        rooms: rooms
          .filter((r) => r.name.trim())
          .map(({ name, x, y, length, width }) => ({ name, x, y, length, width })),
      };
      const designResult = await studioApi.createConstructionDesign(payload);
      setResult(designResult);
    } catch (err) {
      if (err.status === 403 && onQuotaExceeded) {
        onQuotaExceeded(err.message);
        return;
      }
      setError(err.message || "Couldn't generate the design. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const downloadDxf = () => {
    if (!result?.design_id || !result?.dxf_available) return;
    const url = `https://propertyiq-api-q21y.onrender.com/api/construction-studio/design/${result.design_id}/dxf`;
    window.open(url, "_blank", "noopener");
  };

  const canProceedFromPlot = plot.plot_length_ft > 0 && plot.plot_width_ft > 0 && plot.city.trim();
  const canProceedFromMaterials = catalog && Object.keys(selections).length > 0;

  return (
    <div className="cs-wizard">
      <div className="cs-steps">
        {STEPS.map((label, i) => (
          <span
            key={label}
            className={`cs-step-pill ${i === step ? "cs-step-active" : i < step ? "cs-step-done" : ""}`}
          >
            {i + 1}. {label}
          </span>
        ))}
      </div>

      {error && <div className="studio-status-banner" style={{ background: "#fef2f2", borderColor: "#fecaca", color: "#991b1b" }}>{error}</div>}

      {step === 0 && (
        <div className="cs-card">
          <h3>Plot Details</h3>
          <div className="cs-field-grid">
            <div className="cs-field">
              <label>City</label>
              <input value={plot.city} onChange={(e) => updatePlotField("city", e.target.value)} placeholder="e.g. Hyderabad" />
            </div>
            <div className="cs-field">
              <label>Region</label>
              <select value={plot.region} onChange={(e) => updatePlotField("region", e.target.value)}>
                {REGIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div className="cs-field">
              <label>Currency</label>
              <select value={plot.currency} onChange={(e) => updatePlotField("currency", e.target.value)}>
                {CURRENCIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div className="cs-field">
              <label>Plot Length (ft)</label>
              <input type="number" min="1" value={plot.plot_length_ft} onChange={(e) => updatePlotField("plot_length_ft", Number(e.target.value))} />
            </div>
            <div className="cs-field">
              <label>Plot Width (ft)</label>
              <input type="number" min="1" value={plot.plot_width_ft} onChange={(e) => updatePlotField("plot_width_ft", Number(e.target.value))} />
            </div>
            <div className="cs-field">
              <label>Road-Facing Side</label>
              <select value={plot.road_facing_side} onChange={(e) => updatePlotField("road_facing_side", e.target.value)}>
                {DIRECTIONS.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
            <div className="cs-field">
              <label>Main Entrance Direction</label>
              <select value={plot.entrance_direction} onChange={(e) => updatePlotField("entrance_direction", e.target.value)}>
                {DIRECTIONS.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
            <div className="cs-field">
              <label>Plot Slope Direction</label>
              <select value={plot.slope_direction} onChange={(e) => updatePlotField("slope_direction", e.target.value)}>
                {DIRECTIONS.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
          </div>
          <p className="studio-subtext">Plot area: <strong>{plotSizeSqft} sqft</strong></p>
        </div>
      )}

      {step === 1 && (
        <div className="cs-card">
          <h3>Materials & Suppliers</h3>
          <p className="studio-subtext">Pick one option per category — your estimate updates live below.</p>
          {!catalog && <p className="studio-subtext">Loading catalog...</p>}
          {catalog && Object.entries(catalog).map(([catId, cat]) => (
            <div className="cs-material-category" key={catId}>
              <h4>{cat.label}</h4>
              <div className="cs-material-options">
                {cat.options.map((opt) => (
                  <div
                    key={opt.id}
                    className={`cs-material-option ${selections[catId] === opt.id ? "cs-material-selected" : ""}`}
                    onClick={() => toggleMaterial(catId, opt.id)}
                  >
                    <div className="cs-material-name">{opt.name}</div>
                    <div className="cs-material-price">
                      ${opt.base_cost_usd}/{opt.unit} · {opt.suppliers.slice(0, 2).join(", ")}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}

          {estimate && Object.keys(selections).length > 0 && (
            <div className="cs-running-total">
              <span className="cs-total-label">Running estimate ({plot.currency})</span>
              <span className="cs-total-value">
                {plot.currency} {estimate.grand_total_converted.toLocaleString()}
              </span>
            </div>
          )}
        </div>
      )}

      {step === 2 && (
        <div className="cs-card">
          <h3>Room Layout</h3>
          <p className="studio-subtext">
            Position each room within your plot (feet from the bottom-left corner). Naming rooms clearly
            (e.g. "Kitchen", "Master Bedroom", "Pooja Room") enables Vastu compliance checks for that room.
          </p>
          <div className="cs-room-row" style={{ fontSize: 12, color: "#9ca3af", fontWeight: 600 }}>
            <span>Room name</span><span>X (ft)</span><span>Y (ft)</span><span>Length (ft)</span><span>Width (ft)</span><span></span>
          </div>
          {rooms.map((room) => (
            <div className="cs-room-row" key={room._key}>
              <input placeholder="Kitchen" value={room.name} onChange={(e) => updateRoom(room._key, "name", e.target.value)} />
              <input type="number" value={room.x} onChange={(e) => updateRoom(room._key, "x", Number(e.target.value))} />
              <input type="number" value={room.y} onChange={(e) => updateRoom(room._key, "y", Number(e.target.value))} />
              <input type="number" value={room.length} onChange={(e) => updateRoom(room._key, "length", Number(e.target.value))} />
              <input type="number" value={room.width} onChange={(e) => updateRoom(room._key, "width", Number(e.target.value))} />
              <button className="cs-remove-room" onClick={() => removeRoom(room._key)}>Remove</button>
            </div>
          ))}
          <button className="cs-add-room-btn" onClick={addRoom}>+ Add room</button>
        </div>
      )}

      {step === 3 && (
        <div className="cs-card">
          <h3>Review & Generate</h3>

          {!result && (
            <>
              <p className="studio-subtext">
                Plot: {plot.plot_length_ft}ft × {plot.plot_width_ft}ft in {plot.city || "your city"} ·{" "}
                {Object.keys(selections).length} material{Object.keys(selections).length === 1 ? "" : "s"} selected ·{" "}
                {rooms.filter((r) => r.name.trim()).length} room(s)
              </p>
              <button className="cs-nav-btn cs-nav-primary" onClick={generateDesign} disabled={loading}>
                {loading ? "Generating..." : "Generate Design"}
              </button>
            </>
          )}

          {result && (
            <>
              <div className="cs-running-total" style={{ position: "static", marginBottom: 20 }}>
                <span className="cs-total-label">Total estimated cost</span>
                <span className="cs-total-value">
                  {plot.currency} {result.cost_estimate.grand_total_converted.toLocaleString()}
                </span>
              </div>

              <h4>Vastu Compliance</h4>
              {result.vastu_result.scope === "full_multi_rule_check" ? (
                result.vastu_result.findings.map((f, i) => (
                  <div
                    key={i}
                    className={`cs-vastu-finding ${
                      f.note.includes("advises against") || f.note.includes("recommends keeping open")
                        ? "cs-vastu-bad"
                        : f.note.includes("aligns")
                        ? "cs-vastu-good"
                        : "cs-vastu-neutral"
                    }`}
                  >
                    {f.note}
                  </div>
                ))
              ) : (
                result.vastu_result.notes.map((n, i) => (
                  <div key={i} className="cs-vastu-finding cs-vastu-neutral">{n}</div>
                ))
              )}

              <h4 style={{ marginTop: 24 }}>Risks to Consider</h4>
              <ul className="cs-risk-list">
                {result.risks.map((r, i) => <li key={i}>{r}</li>)}
              </ul>

              {result.dxf_available ? (
                <button className="cs-download-btn" onClick={downloadDxf}>
                  Download Plot Layout (DXF)
                </button>
              ) : (
                <p className="studio-subtext">
                  No DXF was generated — add at least one named room in the previous step to export a layout.
                </p>
              )}
            </>
          )}
        </div>
      )}

      <div className="cs-wizard-nav">
        <button
          className="cs-nav-btn cs-nav-secondary"
          onClick={() => (step === 0 ? onBack() : setStep((s) => s - 1))}
        >
          {step === 0 ? "← Back to plans" : "← Previous"}
        </button>
        {step < 3 && (
          <button
            className="cs-nav-btn cs-nav-primary"
            disabled={(step === 0 && !canProceedFromPlot) || (step === 1 && !canProceedFromMaterials)}
            onClick={() => setStep((s) => s + 1)}
          >
            Next →
          </button>
        )}
      </div>
    </div>
  );
}

export default ConstructionStudio;
