import { useEffect, useState } from "react";
import { studioApi } from "./studioApi";

// SVG y-axis grows downward, but this app's plot convention (matching
// the DXF export and PlotPreview.jsx) treats y as south(0) -> north(+).
// Flip y when drawing so "north" visually renders at the top — same
// convention/helper as PlotPreview.jsx, duplicated here rather than
// refactoring that already-working component just to share one line.
function flipY(y, widthFt) {
  return widthFt - y;
}

const DISCIPLINES = [
  { id: "structural", label: "Structural" },
  { id: "plumbing", label: "Plumbing" },
  { id: "electrical", label: "Electrical" },
];

// Same clamp range as RoomCanvas.jsx's own zoom, for a consistent feel
// between this view and the interactive room-layout canvas.
const clampZoom = (z) => Math.max(0.4, Math.min(3, z));

// Colors are NEVER hardcoded here — every drawn element's color comes
// from the backend's own `legend` array (see discipline_overlays.py's
// LEGEND constant), so the swatch shown in the legend key and the color
// actually used to draw that element can never drift apart. Falls back
// to a neutral gray only if a legend entry is ever genuinely missing
// (should not happen in practice — every element type has one).
function legendColor(legend, key) {
  return legend?.find((entry) => entry.key === key)?.color || "#6b7280";
}

// A single, small label text element, consistently offset from its
// marker so it never sits exactly on top of it — shared by every
// discipline's rendering below rather than repeating this in each.
// Also the click target for showing that element's reference spec.
function ElementLabel({ x, y, plotWidthFt, text, onClick }) {
  return (
    <text
      x={x + 0.5} y={flipY(y, plotWidthFt) - 0.5}
      fontSize={1.1} fontWeight={700} fill="#1f2937"
      onClick={onClick} style={{ cursor: onClick ? "pointer" : "default" }}
    >
      {text}
    </text>
  );
}

// Three separate, transparent overlay layouts drawn over the exact same
// room footprint as the live floor plan — one discipline shown at a
// time via the toggle below, with a floor tab row when the design has
// more than one floor. See discipline_overlays.py's own docstring for
// the critical honesty boundary every result here carries: this is a
// SCHEMATIC visualization aid, not a licensed engineer's calculated
// design — the disclaimer returned by the backend is always shown
// prominently, never hidden or shortened. Every element's reference
// spec (also never calculated for this specific building — same
// boundary, just per-element instead of a single top-level statement)
// is shown when the user taps that element's label, not by default,
// since there's real text-per-element and showing all of it inline for
// every element at once would overwhelm the drawing.
function DisciplineOverlayView({ floors, plotLengthFt, plotWidthFt, initialFloorIndex = 0 }) {
  const [floorIndex, setFloorIndex] = useState(initialFloorIndex);
  const [discipline, setDiscipline] = useState("structural");
  const [zoom, setZoom] = useState(1);
  const [overlay, setOverlay] = useState(null);
  const [state, setState] = useState("idle"); // "idle" | "loading" | "done" | "error"
  const [selectedElement, setSelectedElement] = useState(null); // { label, spec } | null

  const rooms = floors[floorIndex]?.rooms || [];
  const totalFloors = floors.length;

  // Depend on a stable, content-based key rather than the `rooms` array
  // reference itself — `rooms` is recomputed from floor/layout state on
  // every render even when its actual content hasn't changed, which
  // would otherwise re-fire this fetch continuously and never let it
  // settle into a "done" state.
  const roomsKey = JSON.stringify(rooms.map((r) => [r.name, r.x, r.y, r.length, r.width]));

  useEffect(() => {
    if (!plotLengthFt || !plotWidthFt) return;
    // A real, genuine race condition to avoid, not just a lint-rule
    // formality: setTimeout(fn, 0) is a macrotask, but this fetch's own
    // promise resolves as a microtask — if the API responds fast enough,
    // the deferred "loading" setState would fire AFTER the fetch's
    // "done" setState already landed, incorrectly reverting the UI back
    // to a loading spinner over content that already successfully
    // loaded. Promise.resolve().then(...) defers to a microtask instead,
    // which still satisfies the "don't setState synchronously in an
    // effect" rule while staying correctly ordered before the fetch's
    // own microtask-based resolution.
    Promise.resolve().then(() => {
      setState("loading");
      setSelectedElement(null); // a stale spec from the previous discipline/floor must not linger
    });
    studioApi.getDisciplineOverlay(discipline, rooms, plotLengthFt, plotWidthFt, totalFloors)
      .then((data) => {
        setOverlay(data);
        setState("done");
      })
      .catch(() => setState("error"));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- roomsKey is the intentional, stable stand-in for rooms' actual content
  }, [discipline, plotLengthFt, plotWidthFt, roomsKey, totalFloors]);

  if (!plotLengthFt || !plotWidthFt) return null;

  const padding = 20;
  const viewW = plotLengthFt + padding * 2;
  const viewH = plotWidthFt + padding * 2;
  const validRooms = rooms.filter((r) => r.name.trim() && r.length > 0 && r.width > 0);
  const showFloorTabs = floors.length > 1;

  return (
    <div className="discipline-overlay-view">
      {showFloorTabs && (
        <div className="discipline-overlay-floor-tabs">
          {floors.map((floor, i) => (
            <button
              key={floor.floor_id || i}
              type="button"
              className={`discipline-overlay-floor-tab ${floorIndex === i ? "discipline-overlay-floor-tab-active" : ""}`}
              onClick={() => setFloorIndex(i)}
            >
              {floor.floor_label || `Floor ${floor.floor_number}`}
            </button>
          ))}
        </div>
      )}

      <div className="discipline-overlay-toggle">
        {DISCIPLINES.map((d) => (
          <button
            key={d.id}
            type="button"
            className={`discipline-overlay-toggle-btn ${discipline === d.id ? "discipline-overlay-toggle-active" : ""}`}
            onClick={() => setDiscipline(d.id)}
          >
            {d.label}
          </button>
        ))}

        <span className="discipline-overlay-toolbar-spacer" />

        <button type="button" className="discipline-overlay-zoom-btn" onClick={() => setZoom((z) => clampZoom(z + 0.15))} title="Zoom in">＋</button>
        <button type="button" className="discipline-overlay-zoom-btn" onClick={() => setZoom((z) => clampZoom(z - 0.15))} title="Zoom out">－</button>
        <button type="button" className="discipline-overlay-zoom-btn" onClick={() => setZoom(1)} title="Reset view">Fit</button>
      </div>

      {state === "loading" && <p className="studio-subtext">Loading {discipline} overlay...</p>}
      {state === "error" && <p className="studio-subtext">Couldn't load this overlay right now — please try again.</p>}

      {state === "done" && overlay && overlay.discipline === discipline && (
        <>
          <div className="discipline-overlay-legend">
            {overlay.legend.map((entry) => (
              <span key={entry.key} className="discipline-overlay-legend-item">
                <span className="discipline-overlay-legend-swatch" style={{ background: entry.color }} />
                {entry.label}
              </span>
            ))}
          </div>

          <div className="discipline-overlay-canvas-wrap">
            {/* North is always "up" in this app's plot coordinate convention
                (same as RoomCanvas.jsx's own compass), so this is static,
                not rotated to match anything. Positioned as a plain
                overlay outside the zoomed SVG so it stays fixed in the
                corner rather than zooming/panning along with the drawing
                — same reasoning as RoomCanvas.jsx's own compass. */}
            <svg className="discipline-overlay-compass" viewBox="0 0 56 56" xmlns="http://www.w3.org/2000/svg">
              <circle cx="28" cy="28" r="26" fill="white" stroke="#d1d5db" strokeWidth="1.5" />
              <polygon points="28,8 32,28 28,24 24,28" fill="#4c1d95" />
              <polygon points="28,48 32,28 28,32 24,28" fill="#9ca3af" />
              <text x="28" y="16" textAnchor="middle" fontSize="10" fontWeight="700" fill="#111827">N</text>
              <text x="46" y="31" textAnchor="middle" fontSize="9" fill="#6b7280">E</text>
              <text x="28" y="45" textAnchor="middle" fontSize="9" fill="#6b7280">S</text>
              <text x="10" y="31" textAnchor="middle" fontSize="9" fill="#6b7280">W</text>
            </svg>

            <svg
              viewBox={`${-padding} ${-padding} ${viewW} ${viewH}`}
              preserveAspectRatio="xMidYMid meet"
              className="discipline-overlay-svg"
              style={{ transform: `scale(${zoom})` }}
            >
              {/* Base floor plan, faded — the "transparent overlay" backdrop every discipline draws over */}
              <rect x={0} y={0} width={plotLengthFt} height={plotWidthFt} fill="#f5f3ff" stroke="#c4b5fd" strokeWidth={0.4} opacity={0.5} />
              {validRooms.map((room) => {
                const rectY = flipY(room.y + room.width, plotWidthFt);
                return (
                  <g key={room._key} opacity={0.35}>
                    <rect x={room.x} y={rectY} width={room.length} height={room.width} fill="#ede9fe" stroke="#a78bfa" strokeWidth={0.3} />
                    <text x={room.x + room.length / 2} y={rectY + room.width / 2} fontSize={Math.min(2.2, room.width / 2, room.length / 4)} textAnchor="middle" dominantBaseline="middle" fill="#6b5f85">
                      {room.name}
                    </text>
                  </g>
                );
              })}

              {/* Structural overlay */}
              {discipline === "structural" && (
                <>
                  {overlay.walls.map((wall, i) => (
                    <rect
                      key={`wall-${i}`}
                      x={wall.x}
                      y={flipY(wall.y + wall.width, plotWidthFt)}
                      width={wall.length}
                      height={wall.width}
                      fill="none"
                      stroke={legendColor(overlay.legend, wall.kind === "perimeter" ? "perimeter_wall" : "partition_wall")}
                      strokeWidth={wall.kind === "perimeter" ? 0.8 : 0.6}
                    />
                  ))}
                  {overlay.beams.map((beam) => (
                    <line
                      key={beam.label}
                      x1={beam.x} y1={flipY(beam.y, plotWidthFt)}
                      x2={beam.x2} y2={flipY(beam.y2, plotWidthFt)}
                      stroke={legendColor(overlay.legend, "beam")} strokeWidth={0.45} strokeDasharray="0.6,0.6"
                      onClick={() => setSelectedElement(beam)}
                      style={{ cursor: "pointer" }}
                    />
                  ))}
                  {overlay.columns.map((col) => (
                    <g key={col.label}>
                      <rect
                        x={col.x - 0.6} y={flipY(col.y, plotWidthFt) - 0.6} width={1.2} height={1.2}
                        fill={legendColor(overlay.legend, "column")}
                        onClick={() => setSelectedElement(col)} style={{ cursor: "pointer" }}
                      />
                      <ElementLabel x={col.x} y={col.y} plotWidthFt={plotWidthFt} text={col.label} onClick={() => setSelectedElement(col)} />
                    </g>
                  ))}
                </>
              )}

              {/* Plumbing overlay */}
              {discipline === "plumbing" && (
                <>
                  {overlay.pipe_runs.map((run, i) => (
                    <line
                      key={i}
                      x1={run.from.x} y1={flipY(run.from.y, plotWidthFt)}
                      x2={run.to.x} y2={flipY(run.to.y, plotWidthFt)}
                      stroke={legendColor(overlay.legend, "pipe_run")} strokeWidth={0.5} strokeDasharray="1.2,0.8"
                    />
                  ))}
                  {overlay.fixtures.map((f) => (
                    <g key={f.label}>
                      <circle
                        cx={f.x} cy={flipY(f.y, plotWidthFt)} r={0.8}
                        fill={legendColor(overlay.legend, "fixture")}
                        onClick={() => setSelectedElement(f)} style={{ cursor: "pointer" }}
                      />
                      <ElementLabel x={f.x} y={f.y} plotWidthFt={plotWidthFt} text={f.label} onClick={() => setSelectedElement(f)} />
                    </g>
                  ))}
                  {overlay.main_riser && (
                    <g>
                      <rect
                        x={overlay.main_riser.x - 0.7} y={flipY(overlay.main_riser.y, plotWidthFt) - 0.7}
                        width={1.4} height={1.4} fill={legendColor(overlay.legend, "main_riser")}
                        onClick={() => setSelectedElement(overlay.main_riser)} style={{ cursor: "pointer" }}
                      />
                      <ElementLabel x={overlay.main_riser.x} y={overlay.main_riser.y} plotWidthFt={plotWidthFt} text={overlay.main_riser.label} onClick={() => setSelectedElement(overlay.main_riser)} />
                    </g>
                  )}
                </>
              )}

              {/* Electrical overlay */}
              {discipline === "electrical" && (
                <>
                  {overlay.sockets.map((s) => (
                    <g key={s.label}>
                      <rect
                        x={s.x - 0.3} y={flipY(s.y, plotWidthFt) - 0.3} width={0.6} height={0.6}
                        fill={legendColor(overlay.legend, "socket")}
                        onClick={() => setSelectedElement(s)} style={{ cursor: "pointer" }}
                      />
                      <ElementLabel x={s.x} y={s.y} plotWidthFt={plotWidthFt} text={s.label} onClick={() => setSelectedElement(s)} />
                    </g>
                  ))}
                  {overlay.switches.map((s) => (
                    <g key={s.label}>
                      <rect
                        x={s.x - 0.4} y={flipY(s.y, plotWidthFt) - 0.4} width={0.8} height={0.8}
                        fill={legendColor(overlay.legend, "switch")}
                        onClick={() => setSelectedElement(s)} style={{ cursor: "pointer" }}
                      />
                      <ElementLabel x={s.x} y={s.y} plotWidthFt={plotWidthFt} text={s.label} onClick={() => setSelectedElement(s)} />
                    </g>
                  ))}
                  {overlay.fans.map((f) => {
                    // A fan-blade cross, distinct from the light's plain
                    // circle outline below, so the two markers (which
                    // sit close together in the same room) are easy to
                    // tell apart at a glance.
                    const fanColor = legendColor(overlay.legend, "fan");
                    return (
                      <g key={f.label} onClick={() => setSelectedElement(f)} style={{ cursor: "pointer" }}>
                        <circle cx={f.x} cy={flipY(f.y, plotWidthFt)} r={0.9} fill="none" stroke={fanColor} strokeWidth={0.35} />
                        <line x1={f.x - 0.9} y1={flipY(f.y, plotWidthFt)} x2={f.x + 0.9} y2={flipY(f.y, plotWidthFt)} stroke={fanColor} strokeWidth={0.3} />
                        <line x1={f.x} y1={flipY(f.y, plotWidthFt) - 0.9} x2={f.x} y2={flipY(f.y, plotWidthFt) + 0.9} stroke={fanColor} strokeWidth={0.3} />
                        <ElementLabel x={f.x} y={f.y} plotWidthFt={plotWidthFt} text={f.label} onClick={() => setSelectedElement(f)} />
                      </g>
                    );
                  })}
                  {overlay.lights.map((l) => (
                    <g key={l.label}>
                      <circle
                        cx={l.x} cy={flipY(l.y, plotWidthFt)} r={0.6} fill="none"
                        stroke={legendColor(overlay.legend, "light")} strokeWidth={0.4}
                        onClick={() => setSelectedElement(l)} style={{ cursor: "pointer" }}
                      />
                      <ElementLabel x={l.x} y={l.y} plotWidthFt={plotWidthFt} text={l.label} onClick={() => setSelectedElement(l)} />
                    </g>
                  ))}
                </>
              )}
            </svg>
          </div>

          {selectedElement && (
            <div className="discipline-overlay-spec-panel">
              <div className="discipline-overlay-spec-header">
                <strong>{selectedElement.label}</strong>
                <button type="button" className="discipline-overlay-spec-close" onClick={() => setSelectedElement(null)} aria-label="Close">×</button>
              </div>
              <p className="discipline-overlay-spec-text">{selectedElement.spec}</p>
            </div>
          )}

          <p className="discipline-overlay-disclaimer">⚠️ {overlay.disclaimer}</p>
        </>
      )}
    </div>
  );
}

export default DisciplineOverlayView;
