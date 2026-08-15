const ROAD_OFFSET = 4;

function roadLine(side, lengthFt, widthFt) {
  switch (side) {
    case "north":
    case "north-east":
    case "north-west":
      return { x1: 0, y1: widthFt + ROAD_OFFSET, x2: lengthFt, y2: widthFt + ROAD_OFFSET };
    case "south":
    case "south-east":
    case "south-west":
      return { x1: 0, y1: -ROAD_OFFSET, x2: lengthFt, y2: -ROAD_OFFSET };
    case "east":
      return { x1: lengthFt + ROAD_OFFSET, y1: 0, x2: lengthFt + ROAD_OFFSET, y2: widthFt };
    case "west":
      return { x1: -ROAD_OFFSET, y1: 0, x2: -ROAD_OFFSET, y2: widthFt };
    default:
      return null;
  }
}

// SVG y-axis grows downward, but our plot convention (matching the DXF
// export) treats y as south(0) -> north(+). Flip y when drawing so "north"
// visually renders at the top, matching how people actually read a plot.
function flipY(y, widthFt) {
  return widthFt - y;
}

function PlotPreview({ plotLengthFt, plotWidthFt, roadFacingSide, rooms }) {
  if (!plotLengthFt || !plotWidthFt) return null;

  const padding = 20;
  const viewW = plotLengthFt + padding * 2;
  const viewH = plotWidthFt + padding * 2;
  const road = roadLine(roadFacingSide, plotLengthFt, plotWidthFt);

  return (
    <div className="plot-preview">
      <div className="plot-preview-label">Live plot preview</div>
      <svg
        viewBox={`${-padding} ${-padding} ${viewW} ${viewH}`}
        preserveAspectRatio="xMidYMid meet"
        className="plot-preview-svg"
      >
        {/* Plot boundary */}
        <rect
          x={0}
          y={0}
          width={plotLengthFt}
          height={plotWidthFt}
          fill="#f5f3ff"
          stroke="#7c3aed"
          strokeWidth={0.6}
        />

        {/* Road-facing side marker */}
        {road && (
          <line
            x1={road.x1}
            y1={flipY(road.y1, plotWidthFt)}
            x2={road.x2}
            y2={flipY(road.y2, plotWidthFt)}
            stroke="#9ca3af"
            strokeWidth={1.2}
            strokeDasharray="2,1.5"
          />
        )}

        {/* Rooms */}
        {rooms
          .filter((r) => r.name.trim() && r.length > 0 && r.width > 0)
          .map((room) => {
            const rectY = flipY(room.y + room.width, plotWidthFt);
            return (
              <g key={room._key}>
                <rect
                  x={room.x}
                  y={rectY}
                  width={room.length}
                  height={room.width}
                  fill="#ede9fe"
                  stroke="#a78bfa"
                  strokeWidth={0.4}
                />
                <text
                  x={room.x + room.length / 2}
                  y={rectY + room.width / 2}
                  fontSize={Math.min(2.6, room.width / 2, room.length / 4)}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fill="#4c1d95"
                >
                  {room.name}
                </text>
              </g>
            );
          })}
      </svg>
      <div className="plot-preview-meta">
        {plotLengthFt}ft × {plotWidthFt}ft
        {road && " · road side shown as dashed line"}
      </div>
    </div>
  );
}

export default PlotPreview;
