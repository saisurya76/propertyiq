import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { Stage, Layer, Rect, Text, Line, Transformer, Group } from "react-konva";

const BASE_CANVAS_WIDTH = 640;
const ROAD_SIDE_OFFSET = 14;
const GRID_STEP_FT = 2; // grid line every 2ft
const SNAP_FT = 0.5; // rooms snap to the nearest 0.5ft on drag/resize
const EDGE_SNAP_PX = 6; // snap-to-other-room edge alignment threshold, in screen px (pre-zoom)
const MIN_ROOM_FT = 3; // smallest a room can be resized to

function snap(value, step) {
  return Math.round(value / step) * step;
}

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
 * Enterprise-style 2D floor planner: drag-to-position, resize via corner
 * handles, zoom/pan, grid + snap-to-grid, snap-to-other-room edge guides,
 * rubber-band multi-select, and delete. Rooms stay axis-aligned by design
 * (no rotation) — the backend's Vastu zone math and DXF export both assume
 * plain, unrotated rectangles, and extending that is a materially bigger
 * change than this pass covers.
 *
 * Coordinates: feet, origin bottom-left, y increasing north — same
 * convention as the backend/DXF export. Canvas y grows downward, so this
 * component handles that flip internally; callers only ever see feet.
 */
function RoomCanvas({
  plotLengthFt,
  plotWidthFt,
  roadFacingSide,
  rooms,
  onRoomsChange,
  selectedKeys,
  onSelectionChange,
}) {
  const [zoom, setZoom] = useState(1);
  const [stagePos, setStagePos] = useState({ x: 0, y: 0 });
  const [panMode, setPanMode] = useState(false);
  const [guides, setGuides] = useState([]); // transient alignment guide lines, cleared after drag/resize
  const [selectionRect, setSelectionRect] = useState(null); // transient rubber-band box
  const stageRef = useRef(null);
  const transformerRef = useRef(null);
  const shapeRefs = useRef({});

  const hasValidPlot = Boolean(plotLengthFt) && Boolean(plotWidthFt);
  // Guarded fallbacks so hooks below never divide by zero/undefined —
  // the actual bail-out happens at the very end, after every hook has run,
  // never before (calling hooks conditionally breaks React's hook order).
  const safeLengthFt = plotLengthFt || 1;
  const safeWidthFt = plotWidthFt || 1;

  const baseScale = BASE_CANVAS_WIDTH / safeLengthFt;
  const canvasWidth = safeLengthFt * baseScale;
  const canvasHeight = safeWidthFt * baseScale;
  const roadPoints = roadLinePoints(roadFacingSide, canvasWidth, canvasHeight);

  const placedRooms = useMemo(
    () => rooms.filter((r) => r.name.trim() && r.length > 0 && r.width > 0),
    [rooms]
  );

  // Konva's Transformer must be attached to a live shape node imperatively
  // (via an effect), not by reading a ref's .current value inline during
  // render — React 19 flags that as unsafe.
  useEffect(() => {
    if (!transformerRef.current) return;
    const node = selectedKeys.length === 1 ? shapeRefs.current[selectedKeys[0]] : null;
    transformerRef.current.nodes(node ? [node] : []);
    transformerRef.current.getLayer()?.batchDraw();
  }, [selectedKeys, placedRooms]);

  // ---- feet <-> canvas-pixel conversion (pre-zoom "base" pixels) ----
  const feetToCanvas = (room) => ({
    x: room.x * baseScale,
    y: (safeWidthFt - room.y - room.width) * baseScale,
    width: room.length * baseScale,
    height: room.width * baseScale,
  });

  const canvasToFeet = (canvasX, canvasY, widthPx, heightPx) => ({
    x: snap(canvasX / baseScale, SNAP_FT),
    y: snap(safeWidthFt - canvasY / baseScale - heightPx / baseScale, SNAP_FT),
    length: snap(widthPx / baseScale, SNAP_FT),
    width: snap(heightPx / baseScale, SNAP_FT),
  });

  // ---- grid lines ----
  const gridLines = useMemo(() => {
    const lines = [];
    for (let ft = 0; ft <= safeLengthFt; ft += GRID_STEP_FT) {
      const x = ft * baseScale;
      lines.push({ key: `v${ft}`, points: [x, 0, x, canvasHeight] });
    }
    for (let ft = 0; ft <= safeWidthFt; ft += GRID_STEP_FT) {
      const y = ft * baseScale;
      lines.push({ key: `h${ft}`, points: [0, y, canvasWidth, y] });
    }
    return lines;
  }, [safeLengthFt, safeWidthFt, baseScale, canvasWidth, canvasHeight]);

  // ---- zoom controls ----
  const clampZoom = (z) => Math.max(0.4, Math.min(3, z));

  const handleWheel = (e) => {
    e.evt.preventDefault();
    const stage = stageRef.current;
    const pointer = stage.getPointerPosition();
    const oldScale = zoom;
    const direction = e.evt.deltaY > 0 ? -1 : 1;
    const newScale = clampZoom(oldScale + direction * 0.1);

    const mousePointTo = {
      x: (pointer.x - stagePos.x) / oldScale,
      y: (pointer.y - stagePos.y) / oldScale,
    };
    setStagePos({
      x: pointer.x - mousePointTo.x * newScale,
      y: pointer.y - mousePointTo.y * newScale,
    });
    setZoom(newScale);
  };

  const zoomBy = (delta) => setZoom((z) => clampZoom(z + delta));
  const resetView = () => {
    setZoom(1);
    setStagePos({ x: 0, y: 0 });
  };

  // ---- selection ----
  const toggleSelect = (key, additive) => {
    if (additive) {
      onSelectionChange(
        selectedKeys.includes(key) ? selectedKeys.filter((k) => k !== key) : [...selectedKeys, key]
      );
    } else {
      onSelectionChange([key]);
    }
  };

  const handleStageMouseDown = (e) => {
    if (panMode) return;
    // Clicking empty canvas starts a rubber-band selection; clicking a
    // shape is handled by that shape's own onClick instead.
    if (e.target === e.target.getStage()) {
      const pos = e.target.getStage().getRelativePointerPosition();
      setSelectionRect({ x1: pos.x, y1: pos.y, x2: pos.x, y2: pos.y });
      onSelectionChange([]);
    }
  };

  const handleStageMouseMove = (e) => {
    if (!selectionRect) return;
    const pos = e.target.getStage().getRelativePointerPosition();
    setSelectionRect((r) => ({ ...r, x2: pos.x, y2: pos.y }));
  };

  const handleStageMouseUp = () => {
    if (!selectionRect) return;
    const x1 = Math.min(selectionRect.x1, selectionRect.x2);
    const x2 = Math.max(selectionRect.x1, selectionRect.x2);
    const y1 = Math.min(selectionRect.y1, selectionRect.y2);
    const y2 = Math.max(selectionRect.y1, selectionRect.y2);

    const hits = placedRooms.filter((room) => {
      const { x, y, width, height } = feetToCanvas(room);
      return x < x2 && x + width > x1 && y < y2 && y + height > y1;
    });

    if (hits.length > 0) onSelectionChange(hits.map((r) => r._key));
    setSelectionRect(null);
  };

  // ---- edge snapping against other rooms (drag) ----
  const computeEdgeSnap = (movingKey, proposedX, proposedY, widthPx, heightPx) => {
    let snappedX = proposedX;
    let snappedY = proposedY;
    const newGuides = [];

    for (const other of placedRooms) {
      if (other._key === movingKey) continue;
      const o = feetToCanvas(other);

      // Vertical alignment: left-left, left-right, right-left, right-right
      const myLeft = proposedX, myRight = proposedX + widthPx;
      const otherLeft = o.x, otherRight = o.x + o.width;
      for (const [mine, theirs] of [[myLeft, otherLeft], [myLeft, otherRight], [myRight, otherLeft], [myRight, otherRight]]) {
        if (Math.abs(mine - theirs) < EDGE_SNAP_PX) {
          snappedX = proposedX + (theirs - mine);
          newGuides.push({ points: [theirs, 0, theirs, canvasHeight], key: `vg-${other._key}` });
        }
      }

      // Horizontal alignment: top-top, top-bottom, bottom-top, bottom-bottom
      const myTop = proposedY, myBottom = proposedY + heightPx;
      const otherTop = o.y, otherBottom = o.y + o.height;
      for (const [mine, theirs] of [[myTop, otherTop], [myTop, otherBottom], [myBottom, otherTop], [myBottom, otherBottom]]) {
        if (Math.abs(mine - theirs) < EDGE_SNAP_PX) {
          snappedY = proposedY + (theirs - mine);
          newGuides.push({ points: [0, theirs, canvasWidth, theirs], key: `hg-${other._key}` });
        }
      }
    }

    return { snappedX, snappedY, newGuides };
  };

  const handleDragMove = (room, e) => {
    const { width, height } = feetToCanvas(room);
    const { snappedX, snappedY, newGuides } = computeEdgeSnap(room._key, e.target.x(), e.target.y(), width, height);
    e.target.x(snappedX);
    e.target.y(snappedY);
    setGuides(newGuides);
  };

  const handleDragEnd = (room, e) => {
    setGuides([]);
    const { x, y } = canvasToFeet(e.target.x(), e.target.y(), 0, feetToCanvas(room).height);
    const updated = rooms.map((r) => (r._key === room._key ? { ...r, x, y } : r));
    onRoomsChange(updated);
  };

  const handleTransformEnd = (room, e) => {
    const node = e.target;
    const scaleX = node.scaleX();
    const scaleY = node.scaleY();
    node.scaleX(1);
    node.scaleY(1);

    const newWidthPx = Math.max(MIN_ROOM_FT * baseScale, node.width() * scaleX);
    const newHeightPx = Math.max(MIN_ROOM_FT * baseScale, node.height() * scaleY);

    const { x, y, length, width } = canvasToFeet(node.x(), node.y(), newWidthPx, newHeightPx);
    const updated = rooms.map((r) => (r._key === room._key ? { ...r, x, y, length, width } : r));
    onRoomsChange(updated);
  };

  if (!hasValidPlot) return null;

  return (
    <div className="room-canvas-wrap">
      <div className="room-canvas-toolbar">
        <button type="button" className="rc-tool-btn" onClick={() => zoomBy(0.15)} title="Zoom in">＋</button>
        <button type="button" className="rc-tool-btn" onClick={() => zoomBy(-0.15)} title="Zoom out">－</button>
        <button type="button" className="rc-tool-btn" onClick={resetView} title="Reset view">Fit</button>
        <button
          type="button"
          className={`rc-tool-btn ${panMode ? "rc-tool-btn-active" : ""}`}
          onClick={() => setPanMode((p) => !p)}
          title="Pan mode"
        >
          ✋ Pan
        </button>
        <span className="rc-tool-hint">
          {panMode ? "Drag to pan the canvas" : "Drag rooms to move · drag corners to resize · drag empty space to select multiple"}
        </span>
      </div>

      <Stage
        ref={stageRef}
        width={canvasWidth + 2 * ROAD_SIDE_OFFSET}
        height={canvasHeight + 2 * ROAD_SIDE_OFFSET}
        offsetX={-ROAD_SIDE_OFFSET}
        offsetY={-ROAD_SIDE_OFFSET}
        scaleX={zoom}
        scaleY={zoom}
        x={stagePos.x}
        y={stagePos.y}
        draggable={panMode}
        onWheel={handleWheel}
        onMouseDown={handleStageMouseDown}
        onMouseMove={handleStageMouseMove}
        onMouseUp={handleStageMouseUp}
      >
        <Layer>
          <Rect x={0} y={0} width={canvasWidth} height={canvasHeight} fill="#f5f3ff" stroke="#7c3aed" strokeWidth={1.5} />

          {gridLines.map((line) => (
            <Line key={line.key} points={line.points} stroke="#e9e4fb" strokeWidth={1} listening={false} />
          ))}

          {roadPoints && <Line points={roadPoints} stroke="#9ca3af" strokeWidth={1.5} dash={[5, 4]} listening={false} />}

          {guides.map((g) => (
            <Line key={g.key} points={g.points} stroke="#ec4899" strokeWidth={1} dash={[4, 3]} listening={false} />
          ))}

          {placedRooms.map((room) => {
            const { x, y, width, height } = feetToCanvas(room);
            const isSelected = selectedKeys.includes(room._key);

            return (
              <Fragment key={room._key}>
                <Group>
                  <Rect
                    ref={(node) => {
                      if (node) shapeRefs.current[room._key] = node;
                    }}
                    x={x}
                    y={y}
                    width={width}
                    height={height}
                    fill={room.color || "#ede9fe"}
                    stroke={isSelected ? "#4c1d95" : "#a78bfa"}
                    strokeWidth={isSelected ? 2.5 : 1}
                    draggable={!panMode}
                    dragBoundFunc={(pos) => ({
                      x: Math.max(0, Math.min(pos.x, canvasWidth - width)),
                      y: Math.max(0, Math.min(pos.y, canvasHeight - height)),
                    })}
                    onDragMove={(e) => handleDragMove(room, e)}
                    onDragEnd={(e) => handleDragEnd(room, e)}
                    onTransformEnd={(e) => handleTransformEnd(room, e)}
                    onClick={(e) => toggleSelect(room._key, e.evt.shiftKey)}
                    onTap={() => toggleSelect(room._key, false)}
                  />
                  <Text
                    x={x}
                    y={y + height / 2 - 14}
                    width={width}
                    align="center"
                    text={room.name}
                    fontSize={12}
                    fontStyle="600"
                    fill="#4c1d95"
                    listening={false}
                  />
                  <Text
                    x={x}
                    y={y + height / 2 + 2}
                    width={width}
                    align="center"
                    text={`${room.length}' × ${room.width}'`}
                    fontSize={10}
                    fill="#7c6a99"
                    listening={false}
                  />
                </Group>
              </Fragment>
            );
          })}

          <Transformer
            ref={transformerRef}
            rotateEnabled={false}
            enabledAnchors={["top-left", "top-right", "bottom-left", "bottom-right"]}
            boundBoxFunc={(oldBox, newBox) => {
              if (newBox.width < MIN_ROOM_FT * baseScale || newBox.height < MIN_ROOM_FT * baseScale) {
                return oldBox;
              }
              return newBox;
            }}
          />

          {selectionRect && (
            <Rect
              x={Math.min(selectionRect.x1, selectionRect.x2)}
              y={Math.min(selectionRect.y1, selectionRect.y2)}
              width={Math.abs(selectionRect.x2 - selectionRect.x1)}
              height={Math.abs(selectionRect.y2 - selectionRect.y1)}
              fill="rgba(124, 58, 237, 0.1)"
              stroke="#7c3aed"
              strokeWidth={1}
              dash={[4, 3]}
              listening={false}
            />
          )}
        </Layer>
      </Stage>
    </div>
  );
}

export default RoomCanvas;
