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

// Three separate, transparent overlay layouts drawn over the exact same
// room footprint as the live floor plan — one discipline shown at a
// time via the toggle below. See discipline_overlays.py's own docstring
// for the critical honesty boundary every result here carries: this is
// a SCHEMATIC visualization aid, not a licensed engineer's calculated
// design — the disclaimer returned by the backend is always shown
// prominently, never hidden or shortened.
function DisciplineOverlayView({ plotLengthFt, plotWidthFt, rooms }) {
  const [discipline, setDiscipline] = useState("structural");
  const [overlay, setOverlay] = useState(null);
  const [state, setState] = useState("idle"); // "idle" | "loading" | "done" | "error"

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
    Promise.resolve().then(() => setState("loading"));
    studioApi.getDisciplineOverlay(discipline, rooms, plotLengthFt, plotWidthFt)
      .then((data) => {
        setOverlay(data);
        setState("done");
      })
      .catch(() => setState("error"));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- roomsKey is the intentional, stable stand-in for rooms' actual content
  }, [discipline, plotLengthFt, plotWidthFt, roomsKey]);

  if (!plotLengthFt || !plotWidthFt) return null;

  const padding = 20;
  const viewW = plotLengthFt + padding * 2;
  const viewH = plotWidthFt + padding * 2;
  const validRooms = rooms.filter((r) => r.name.trim() && r.length > 0 && r.width > 0);

  return (
    <div className="discipline-overlay-view">
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
      </div>

      {state === "loading" && <p className="studio-subtext">Loading {discipline} overlay...</p>}
      {state === "error" && <p className="studio-subtext">Couldn't load this overlay right now — please try again.</p>}

      {state === "done" && overlay && overlay.discipline === discipline && (
        <>
          <svg
            viewBox={`${-padding} ${-padding} ${viewW} ${viewH}`}
            preserveAspectRatio="xMidYMid meet"
            className="discipline-overlay-svg"
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
                    key={i}
                    x={wall.x}
                    y={flipY(wall.y + wall.width, plotWidthFt)}
                    width={wall.length}
                    height={wall.width}
                    fill="none"
                    stroke={wall.kind === "perimeter" ? "#dc2626" : "#f59e0b"}
                    strokeWidth={wall.kind === "perimeter" ? 0.8 : 0.6}
                  />
                ))}
                {overlay.columns.map((col, i) => (
                  <rect
                    key={i}
                    x={col.x - 0.6}
                    y={flipY(col.y, plotWidthFt) - 0.6}
                    width={1.2}
                    height={1.2}
                    fill="#dc2626"
                  />
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
                    stroke="#2563eb" strokeWidth={0.5} strokeDasharray="1.2,0.8"
                  />
                ))}
                {overlay.fixtures.map((f, i) => (
                  <circle key={i} cx={f.x} cy={flipY(f.y, plotWidthFt)} r={0.8} fill="#2563eb" />
                ))}
                {overlay.main_riser && (
                  <rect
                    x={overlay.main_riser.x - 0.7} y={flipY(overlay.main_riser.y, plotWidthFt) - 0.7}
                    width={1.4} height={1.4} fill="#1e3a8a"
                  />
                )}
              </>
            )}

            {/* Electrical overlay */}
            {discipline === "electrical" && (
              <>
                {overlay.sockets.map((s, i) => (
                  <rect key={i} x={s.x - 0.3} y={flipY(s.y, plotWidthFt) - 0.3} width={0.6} height={0.6} fill="#059669" />
                ))}
                {overlay.switches.map((s, i) => (
                  <rect key={i} x={s.x - 0.4} y={flipY(s.y, plotWidthFt) - 0.4} width={0.8} height={0.8} fill="#d97706" />
                ))}
                {overlay.lights.map((l, i) => (
                  <circle key={i} cx={l.x} cy={flipY(l.y, plotWidthFt)} r={0.9} fill="none" stroke="#d97706" strokeWidth={0.4} />
                ))}
              </>
            )}
          </svg>

          <p className="discipline-overlay-disclaimer">⚠️ {overlay.disclaimer}</p>
        </>
      )}
    </div>
  );
}

export default DisciplineOverlayView;
