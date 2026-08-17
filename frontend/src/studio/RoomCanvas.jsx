import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { Stage, Layer, Rect, Text, Line, Circle, RegularPolygon, Transformer, Group } from "react-konva";
import Konva from "konva";

const BASE_CANVAS_WIDTH = 640;
const ROAD_SIDE_OFFSET = 14;
const GRID_STEP_FT = 2; // grid line every 2ft
const SNAP_FT = 0.5; // rooms snap to the nearest 0.5ft on drag/resize
const EDGE_SNAP_PX = 6; // snap-to-other-room edge alignment threshold, in screen px (pre-zoom)
const MIN_ROOM_FT = 3; // smallest a room can be resized to
const WALL_THICKNESS_FT = 0.4; // ~5in interior partition wall

// Konva dash arrays per line style — solid uses `undefined` (Konva treats
// a missing dash prop as solid). Kept in sync with ConstructionStudio.jsx's
// copy of the same map.
const LINE_DASH_PATTERNS = {
  solid: undefined,
  dotted: [2, 3],
  dash: [8, 6],
  "dash-dot": [10, 4, 2, 4],
};
const EDGE_TOUCH_TOLERANCE_FT = 0.6; // how close to a plot edge counts as "touching" it for dimensioning
const DIM_LINE_OFFSET_PX = 22; // distance of the segmented dimension chain from the plot edge
const DIM_TOTAL_OFFSET_PX = 44; // distance of the overall-total dimension line, further out
const STAGE_MARGIN_PX = DIM_TOTAL_OFFSET_PX + 20; // canvas padding — must clear the outermost dimension + its label

function snap(value, step) {
  return Math.round(value / step) * step;
}

/**
 * Architectural-style dimension chain: finds every room touching the given
 * plot edge, collects their boundary positions along that edge, and
 * returns consecutive segments that span the FULL edge with no gaps or
 * overlaps — same convention as the segmented measurement chains in a
 * real architectural drawing (e.g. "3000 | 7000 | 1200 | 3000").
 */
function computeEdgeDimensionSegments(rooms, plotLengthFt, plotWidthFt, edge) {
  const fullSpan = edge === "north" ? plotLengthFt : plotWidthFt;
  const boundaries = new Set([0, fullSpan]);

  for (const room of rooms) {
    if (edge === "north") {
      const touches = Math.abs(room.y + room.width - plotWidthFt) < EDGE_TOUCH_TOLERANCE_FT;
      if (touches) {
        boundaries.add(Math.round(room.x * 10) / 10);
        boundaries.add(Math.round((room.x + room.length) * 10) / 10);
      }
    } else {
      const touches = Math.abs(room.x - 0) < EDGE_TOUCH_TOLERANCE_FT;
      if (touches) {
        boundaries.add(Math.round(room.y * 10) / 10);
        boundaries.add(Math.round((room.y + room.width) * 10) / 10);
      }
    }
  }

  const sorted = [...boundaries].sort((a, b) => a - b);
  const segments = [];
  for (let i = 0; i < sorted.length - 1; i++) {
    const start = sorted[i];
    const end = sorted[i + 1];
    if (end - start < 0.05) continue;
    segments.push({ start, end, length: Math.round((end - start) * 10) / 10 });
  }
  return segments;
}

function DimensionChain({ segments, edge, offsetPx, baseScale, plotWidthFt }) {
  if (!segments.length) return null;
  const tickHalf = 4;

  if (edge === "north") {
    const lineY = -offsetPx;
    const lastX = segments[segments.length - 1].end * baseScale;
    return (
      <Group listening={false}>
        {segments.map((seg, i) => {
          const x1 = seg.start * baseScale;
          const x2 = seg.end * baseScale;
          return (
            <Fragment key={i}>
              <Line points={[x1, lineY - tickHalf, x1, lineY + tickHalf]} stroke="#111827" strokeWidth={1} />
              <Line points={[x1, lineY, x2, lineY]} stroke="#111827" strokeWidth={1} />
              <Text x={x1} y={lineY - 13} width={x2 - x1} align="center" text={`${seg.length}'`} fontSize={9} fill="#111827" />
            </Fragment>
          );
        })}
        <Line points={[lastX, lineY - tickHalf, lastX, lineY + tickHalf]} stroke="#111827" strokeWidth={1} />
      </Group>
    );
  }

  // west edge: vertical chain. Segments are in feet, south-up (0=south,
  // plotWidthFt=north); canvas y grows downward, so flip each endpoint.
  const canvasYForFeet = (feetY) => (plotWidthFt - feetY) * baseScale;
  const lineX = -offsetPx;
  const allCanvasY = segments.flatMap((s) => [canvasYForFeet(s.start), canvasYForFeet(s.end)]);
  const extremeY = [Math.min(...allCanvasY), Math.max(...allCanvasY)];

  return (
    <Group listening={false}>
      {segments.map((seg, i) => {
        const y1 = canvasYForFeet(seg.start);
        const y2 = canvasYForFeet(seg.end);
        const midY = (y1 + y2) / 2;
        return (
          <Fragment key={i}>
            <Line points={[lineX - tickHalf, y1, lineX + tickHalf, y1]} stroke="#111827" strokeWidth={1} />
            <Line points={[lineX, y1, lineX, y2]} stroke="#111827" strokeWidth={1} />
            <Text
              x={lineX - 34}
              y={midY - 5}
              width={30}
              align="right"
              text={`${seg.length}'`}
              fontSize={9}
              fill="#111827"
            />
          </Fragment>
        );
      })}
      <Line points={[lineX - tickHalf, extremeY[0], lineX + tickHalf, extremeY[0]]} stroke="#111827" strokeWidth={1} />
      <Line points={[lineX - tickHalf, extremeY[1], lineX + tickHalf, extremeY[1]]} stroke="#111827" strokeWidth={1} />
    </Group>
  );
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
const LINE_TYPES = new Set(["line", "dotted_line"]);

// Rendering-relevant subset of ConstructionStudio.jsx's ELEMENT_DEFS —
// duplicated deliberately (not imported) so this lazy-loaded chunk stays
// self-contained. Keep in sync if element types change there.
const ELEMENT_DEFS_FOR_RENDER = {
  tree: { label: "Tree", color: "#86efac", symbol: "circle" },
  plant: { label: "Plant", color: "#bbf7d0", symbol: "circle" },
  gazebo: { label: "Gazebo", color: "#e7d4b5", symbol: "hexagon" },
  pool: { label: "Swimming Pool", color: "#7dd3fc", symbol: null, rounded: true },
  car: { label: "Car", color: "#cbd5e1", symbol: "car", rounded: true },
  pathway: { label: "Pathway", color: "#e7e5e4", symbol: null },
  bench: { label: "Bench", color: "#c4a484", symbol: null, rounded: true },
};

function RoomCanvas({
  plotLengthFt,
  plotWidthFt,
  roadFacingSide,
  rooms,
  onRoomsChange,
  siteElements = [],
  onElementsChange,
  selectedKeys,
  onSelectionChange,
  locked = false,
}) {
  const [zoom, setZoom] = useState(1);
  const [stagePos, setStagePos] = useState({ x: 0, y: 0 });
  const [panMode, setPanMode] = useState(false);
  const [selectionRect, setSelectionRect] = useState(null); // transient rubber-band box
  const stageRef = useRef(null);
  const transformerRef = useRef(null);
  const guideGroupRef = useRef(null); // alignment guide lines are drawn imperatively (not React
    // state) so they never trigger a re-render mid-drag — a re-render while
    // Konva has an active drag gesture in progress is a known source of the
    // shape fighting/snapping-back-to-stale-props during that gesture.
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

  const areaElements = useMemo(
    () => siteElements.filter((el) => !LINE_TYPES.has(el.type) && el.length > 0 && el.width > 0),
    [siteElements]
  );
  const lineElements = useMemo(() => siteElements.filter((el) => LINE_TYPES.has(el.type)), [siteElements]);

  // Konva's Transformer must be attached to a live shape node imperatively
  // (via an effect), not by reading a ref's .current value inline during
  // render — React 19 flags that as unsafe.
  useEffect(() => {
    if (!transformerRef.current) return;
    const node = selectedKeys.length === 1 ? shapeRefs.current[selectedKeys[0]] : null;
    transformerRef.current.nodes(node ? [node] : []);
    transformerRef.current.getLayer()?.batchDraw();
  }, [selectedKeys, placedRooms, areaElements]);

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

  // ---- architectural dimension chains (north edge along the top, west edge along the left) ----
  const northDimSegments = useMemo(
    () => computeEdgeDimensionSegments(placedRooms, safeLengthFt, safeWidthFt, "north"),
    [placedRooms, safeLengthFt, safeWidthFt]
  );
  const westDimSegments = useMemo(
    () => computeEdgeDimensionSegments(placedRooms, safeLengthFt, safeWidthFt, "west"),
    [placedRooms, safeLengthFt, safeWidthFt]
  );

  // dragBoundFunc must receive AND return positions in Konva's "absolute"
  // coordinate space (confirmed directly from Konva's own source — see
  // Node.js's _setDragPosition, which calls setAbsolutePosition() on
  // whatever dragBoundFunc returns). That is NOT the same as this shape's
  // local/model-space x/y whenever any ancestor (the Stage's zoom, pan, or
  // the STAGE_MARGIN_PX offset added for the dimension chains) applies a
  // transform — which they now do. Clamping the raw `pos` value directly
  // against local-space bounds, as this used to do, silently shifted the
  // drag boundary by exactly that transform's offset. This converts
  // absolute -> local, clamps in local space (where the bounds actually
  // make sense), then converts back — correct regardless of current zoom
  // or pan, since it reads the live transform rather than assuming it.
  function makeDragBoundFunc(width, height) {
    return function (pos) {
      const parentTransform = this.getParent().getAbsoluteTransform();
      const inverse = parentTransform.copy().invert();
      const local = inverse.point(pos);
      const clampedLocal = {
        x: Math.max(0, Math.min(local.x, canvasWidth - width)),
        y: Math.max(0, Math.min(local.y, canvasHeight - height)),
      };
      return parentTransform.point(clampedLocal);
    };
  }

  // Site elements use CENTER-pivot rotation (see the areaElements render
  // loop), so their drag-bound must clamp the CENTER position such that
  // the element's true ROTATED footprint — not its unrotated width/height —
  // never exceeds the plot. A rotated rectangle's axis-aligned bounding
  // half-extents are a standard, well-defined formula; using the plain
  // unrotated width/height here (as an earlier version did) is exactly
  // what let rotated elements (e.g. a rotated pool) visually escape the
  // plot boundary even though their nominal x/y stayed "in bounds".
  function makeElementDragBoundFunc(width, height, rotationDeg) {
    const hw = width / 2;
    const hh = height / 2;
    const theta = (rotationDeg * Math.PI) / 180;
    const c = Math.abs(Math.cos(theta));
    const s = Math.abs(Math.sin(theta));
    const boundHalfWidth = hw * c + hh * s;
    const boundHalfHeight = hw * s + hh * c;

    return function (pos) {
      const parentTransform = this.getParent().getAbsoluteTransform();
      const inverse = parentTransform.copy().invert();
      const local = inverse.point(pos); // this Group's local x/y IS its center
      const clampedLocal = {
        x: Math.max(boundHalfWidth, Math.min(local.x, canvasWidth - boundHalfWidth)),
        y: Math.max(boundHalfHeight, Math.min(local.y, canvasHeight - boundHalfHeight)),
      };
      return parentTransform.point(clampedLocal);
    };
  }

  // ---- zoom controls ----
  const clampZoom = (z) => Math.max(0.4, Math.min(3, z));

  const handleWheel = (e) => {
    e.evt.preventDefault();
    const stage = stageRef.current;
    const rawPointer = stage.getPointerPosition();
    const oldScale = zoom;
    const direction = e.evt.deltaY > 0 ? -1 : 1;
    const newScale = clampZoom(oldScale + direction * 0.1);

    // Same absolute-vs-local distinction as the dragBoundFunc fix above:
    // getPointerPosition() is raw container pixels, not the Stage's local
    // content coordinates. Convert via the Stage's OWN current transform
    // (which already accounts for STAGE_MARGIN_PX) so the point under the
    // cursor stays fixed while zooming, instead of drifting.
    const oldTransform = stage.getAbsoluteTransform().copy();
    const localPointUnderCursor = oldTransform.invert().point(rawPointer);

    setStagePos({
      x: rawPointer.x - (localPointUnderCursor.x + STAGE_MARGIN_PX) * newScale,
      y: rawPointer.y - (localPointUnderCursor.y + STAGE_MARGIN_PX) * newScale,
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

  // ---- multi-select group drag: moving any one selected shape moves all
  // other currently-selected shapes by the same delta. Works uniformly for
  // rooms (corner-anchored) and elements (center-anchored, post rotation
  // refactor) since a translation delta is agnostic to what the anchor
  // point represents — only the FINAL per-shape commit needs to know which
  // convention applies. ----
  const multiDragRef = useRef(null);

  const handleAnyDragStart = (key) => {
    if (selectedKeys.length > 1 && selectedKeys.includes(key)) {
      const startPositions = {};
      for (const k of selectedKeys) {
        const node = shapeRefs.current[k];
        if (node) startPositions[k] = { x: node.x(), y: node.y() };
      }
      multiDragRef.current = { anchorKey: key, startPositions };
    } else {
      multiDragRef.current = null;
    }
  };

  const applyMultiDragDelta = (anchorKey, e) => {
    const md = multiDragRef.current;
    if (!md || md.anchorKey !== anchorKey) return;
    const anchorStart = md.startPositions[anchorKey];
    const dx = e.target.x() - anchorStart.x;
    const dy = e.target.y() - anchorStart.y;
    for (const [key, start] of Object.entries(md.startPositions)) {
      if (key === anchorKey) continue;
      const node = shapeRefs.current[key];
      if (node) {
        node.x(start.x + dx);
        node.y(start.y + dy);
      }
    }
  };

  // Returns the OTHER selected keys that were moved (excluding the anchor,
  // which the caller commits separately via its own normal path), or null
  // if this wasn't a multi-drag.
  const finishMultiDrag = (anchorKey) => {
    const md = multiDragRef.current;
    if (!md || md.anchorKey !== anchorKey) return null;
    multiDragRef.current = null;
    return Object.keys(md.startPositions).filter((k) => k !== anchorKey);
  };

  // Commits a moved shape's CURRENT Konva node position back to React
  // state, looking up whether it's a room (corner-anchored) or an element
  // (center-anchored) to apply the right conversion.
  const commitMovedShapeByKey = (key, roomUpdates, elementUpdates) => {
    const node = shapeRefs.current[key];
    if (!node) return;

    const room = rooms.find((r) => r._key === key);
    if (room) {
      const { height } = feetToCanvas(room);
      const { x, y } = canvasToFeet(node.x(), node.y(), 0, height);
      roomUpdates.push({ key, x, y });
      return;
    }

    const el = areaElements.find((it) => it._key === key);
    if (el) {
      const { width, height } = feetToCanvas(el);
      const topLeftCanvasX = node.x() - width / 2;
      const topLeftCanvasY = node.y() - height / 2;
      const { x, y } = canvasToFeet(topLeftCanvasX, topLeftCanvasY, width, height);
      elementUpdates.push({ key, x, y });
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

    const intersects = (item) => {
      const { x, y, width, height } = feetToCanvas(item);
      return x < x2 && x + width > x1 && y < y2 && y + height > y1;
    };

    const roomHits = placedRooms.filter(intersects);
    const elementHits = areaElements.filter(intersects);
    const lineHits = lineElements.filter((line) => {
      const p1x = line.x * baseScale;
      const p1y = (safeWidthFt - line.y) * baseScale;
      const p2x = line.x2 * baseScale;
      const p2y = (safeWidthFt - line.y2) * baseScale;
      const inBox = (px, py) => px >= x1 && px <= x2 && py >= y1 && py <= y2;
      return inBox(p1x, p1y) || inBox(p2x, p2y);
    });
    const allHits = [...roomHits, ...elementHits, ...lineHits];

    if (allHits.length > 0) onSelectionChange(allHits.map((r) => r._key));
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

  const drawGuides = (newGuides) => {
    const group = guideGroupRef.current;
    if (!group) return;
    group.destroyChildren();
    for (const g of newGuides) {
      group.add(new Konva.Line({ points: g.points, stroke: "#ec4899", strokeWidth: 1, dash: [4, 3], listening: false }));
    }
    group.getLayer()?.batchDraw();
  };

  const handleDragMove = (item, e) => {
    const { width, height } = feetToCanvas(item);
    const { snappedX, snappedY, newGuides } = computeEdgeSnap(item._key, e.target.x(), e.target.y(), width, height);
    e.target.x(snappedX);
    e.target.y(snappedY);
    drawGuides(newGuides);
    applyMultiDragDelta(item._key, e);
  };

  const finishMultiDragAndCommit = (anchorKey) => {
    const otherKeys = finishMultiDrag(anchorKey);
    if (!otherKeys || otherKeys.length === 0) return;

    const roomUpdates = [];
    const elementUpdates = [];
    for (const key of otherKeys) commitMovedShapeByKey(key, roomUpdates, elementUpdates);

    if (roomUpdates.length > 0) {
      onRoomsChange(
        rooms.map((r) => {
          const u = roomUpdates.find((ru) => ru.key === r._key);
          return u ? { ...r, x: u.x, y: u.y } : r;
        })
      );
    }
    if (elementUpdates.length > 0) {
      onElementsChange(
        siteElements.map((el) => {
          const u = elementUpdates.find((eu) => eu.key === el._key);
          return u ? { ...el, x: u.x, y: u.y } : el;
        })
      );
    }
  };

  const handleDragEnd = (item, items, onChange, e) => {
    drawGuides([]);
    const { x, y } = canvasToFeet(e.target.x(), e.target.y(), 0, feetToCanvas(item).height);
    onChange(items.map((it) => (it._key === item._key ? { ...it, x, y } : it)));
    finishMultiDragAndCommit(item._key);
  };

  const handleTransformEnd = (item, items, onChange, e) => {
    const node = e.target;
    const scaleX = node.scaleX();
    const scaleY = node.scaleY();
    const rotation = node.rotation();
    node.scaleX(1);
    node.scaleY(1);

    const newWidthPx = Math.max(MIN_ROOM_FT * baseScale, node.width() * scaleX);
    const newHeightPx = Math.max(MIN_ROOM_FT * baseScale, node.height() * scaleY);

    const { x, y, length, width } = canvasToFeet(node.x(), node.y(), newWidthPx, newHeightPx);
    onChange(
      items.map((it) =>
        it._key === item._key ? { ...it, x, y, length, width, ...("rotation" in it ? { rotation } : {}) } : it
      )
    );
  };

  const handleElementDragMove = (el, e) => {
    applyMultiDragDelta(el._key, e);
  };

  const handleElementDragEnd = (el, e) => {
    const { width, height } = feetToCanvas(el); // pixel size, unaffected by drag
    const topLeftCanvasX = e.target.x() - width / 2;
    const topLeftCanvasY = e.target.y() - height / 2;
    const { x, y } = canvasToFeet(topLeftCanvasX, topLeftCanvasY, width, height);
    onElementsChange(siteElements.map((it) => (it._key === el._key ? { ...it, x, y } : it)));
    finishMultiDragAndCommit(el._key);
  };

  const handleElementTransformEnd = (el, e) => {
    const node = e.target;
    const scaleX = node.scaleX();
    const scaleY = node.scaleY();
    const rotation = node.rotation();
    node.scaleX(1);
    node.scaleY(1);

    const newWidthPx = Math.max(MIN_ROOM_FT * baseScale, node.width() * scaleX);
    const newHeightPx = Math.max(MIN_ROOM_FT * baseScale, node.height() * scaleY);

    // Keep the node's own offset in sync with its new size immediately —
    // otherwise there's a one-frame visual glitch before React's next
    // render (which derives offsetX/Y fresh from the committed state)
    // catches up.
    node.offsetX(newWidthPx / 2);
    node.offsetY(newHeightPx / 2);

    const topLeftCanvasX = node.x() - newWidthPx / 2;
    const topLeftCanvasY = node.y() - newHeightPx / 2;
    const { x, y, length, width } = canvasToFeet(topLeftCanvasX, topLeftCanvasY, newWidthPx, newHeightPx);

    onElementsChange(
      siteElements.map((it) => (it._key === el._key ? { ...it, x, y, length, width, rotation } : it))
    );
  };

  const handleLineEndpointDrag = (line, endpoint, e) => {
    const { x, y } = canvasToFeet(e.target.x(), e.target.y(), 0, 0);
    const field1 = endpoint === "start" ? "x" : "x2";
    const field2 = endpoint === "start" ? "y" : "y2";
    onElementsChange(siteElements.map((el) => (el._key === line._key ? { ...el, [field1]: x, [field2]: y } : el)));
  };

  // Rotates the WHOLE line around its own midpoint, keeping its length
  // fixed — distinct from dragging a single endpoint (which stretches
  // that end freely and changes length). Committed on drag end only (no
  // live imperative preview during the gesture, unlike shape drags —
  // an acceptable simplification for this smaller, less-used control).
  const handleLineRotateDrag = (line, e) => {
    const p1x = line.x * baseScale;
    const p1y = (safeWidthFt - line.y) * baseScale;
    const p2x = line.x2 * baseScale;
    const p2y = (safeWidthFt - line.y2) * baseScale;
    const midX = (p1x + p2x) / 2;
    const midY = (p1y + p2y) / 2;
    const lengthPx = Math.hypot(p2x - p1x, p2y - p1y);

    const angle = Math.atan2(e.target.y() - midY, e.target.x() - midX);
    const newP1x = midX - (lengthPx / 2) * Math.cos(angle);
    const newP1y = midY - (lengthPx / 2) * Math.sin(angle);
    const newP2x = midX + (lengthPx / 2) * Math.cos(angle);
    const newP2y = midY + (lengthPx / 2) * Math.sin(angle);

    const feet1 = canvasToFeet(newP1x, newP1y, 0, 0);
    const feet2 = canvasToFeet(newP2x, newP2y, 0, 0);

    onElementsChange(
      siteElements.map((el) =>
        el._key === line._key ? { ...el, x: feet1.x, y: feet1.y, x2: feet2.x, y2: feet2.y } : el
      )
    );
  };

  const handleLineBodyDragEnd = (line, e) => {
    const dxFt = e.target.x() / baseScale;
    const dyFt = -e.target.y() / baseScale; // canvas y is flipped relative to feet-north
    e.target.x(0);
    e.target.y(0);
    onElementsChange(
      siteElements.map((el) =>
        el._key === line._key
          ? { ...el, x: el.x + dxFt, y: el.y + dyFt, x2: el.x2 + dxFt, y2: el.y2 + dyFt }
          : el
      )
    );
  };

  if (!hasValidPlot) return null;

  return (
    <div className="room-canvas-wrap">
      {/* North is always "up" in this app's plot coordinate convention
          (confirmed by feetToCanvas's y-flip), and x increases eastward —
          standard map orientation, so this compass is static, not
          rotated to match anything. Plain HTML/SVG overlay rather than a
          Konva shape: the whole Stage shares one pan/zoom transform, so
          a shape drawn inside it would zoom and pan along with the
          drawing instead of staying fixed in the corner. */}
      <svg className="rc-compass" viewBox="0 0 56 56" xmlns="http://www.w3.org/2000/svg">
        <circle cx="28" cy="28" r="26" fill="white" stroke="#d1d5db" strokeWidth="1.5" />
        <polygon points="28,8 32,28 28,24 24,28" fill="#4c1d95" />
        <polygon points="28,48 32,28 28,32 24,28" fill="#9ca3af" />
        <text x="28" y="16" textAnchor="middle" fontSize="10" fontWeight="700" fill="#111827">N</text>
        <text x="46" y="31" textAnchor="middle" fontSize="9" fill="#6b7280">E</text>
        <text x="28" y="45" textAnchor="middle" fontSize="9" fill="#6b7280">S</text>
        <text x="10" y="31" textAnchor="middle" fontSize="9" fill="#6b7280">W</text>
      </svg>

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
        width={canvasWidth + STAGE_MARGIN_PX * 2}
        height={canvasHeight + STAGE_MARGIN_PX * 2}
        offsetX={-STAGE_MARGIN_PX}
        offsetY={-STAGE_MARGIN_PX}
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
          <Rect
            x={0}
            y={0}
            width={canvasWidth}
            height={canvasHeight}
            fill="#f5f3ff"
            stroke="#1f2937"
            strokeWidth={WALL_THICKNESS_FT * baseScale * 1.3}
          />

          {gridLines.map((line) => (
            <Line key={line.key} points={line.points} stroke="#e9e4fb" strokeWidth={1} listening={false} />
          ))}

          {roadPoints && <Line points={roadPoints} stroke="#9ca3af" strokeWidth={1.5} dash={[5, 4]} listening={false} />}

          <Group ref={guideGroupRef} listening={false} />

          <DimensionChain segments={northDimSegments} edge="north" offsetPx={DIM_LINE_OFFSET_PX} baseScale={baseScale} plotWidthFt={safeWidthFt} />
          <DimensionChain segments={westDimSegments} edge="west" offsetPx={DIM_LINE_OFFSET_PX} baseScale={baseScale} plotWidthFt={safeWidthFt} />

          {/* Overall plot totals — outermost dimension line, matching the
              unbroken outer measurement in a real architectural drawing. */}
          <Group listening={false}>
            <Line points={[0, -DIM_TOTAL_OFFSET_PX, canvasWidth, -DIM_TOTAL_OFFSET_PX]} stroke="#111827" strokeWidth={1} />
            <Line points={[0, -DIM_TOTAL_OFFSET_PX - 4, 0, -DIM_TOTAL_OFFSET_PX + 4]} stroke="#111827" strokeWidth={1} />
            <Line points={[canvasWidth, -DIM_TOTAL_OFFSET_PX - 4, canvasWidth, -DIM_TOTAL_OFFSET_PX + 4]} stroke="#111827" strokeWidth={1} />
            <Text x={0} y={-DIM_TOTAL_OFFSET_PX - 15} width={canvasWidth} align="center" text={`${safeLengthFt}' total`} fontSize={10} fontStyle="700" fill="#111827" />

            <Line points={[-DIM_TOTAL_OFFSET_PX, 0, -DIM_TOTAL_OFFSET_PX, canvasHeight]} stroke="#111827" strokeWidth={1} />
            <Line points={[-DIM_TOTAL_OFFSET_PX - 4, 0, -DIM_TOTAL_OFFSET_PX + 4, 0]} stroke="#111827" strokeWidth={1} />
            <Line points={[-DIM_TOTAL_OFFSET_PX - 4, canvasHeight, -DIM_TOTAL_OFFSET_PX + 4, canvasHeight]} stroke="#111827" strokeWidth={1} />
          </Group>

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
                    stroke={isSelected ? "#4c1d95" : "#374151"}
                    strokeWidth={isSelected ? WALL_THICKNESS_FT * baseScale + 1.5 : WALL_THICKNESS_FT * baseScale}
                    draggable={!panMode && !locked}
                    dragBoundFunc={makeDragBoundFunc(width, height)}
                    onDragStart={() => handleAnyDragStart(room._key)}
                    onDragMove={(e) => handleDragMove(room, e)}
                    onDragEnd={(e) => handleDragEnd(room, rooms, onRoomsChange, e)}
                    onTransformEnd={(e) => handleTransformEnd(room, rooms, onRoomsChange, e)}
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

          {areaElements.map((el) => {
            const { x: topLeftX, y: topLeftY, width, height } = feetToCanvas(el);
            const cx = topLeftX + width / 2;
            const cy = topLeftY + height / 2;
            const isSelected = selectedKeys.includes(el._key);
            const def = ELEMENT_DEFS_FOR_RENDER[el.type] || {};
            const symbol = def.symbol;
            const fillColor = el.color || def.color || "#e5e7eb";

            return (
              <Fragment key={el._key}>
                {/* Center-pivot Group: x/y is the CENTER (converted from the
                    stored top-left corner just for rendering — the stored
                    data model stays top-left, matching rooms/backend/DXF).
                    Rotating around the center, not a corner, is both more
                    intuitive and makes the boundary-clamping math tractable
                    (a rotated rectangle's true footprint is well-defined
                    relative to its own center, not one of its corners). */}
                <Group
                  ref={(node) => {
                    if (node) shapeRefs.current[el._key] = node;
                  }}
                  x={cx}
                  y={cy}
                  offsetX={width / 2}
                  offsetY={height / 2}
                  rotation={el.rotation || 0}
                  width={width}
                  height={height}
                  draggable={!panMode && !locked}
                  dragBoundFunc={makeElementDragBoundFunc(width, height, el.rotation || 0)}
                  onDragStart={() => handleAnyDragStart(el._key)}
                  onDragMove={(e) => handleElementDragMove(el, e)}
                  onDragEnd={(e) => handleElementDragEnd(el, e)}
                  onTransformEnd={(e) => handleElementTransformEnd(el, e)}
                  onClick={(evt) => toggleSelect(el._key, evt.evt.shiftKey)}
                  onTap={() => toggleSelect(el._key, false)}
                >
                  <Rect
                    x={0}
                    y={0}
                    width={width}
                    height={height}
                    fill={fillColor}
                    stroke={isSelected ? "#4c1d95" : "#6b7280"}
                    strokeWidth={isSelected ? 2 : 1}
                    cornerRadius={def.rounded ? Math.min(width, height) * 0.15 : 0}
                  />
                  {symbol === "circle" && (
                    <>
                      {/* Layered canopy — an offset trio of circles reads as
                          a tree silhouette rather than a single flat dot,
                          matching the same real symbol drawn into the DXF. */}
                      <Circle
                        x={width / 2}
                        y={height / 2}
                        radius={Math.min(width, height) / 2.6}
                        fill={fillColor}
                        stroke="#166534"
                        strokeWidth={1}
                        listening={false}
                      />
                      {def.label === "Tree" && (
                        <>
                          <Circle
                            x={width / 2 - width * 0.12}
                            y={height / 2 - height * 0.1}
                            radius={Math.min(width, height) / 4}
                            fill={fillColor}
                            stroke="#166534"
                            strokeWidth={0.75}
                            opacity={0.9}
                            listening={false}
                          />
                          <Circle
                            x={width / 2 + width * 0.14}
                            y={height / 2 + height * 0.08}
                            radius={Math.min(width, height) / 4.3}
                            fill={fillColor}
                            stroke="#166534"
                            strokeWidth={0.75}
                            opacity={0.9}
                            listening={false}
                          />
                          <Circle
                            x={width / 2}
                            y={height / 2}
                            radius={Math.min(width, height) * 0.06}
                            fill="#78350f"
                            listening={false}
                          />
                        </>
                      )}
                    </>
                  )}
                  {symbol === "hexagon" && (
                    <RegularPolygon
                      x={width / 2}
                      y={height / 2}
                      sides={6}
                      radius={Math.min(width, height) / 2.2}
                      fill="none"
                      stroke="#92400e"
                      strokeWidth={1.5}
                      listening={false}
                    />
                  )}
                  {symbol === "car" && (
                    <>
                      {/* Windshield divider + two wheel marks — a simple,
                          genuine flat-icon silhouette rather than a plain
                          rectangle. Not licensed clipart, which isn't
                          something that can be sourced or bundled here —
                          a distinctive hand-built symbol instead. */}
                      <Line
                        points={[width * 0.32, 0, width * 0.32, height]}
                        stroke="#4b5563"
                        strokeWidth={1}
                        listening={false}
                      />
                      <Circle
                        x={width * 0.22}
                        y={height * 0.12}
                        radius={Math.min(width, height) * 0.09}
                        fill="#374151"
                        listening={false}
                      />
                      <Circle
                        x={width * 0.22}
                        y={height * 0.88}
                        radius={Math.min(width, height) * 0.09}
                        fill="#374151"
                        listening={false}
                      />
                      <Circle
                        x={width * 0.82}
                        y={height * 0.12}
                        radius={Math.min(width, height) * 0.09}
                        fill="#374151"
                        listening={false}
                      />
                      <Circle
                        x={width * 0.82}
                        y={height * 0.88}
                        radius={Math.min(width, height) * 0.09}
                        fill="#374151"
                        listening={false}
                      />
                    </>
                  )}
                  <Text
                    x={0}
                    y={height / 2 - 6}
                    width={width}
                    align="center"
                    text={def.label || el.type}
                    fontSize={9}
                    fontStyle="600"
                    fill="#374151"
                    listening={false}
                  />
                </Group>
              </Fragment>
            );
          })}

          {lineElements.map((line) => {
            const isSelected = selectedKeys.includes(line._key);
            const p1x = line.x * baseScale;
            const p1y = (safeWidthFt - line.y) * baseScale;
            const p2x = line.x2 * baseScale;
            const p2y = (safeWidthFt - line.y2) * baseScale;
            // Fall back to the old type-based dashed/solid behavior for
            // lines saved before per-line style existed.
            const dashStyle = line.dash_style || (line.type === "dotted_line" ? "dotted" : "solid");
            const strokeWidth = line.stroke_width || 1.5;
            const dashPattern = LINE_DASH_PATTERNS[dashStyle];

            return (
              <Fragment key={line._key}>
                <Line
                  points={[p1x, p1y, p2x, p2y]}
                  stroke={line.color || "#111827"}
                  strokeWidth={isSelected ? strokeWidth + 1 : strokeWidth}
                  dash={dashPattern}
                  draggable={!panMode && !locked}
                  onDragEnd={(e) => handleLineBodyDragEnd(line, e)}
                  onClick={(evt) => toggleSelect(line._key, evt.evt.shiftKey)}
                  onTap={() => toggleSelect(line._key, false)}
                  hitStrokeWidth={12}
                />
                <Circle
                  x={p1x}
                  y={p1y}
                  radius={5}
                  fill={isSelected ? "#4c1d95" : "#6b7280"}
                  draggable={!panMode && !locked}
                  onDragMove={(e) => handleLineEndpointDrag(line, "start", e)}
                  onClick={() => toggleSelect(line._key, false)}
                />
                <Circle
                  x={p2x}
                  y={p2y}
                  radius={5}
                  fill={isSelected ? "#4c1d95" : "#6b7280"}
                  draggable={!panMode && !locked}
                  onDragMove={(e) => handleLineEndpointDrag(line, "end", e)}
                  onClick={() => toggleSelect(line._key, false)}
                />
                {isSelected &&
                  (() => {
                    const midX = (p1x + p2x) / 2;
                    const midY = (p1y + p2y) / 2;
                    const dx = p2x - p1x;
                    const dy = p2y - p1y;
                    const len = Math.hypot(dx, dy) || 1;
                    // Perpendicular unit vector, offset outward by a fixed
                    // pixel distance, so the rotate handle sits clearly off
                    // to the side rather than overlapping the line itself.
                    const perpX = (-dy / len) * 22;
                    const perpY = (dx / len) * 22;
                    return (
                      <>
                        <Line
                          points={[midX, midY, midX + perpX, midY + perpY]}
                          stroke="#f59e0b"
                          strokeWidth={1}
                          dash={[2, 2]}
                          listening={false}
                        />
                        <Circle
                          x={midX + perpX}
                          y={midY + perpY}
                          radius={5}
                          fill="#f59e0b"
                          stroke="#92400e"
                          strokeWidth={1}
                          draggable={!panMode && !locked}
                          onDragEnd={(e) => handleLineRotateDrag(line, e)}
                        />
                      </>
                    );
                  })()}
              </Fragment>
            );
          })}

          <Transformer
            ref={transformerRef}
            rotateEnabled={selectedKeys.length === 1 && areaElements.some((el) => el._key === selectedKeys[0])}
            rotationSnaps={[0, 45, 90, 135, 180, 225, 270, 315]}
            enabledAnchors={["top-left", "top-right", "bottom-left", "bottom-right"]}
            boundBoxFunc={(oldBox, newBox) => {
              // Konva's Transformer reports newBox.width/height in absolute
              // (zoom-scaled) pixels — confirmed directly from its source
              // (__getNodeRect applies node.getAbsoluteTransform()) — but
              // MIN_ROOM_FT * baseScale is a fixed model-space quantity.
              // Scale the threshold by the current zoom to compare
              // like-for-like; without this, the minimum-size clamp is
              // wrong at any zoom level other than 1.
              const minPx = MIN_ROOM_FT * baseScale * zoom;
              if (newBox.width < minPx || newBox.height < minPx) {
                return oldBox;
              }

              // Also reject any resize that would push the shape's true
              // bounding box (Konva's __getNodeRect already accounts for
              // the shape's own rotation here) outside the plot. newBox is
              // in absolute space; convert to local/model space via the
              // attached node's own parent transform (boundBoxFunc is
              // invoked directly, not via .call, so `this` isn't the
              // Transformer here — read the live attached node from the
              // ref instead).
              const attachedNode = transformerRef.current?.nodes()?.[0];
              if (attachedNode) {
                const parentTransform = attachedNode.getParent().getAbsoluteTransform();
                const inverse = parentTransform.copy().invert();
                const topLeft = inverse.point({ x: newBox.x, y: newBox.y });
                const bottomRight = inverse.point({ x: newBox.x + newBox.width, y: newBox.y + newBox.height });
                const minX = Math.min(topLeft.x, bottomRight.x);
                const maxX = Math.max(topLeft.x, bottomRight.x);
                const minY = Math.min(topLeft.y, bottomRight.y);
                const maxY = Math.max(topLeft.y, bottomRight.y);
                if (minX < -0.01 || minY < -0.01 || maxX > canvasWidth + 0.01 || maxY > canvasHeight + 0.01) {
                  return oldBox;
                }
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
