import { Fragment } from "react";
import { Stage, Layer, Rect, Text, Line } from "react-konva";

const CANVAS_MAX_WIDTH = 640;

const ROAD_SIDE_OFFSET = 14;

function roadLinePoints(side, canvasWidth, canvasHeight) {
  switch ((side || "").toLowerCase()) {
    case "north":
    case "north-east":
    case "north-west":
      return [0, -ROAD_SIDE_OFFSET, canvasWidth, -ROAD_SIDE_OFFSET];
    case "south":
    case "south-east":
    case "south-west":
      return [0, canvasHeight + ROAD_SIDE_OFFSET, canvasWidth, canvasHeight + ROAD_SIDE_OFFSET];
    case "east":
      return [canvasWidth + ROAD_SIDE_OFFSET, 0, canvasWidth + ROAD_SIDE_OFFSET, canvasHeight];
    case "west":
      return [-ROAD_SIDE_OFFSET, 0, -ROAD_SIDE_OFFSET, canvasHeight];
    default:
      return null;
  }
}

/**
 * Interactive drag-to-position room layout editor. Coordinates follow the
 * same convention as the backend/DXF export (feet, origin bottom-left,
 * y increasing north) — this component just handles the pixel<->feet
 * conversion and the canvas-native y-flip (canvas y grows downward).
 */
function RoomCanvas({ plotLengthFt, plotWidthFt, roadFacingSide, rooms, onRoomDrag, selectedKey, onSelectRoom }) {
  if (!plotLengthFt || !plotWidthFt) return null;

  const scale = CANVAS_MAX_WIDTH / plotLengthFt;
  const canvasWidth = plotLengthFt * scale;
  const canvasHeight = plotWidthFt * scale;
  const roadPoints = roadLinePoints(roadFacingSide, canvasWidth, canvasHeight);

  const placedRooms = rooms.filter((r) => r.name.trim() && r.length > 0 && r.width > 0);

  return (
    <div className="room-canvas-wrap">
      <Stage width={canvasWidth + 2 * ROAD_SIDE_OFFSET} height={canvasHeight + 2 * ROAD_SIDE_OFFSET} offsetX={-ROAD_SIDE_OFFSET} offsetY={-ROAD_SIDE_OFFSET}>
        <Layer>
          <Rect x={0} y={0} width={canvasWidth} height={canvasHeight} fill="#f5f3ff" stroke="#7c3aed" strokeWidth={1.5} />

          {roadPoints && (
            <Line points={roadPoints} stroke="#9ca3af" strokeWidth={1.5} dash={[5, 4]} />
          )}

          {placedRooms.map((room) => {
            const rectWidthPx = room.length * scale;
            const rectHeightPx = room.width * scale;
            const rectX = room.x * scale;
            const rectY = (plotWidthFt - room.y - room.width) * scale;
            const isSelected = room._key === selectedKey;

            return (
              <Fragment key={room._key}>
                <Rect
                  x={rectX}
                  y={rectY}
                  width={rectWidthPx}
                  height={rectHeightPx}
                  fill={room.color || "#ede9fe"}
                  stroke={isSelected ? "#4c1d95" : "#a78bfa"}
                  strokeWidth={isSelected ? 2.5 : 1}
                  draggable
                  dragBoundFunc={(pos) => ({
                    x: Math.max(0, Math.min(pos.x, canvasWidth - rectWidthPx)),
                    y: Math.max(0, Math.min(pos.y, canvasHeight - rectHeightPx)),
                  })}
                  onDragStart={() => onSelectRoom(room._key)}
                  onDragEnd={(e) => {
                    const newXft = Math.round((e.target.x() / scale) * 10) / 10;
                    const newYft = Math.round((plotWidthFt - e.target.y() / scale - room.width) * 10) / 10;
                    onRoomDrag(room._key, newXft, newYft);
                  }}
                  onClick={() => onSelectRoom(room._key)}
                  onTap={() => onSelectRoom(room._key)}
                />
                <Text
                  x={rectX}
                  y={rectY + rectHeightPx / 2 - 7}
                  width={rectWidthPx}
                  align="center"
                  text={room.name}
                  fontSize={12}
                  fontStyle="600"
                  fill="#4c1d95"
                  listening={false}
                />
              </Fragment>
            );
          })}
        </Layer>
      </Stage>
    </div>
  );
}

export default RoomCanvas;
