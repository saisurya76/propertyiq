import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { studioApi } from "./studioApi";
import PlotPreview from "./PlotPreview";
import { evaluateAdjacency, ARCHITECTURAL_STYLE_LABELS } from "./adjacencyEngine";

const RoomCanvas = lazy(() => import("./RoomCanvas"));

const ROOM_COLOR_PALETTE = ["#c4b5fd", "#93c5fd", "#86efac", "#fde68a", "#fca5a5", "#f9a8d4"];

const REGIONS = [
  ["india", "India"],
  ["thailand", "Thailand"],
  ["usa", "USA"],
  ["global", "Other / Global"],
];

const UNIT_SYSTEMS = [
  ["imperial", "Feet / sqft"],
  ["metric", "Meters / sqm"],
];

// Auto-syncs region + currency + unit system when the user types a
// recognized country name — fixes a real, plain gap: country was
// entirely disconnected from region (which drives the materials catalog
// and validation engine) and currency, so a user could type "Thailand"
// as their country while region stayed on "india" with no connection
// between the two, silently showing Indian materials/pricing/Vastu
// validation for a Thai property. Only fires when country CHANGES —
// region, currency, and unit system all stay freely editable afterward
// for anyone who wants a deliberately different combination.
const COUNTRY_TO_REGION_CURRENCY = {
  "india": { region: "india", currency: "INR", unit_system: "imperial" },
  "thailand": { region: "thailand", currency: "THB", unit_system: "metric" },
  "usa": { region: "usa", currency: "USD", unit_system: "imperial" },
  "united states": { region: "usa", currency: "USD", unit_system: "imperial" },
};

// Unit conversion — a display/input layer ONLY. Internal storage stays
// in feet everywhere (plot.plot_length_ft, room.length/width, the DXF
// export, the Konva canvas's own math, Vastu/adjacency zone
// calculations) — all of that assumes feet throughout the codebase, and
// rewriting it to be unit-agnostic would be a far larger, much riskier
// undertaking than this app actually needs. Converting at the boundary —
// the exact input field and label the user sees — gets the same
// practical result (genuinely seeing and entering meters when using the
// metric system) without touching any of that internal math at all.
const FT_TO_M = 0.3048;
const SQFT_TO_SQM = 0.092903;

function feetToDisplay(feetValue, unitSystem) {
  if (feetValue === null || feetValue === undefined || feetValue === "") return feetValue;
  return unitSystem === "metric" ? Math.round(feetValue * FT_TO_M * 100) / 100 : feetValue;
}

function displayToFeet(displayValue, unitSystem) {
  if (displayValue === null || displayValue === undefined || displayValue === "") return displayValue;
  return unitSystem === "metric" ? Math.round((displayValue / FT_TO_M) * 100) / 100 : displayValue;
}

function sqftToDisplayArea(sqft, unitSystem) {
  return unitSystem === "metric" ? Math.round(sqft * SQFT_TO_SQM) : Math.round(sqft);
}

function lengthUnitLabel(unitSystem) {
  return unitSystem === "metric" ? "m" : "ft";
}

function areaUnitLabel(unitSystem) {
  return unitSystem === "metric" ? "sqm" : "sqft";
}

const CURRENCIES = ["USD", "INR", "THB", "AED", "GBP", "EUR"];

const DIRECTIONS = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"];

// Surrounding-site context — what's OUTSIDE the plot boundary in each
// direction (a river to the northeast, a hill to the west, etc). Distinct
// from `site_elements` (objects actually drawn ON the plot, like a pool).
// Water/forest/mountain/open-space were the explicit ask; road and
// religious-structure added as sensible extras matching the app's
// existing Vastu-conscious framing (mentioned to the user, not silently
// assumed — same precedent as pathway/bench being added to the site
// elements toolbar earlier).
const MASTER_PLAN_ELEMENT_TYPES = {
  water_body: "Water Body / Stream",
  forest: "Forest / Green Belt",
  mountain: "Mountain / Hill",
  open_space: "Open Space / Park",
  main_road: "Main Road",
  religious_structure: "Temple / Religious Structure",
};

const STEPS = ["Plot Details", "Materials", "Room Layout", "Review & Generate"];

function emptyRoom() {
  return {
    name: "", x: 0, y: 0, length: 10, width: 10, color: null,
    border_style: "solid", border_color: null, border_width: null,
    _key: Math.random().toString(36).slice(2),
  };
}

// Site elements: landscaping/hardscape/site furnishings — distinct from
// rooms (never Vastu-checked, never in the Materials/cost step). "symbol"
// tells RoomCanvas what decorative overlay to draw inside the bounding
// box (all still use the same interactive Rect+Transformer for drag/resize,
// same proven code path as rooms — only the fill color and overlay differ).
const ELEMENT_DEFS = {
  tree: { label: "Tree", color: "#86efac", symbol: "circle", defaultLength: 6, defaultWidth: 6 },
  plant: { label: "Plant", color: "#bbf7d0", symbol: "circle", defaultLength: 3, defaultWidth: 3 },
  gazebo: { label: "Gazebo", color: "#e7d4b5", symbol: "hexagon", defaultLength: 10, defaultWidth: 10 },
  pool: { label: "Swimming Pool", color: "#7dd3fc", symbol: null, defaultLength: 16, defaultWidth: 8 },
  car: { label: "Car", color: "#cbd5e1", symbol: null, defaultLength: 15, defaultWidth: 7 },
  pathway: { label: "Pathway", color: "#e7e5e4", symbol: null, defaultLength: 4, defaultWidth: 20 },
  bench: { label: "Bench", color: "#c4a484", symbol: null, defaultLength: 5, defaultWidth: 2 },
};

const LINE_ELEMENT_DEFS = {
  line: { label: "Line", dashed: false },
  dotted_line: { label: "Dotted Line", dashed: true },
};

function emptyAreaElement(type) {
  const def = ELEMENT_DEFS[type];
  return {
    _key: `el_${Math.random().toString(36).slice(2)}`,
    type,
    x: 0,
    y: 0,
    length: def.defaultLength,
    width: def.defaultWidth,
    color: def.color,
    rotation: 0,
    border_style: "solid",
    border_color: null,
    border_width: null,
  };
}

function emptyLineElement(type, plotLengthFt, plotWidthFt) {
  return {
    _key: `el_${Math.random().toString(36).slice(2)}`,
    type,
    x: plotLengthFt * 0.25,
    y: plotWidthFt * 0.5,
    x2: plotLengthFt * 0.75,
    y2: plotWidthFt * 0.5,
    color: "#111827",
    dash_style: type === "dotted_line" ? "dotted" : "solid",
    stroke_width: 1.5,
  };
}

// Konva dash arrays live in RoomCanvas.jsx (which does the actual
// rendering) — this file only needs the human-readable labels for the
// dropdown.
const LINE_DASH_STYLE_LABELS = {
  solid: "Solid",
  dotted: "Dotted",
  dash: "Dashed",
  "dash-dot": "Dash-dot",
};

function formatUnitPrice(usdAmount, unit, currency, fxRates) {
  const rate = fxRates?.[currency];
  const amount = rate ? usdAmount * rate : usdAmount;
  const displayCurrency = rate ? currency : "USD";
  try {
    return `${new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: displayCurrency,
      maximumFractionDigits: amount >= 100 ? 0 : 2,
    }).format(amount)}/${unit}`;
  } catch {
    return `$${usdAmount}/${unit}`;
  }
}

function formatLinePrice(usdPerUnit, plotSizeSqft, currency, fxRates, openingAreaFraction) {
  const pricedAreaSqft = openingAreaFraction ? plotSizeSqft * openingAreaFraction : plotSizeSqft;
  const usdTotal = usdPerUnit * pricedAreaSqft;
  const rate = fxRates?.[currency];
  const amount = rate ? usdTotal * rate : usdTotal;
  const displayCurrency = rate ? currency : "USD";
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: displayCurrency,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `$${Math.round(usdTotal).toLocaleString()}`;
  }
}

function ConstructionStudio({ onBack, onQuotaExceeded, resumePropertyId, onStartNew }) {
  const [step, setStep] = useState(0);

  const [plot, setPlot] = useState({
    plot_length_ft: 40,
    plot_width_ft: 30,
    region: "india",
    currency: "INR",
    city: "",
    country: "India",
    unit_system: "imperial",
    entrance_direction: "north-east",
    road_facing_side: "north",
    slope_direction: "north",
    master_plan_elements: [],
    architectural_style: "modern_open_plan",
  });

  const [catalog, setCatalog] = useState(null);
  const [laborCatalog, setLaborCatalog] = useState(null);
  const [fxRates, setFxRates] = useState(null);
  const [selections, setSelections] = useState({});
  const [laborSelections, setLaborSelections] = useState({});
  const [supplierSearch, setSupplierSearch] = useState({}); // { [catId]: searchText }
  const [supplierPreferences, setSupplierPreferences] = useState({}); // { [optionId]: [supplierName, ...] } — local reference only, not sent to backend (no per-supplier cost model server-side)
  const [estimate, setEstimate] = useState(null);
  const [bom, setBom] = useState(null);
  const [boq, setBoq] = useState(null);
  const [bomBoqLoading, setBomBoqLoading] = useState(null); // "bom" | "boq" | null
  const [bomBoqError, setBomBoqError] = useState("");
  const [adjacencyReport, setAdjacencyReport] = useState(null);
  const [adjacencyReportLoading, setAdjacencyReportLoading] = useState(false);
  const [adjacencyReportError, setAdjacencyReportError] = useState("");
  const estimateRequestIdRef = useRef(0); // guards against a slower, older request overwriting a faster, newer one

  // Site elements (trees, pool, etc.) and material/labor selections are
  // shared across the whole property (a pool or a chosen flooring tile
  // realistically applies to the whole build, not one floor) — only rooms
  // are per-floor. `floors` lives in undo/redo history; which floor is
  // currently ACTIVE deliberately does not (switching floors shouldn't be
  // an undoable action).
  const [layoutHistory, setLayoutHistory] = useState({
    past: [],
    present: {
      floors: [{ floor_id: null, floor_number: 0, floor_label: "Ground Floor", rooms: [emptyRoom()] }],
      elements: [],
    },
    future: [],
  });
  const [activeFloorIndex, setActiveFloorIndex] = useState(0);
  const floors = layoutHistory.present.floors;
  const rooms = useMemo(() => floors[activeFloorIndex]?.rooms || [], [floors, activeFloorIndex]);
  const siteElements = layoutHistory.present.elements;
  const [selectedKeys, setSelectedKeys] = useState([]);

  // Steady-state adjacency status (recomputed whenever rooms/style
  // actually change and commit) — the room being actively dragged gets
  // its own LIVE, per-frame update imperatively inside RoomCanvas, so
  // this memo doesn't need to run on every drag frame.
  const adjacencyResult = useMemo(
    () => evaluateAdjacency(rooms, plot.architectural_style),
    [rooms, plot.architectural_style]
  );
  const roomAdjacencyStatus = adjacencyResult.roomStatus;

  // Strips the frontend-only `_key` field before sending rooms/elements to
  // the backend, which doesn't know about it (it's purely for React keys
  // and Konva node refs) — used by copy/paste when cloning items, the
  // live Vastu-check effect below, and the save/autosave payload
  // builders further down. Declared here, early, since the Vastu effect
  // right below needs it (a real ESLint ordering error last time this
  // was attempted, when it lived much further down the file).
  const stripKey = (item) => {
    // eslint-disable-next-line no-unused-vars -- intentionally destructured out
    const { _key, ...rest } = item;
    return rest;
  };

  const [liveVastuResult, setLiveVastuResult] = useState(null);

  // Live Vastu compliance — recomputes from the CURRENT room layout,
  // debounced, via the lightweight quota-free /vastu-check endpoint,
  // shown directly on the Room Layout step itself (not just at Review
  // time) so the feedback loop matches how adjacency validation already
  // works here. Fixes a real reported bug: Vastu compliance previously
  // only came from a generated design's stored snapshot and kept
  // showing stale findings after a room was removed or rearranged,
  // since nothing recomputed it.
  //
  // Recomputes traditional-building compliance live from the CURRENT
  // room layout — routes by plot.country on the backend: Vastu for
  // India (unchanged), the Thai traditional-building engine for
  // Thailand. Both share this same endpoint/effect; the backend decides
  // which engine to use.
  useEffect(() => {
    if (!plot.plot_length_ft || !plot.plot_width_ft || !plot.entrance_direction || !plot.road_facing_side) return;

    const timer = setTimeout(() => {
      studioApi
        .checkVastu({
          plot_length_ft: plot.plot_length_ft,
          plot_width_ft: plot.plot_width_ft,
          rooms: rooms.filter((r) => r.name.trim()).map(stripKey),
          entrance_direction: plot.entrance_direction,
          road_facing_side: plot.road_facing_side,
          slope_direction: plot.slope_direction === "not_available" ? null : plot.slope_direction,
          country: plot.country,
        })
        .then(setLiveVastuResult)
        .catch(() => {}); // non-critical live check — a transient failure just leaves the last-known result showing
    }, 600);

    return () => clearTimeout(timer);
  }, [rooms, plot.plot_length_ft, plot.plot_width_ft, plot.entrance_direction, plot.road_facing_side, plot.slope_direction, plot.country]);

  // Save/load/lock state
  const [propertyId, setPropertyId] = useState(null);
  const [propertyName, setPropertyName] = useState("Untitled Property");
  const [locked, setLocked] = useState(false);
  const [saveStatus, setSaveStatus] = useState(""); // transient "Saved" / error message
  const [saving, setSaving] = useState(false);
  const lastSavedSignatureRef = useRef(null); // used by autosave to detect genuine changes vs. no-op re-renders
  const autosaveTimerRef = useRef(null);
  const [unlockStep, setUnlockStep] = useState(null); // null | "requesting" | "code_sent"
  const [unlockCode, setUnlockCode] = useState("");
  const [unlockError, setUnlockError] = useState("");

  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const plotSizeSqft = Math.round(plot.plot_length_ft * plot.plot_width_ft);

  // Overflow validation — mouse drag/resize can no longer push a room or
  // element outside the plot (the boundary is enforced live on the
  // canvas), but typing a length/width/position directly into the table
  // fields bypasses that. Check on every render and surface it as a
  // dynamic banner rather than silently allowing an invalid layout.
  const overflowWarnings = useMemo(() => {
    const warnings = [];
    const plotLengthFt = plot.plot_length_ft || 0;
    const plotWidthFt = plot.plot_width_ft || 0;

    for (const room of rooms) {
      if (!room.name.trim()) continue;
      if (room.length > plotLengthFt || room.width > plotWidthFt) {
        warnings.push(`"${room.name}" (${room.length}' × ${room.width}') is larger than the plot itself (${plotLengthFt}' × ${plotWidthFt}').`);
      } else if (room.x < 0 || room.y < 0 || room.x + room.length > plotLengthFt || room.y + room.width > plotWidthFt) {
        warnings.push(`"${room.name}" extends outside the plot boundary.`);
      }
    }

    for (const el of siteElements) {
      const isLine = el.type in LINE_ELEMENT_DEFS;
      if (isLine) continue; // lines aren't bounded to the plot
      const label = ELEMENT_DEFS[el.type]?.label || el.type;
      if (el.length > plotLengthFt || el.width > plotWidthFt) {
        warnings.push(`${label} (${el.length}' × ${el.width}') is larger than the plot itself.`);
      } else if (el.x < 0 || el.y < 0 || el.x + el.length > plotLengthFt || el.y + el.width > plotWidthFt) {
        warnings.push(`${label} extends outside the plot boundary.`);
      }
    }

    return warnings;
  }, [rooms, siteElements, plot.plot_length_ft, plot.plot_width_ft]);

  const [catalogRefreshing, setCatalogRefreshing] = useState(false);

  const fetchCatalog = useCallback(
    () =>
      studioApi.getMaterials(plot.region)
        .then((res) => {
          setCatalog(res.categories);
          setLaborCatalog(res.labor_categories || {});
        })
        .catch(() => {
          setCatalog(null);
          setLaborCatalog(null);
        }),
    [plot.region]
  );

  // Load material + labor/contractor catalog whenever region changes.
  // Plain direct call on mount/region-change (no synchronous setState
  // inside the effect body itself) — the refresh button's click handler
  // below does the synchronous "show refreshing" state, safe there since
  // it's a user event, not an effect.
  useEffect(() => {
    fetchCatalog();
  }, [fetchCatalog]);

  const handleCatalogRefreshClick = () => {
    setCatalogRefreshing(true);
    fetchCatalog().finally(() => setCatalogRefreshing(false));
  };

  useEffect(() => {
    studioApi.getFxRates().then(setFxRates).catch(() => {}); // silent — falls back to USD display
  }, []);

  // Load a saved property when resuming (vs. starting fresh) — hydrates
  // plot spec, materials/labor selections, all floors' rooms, and site
  // elements from the server, and remembers propertyId so Save updates
  // this property instead of creating a new one.
  useEffect(() => {
    if (!resumePropertyId) return;
    studioApi
      .getProperty(resumePropertyId)
      .then((prop) => {
        setPropertyId(prop.property_id);
        setPropertyName(prop.name);
        setLocked(prop.locked);
        setPlot((p) => ({ ...p, ...prop.plot_spec, city: p.city }));
        setSelections(prop.selections || {});
        setLaborSelections(prop.labor_selections || {});
        setLayoutHistory({
          past: [],
          present: {
            floors: prop.floors.length > 0
              ? prop.floors.map((f) => ({
                  floor_id: f.floor_id,
                  floor_number: f.floor_number,
                  floor_label: f.floor_label,
                  rooms: f.rooms.map((r) => ({ ...r, _key: r._key || Math.random().toString(36).slice(2) })),
                }))
              : [{ floor_id: null, floor_number: 0, floor_label: "Ground Floor", rooms: [emptyRoom()] }],
            elements: (prop.site_elements || []).map((el) => ({ ...el, _key: el._key || Math.random().toString(36).slice(2) })),
          },
          future: [],
        });
        setActiveFloorIndex(0);
        setStep(2); // jump straight to Room Layout — plot/materials are already set

        // Seed the autosave baseline from the freshly-loaded data (not by
        // calling buildPropertyPayload, which reads component state via
        // closure — the setPlot/setSelections/etc calls above haven't
        // actually applied to state yet inside this same callback, so
        // that would capture stale pre-load values). Without this,
        // autosave would see the just-loaded content as "different from
        // nothing" and fire an immediate, pointless save right after load.
        lastSavedSignatureRef.current = JSON.stringify({
          name: prop.name,
          plot_spec: prop.plot_spec,
          selections: prop.selections || {},
          labor_selections: prop.labor_selections || {},
          site_elements: prop.site_elements || [],
          floors: (prop.floors.length > 0 ? prop.floors : [{ floor_number: 0, floor_label: "Ground Floor", rooms: [] }])
            .map((f) => ({ floor_number: f.floor_number, floor_label: f.floor_label, rooms: f.rooms })),
        });
      })
      .catch(() => setSaveStatus("Couldn't load that saved design."));
  }, [resumePropertyId]);

  // Live running total whenever selections/plot size/currency change
  useEffect(() => {
    if (Object.keys(selections).length === 0 && Object.keys(laborSelections).length === 0) return;
    const requestId = ++estimateRequestIdRef.current;
    studioApi
      .estimateCost({
        plot_size_sqft: plotSizeSqft,
        selections,
        labor_selections: laborSelections,
        region: plot.region,
        currency: plot.currency,
      })
      .then((result) => {
        // A slower earlier request can resolve AFTER a faster later one —
        // confirmed with a real overlapping-request test. Only apply the
        // response if it's still the most recently issued request.
        if (requestId === estimateRequestIdRef.current) setEstimate(result);
      })
      .catch(() => {});
  }, [selections, laborSelections, plotSizeSqft, plot.region, plot.currency]);

  const updatePlotField = (field, value) => {
    setPlot((p) => {
      const next = { ...p, [field]: value };
      if (field === "country") {
        const match = COUNTRY_TO_REGION_CURRENCY[value.trim().toLowerCase()];
        if (match) {
          next.region = match.region;
          next.currency = match.currency;
          next.unit_system = match.unit_system;
        }
      }
      return next;
    });
  };

  const addMasterPlanElement = () => {
    const usedTypes = new Set((plot.master_plan_elements || []).map((el) => el.type));
    const firstUnused = Object.keys(MASTER_PLAN_ELEMENT_TYPES).find((t) => !usedTypes.has(t)) || "water_body";
    setPlot((p) => ({
      ...p,
      master_plan_elements: [...(p.master_plan_elements || []), { type: firstUnused, direction: "north" }],
    }));
  };

  const updateMasterPlanElement = (index, field, value) => {
    setPlot((p) => ({
      ...p,
      master_plan_elements: p.master_plan_elements.map((el, i) => (i === index ? { ...el, [field]: value } : el)),
    }));
  };

  const removeMasterPlanElement = (index) => {
    setPlot((p) => ({ ...p, master_plan_elements: p.master_plan_elements.filter((_, i) => i !== index) }));
  };

  const toggleMaterial = (category, optionId) => {
    setSelections((s) => ({ ...s, [category]: optionId }));
  };

  const toggleLabor = (category, optionId) => {
    setLaborSelections((s) => ({ ...s, [category]: optionId }));
  };

  const getFilteredOptions = (catId, options) => {
    const query = (supplierSearch[catId] || "").trim().toLowerCase();
    if (!query) return options;
    return options.filter(
      (opt) =>
        opt.suppliers.some((s) => s.toLowerCase().includes(query)) ||
        opt.name.toLowerCase().includes(query)
    );
  };

  const toggleSupplierPreference = (optionId, supplier) => {
    setSupplierPreferences((prev) => {
      const current = prev[optionId] || [];
      const next = current.includes(supplier)
        ? current.filter((s) => s !== supplier)
        : [...current, supplier];
      return { ...prev, [optionId]: next };
    });
  };

  const editBaselineRef = useRef(null);

  const clipboardRef = useRef({ rooms: [], elements: [] });
  const [hasClipboard, setHasClipboard] = useState(false);
  const historyDebounceRef = useRef(null);

  // Discrete actions (drag end, resize end, add/remove, color pick) push
  // to history immediately. `present` is always the full { rooms, elements }
  // pair — pass partial updates and this merges them.
  const commitLayout = (partial) => {
    setLayoutHistory((s) => {
      const newPresent = { ...s.present, ...partial };
      if (JSON.stringify(newPresent) === JSON.stringify(s.present)) return s;
      return { past: [...s.past, s.present], present: newPresent, future: [] };
    });
  };

  const commitRooms = (newRooms) =>
    commitLayout({ floors: floors.map((f, i) => (i === activeFloorIndex ? { ...f, rooms: newRooms } : f)) });
  const commitElements = (newElements) => commitLayout({ elements: newElements });

  // Continuous edits (typing in a name/length/width field) update live on
  // every keystroke, but only push ONE history entry 500ms after the user
  // stops — otherwise every keystroke would be its own undo step.
  const commitRoomsDebounced = (newRooms) => {
    setLayoutHistory((s) => {
      if (editBaselineRef.current === null) editBaselineRef.current = s.present;
      const newFloors = s.present.floors.map((f, i) => (i === activeFloorIndex ? { ...f, rooms: newRooms } : f));
      return { ...s, present: { ...s.present, floors: newFloors } };
    });
    if (historyDebounceRef.current) clearTimeout(historyDebounceRef.current);
    historyDebounceRef.current = setTimeout(() => {
      setLayoutHistory((s) => {
        const baseline = editBaselineRef.current;
        editBaselineRef.current = null;
        if (baseline === null || JSON.stringify(baseline) === JSON.stringify(s.present)) return s;
        return { past: [...s.past, baseline], present: s.present, future: [] };
      });
    }, 500);
  };

  const undo = () => {
    setLayoutHistory((s) => {
      if (s.past.length === 0) return s;
      const previous = s.past[s.past.length - 1];
      return { past: s.past.slice(0, -1), present: previous, future: [s.present, ...s.future] };
    });
  };

  const redo = () => {
    setLayoutHistory((s) => {
      if (s.future.length === 0) return s;
      const next = s.future[0];
      return { past: [...s.past, s.present], present: next, future: s.future.slice(1) };
    });
  };

  const copySelection = useCallback(() => {
    if (selectedKeys.length === 0) return;
    clipboardRef.current = {
      rooms: rooms.filter((r) => selectedKeys.includes(r._key)).map(stripKey),
      elements: siteElements.filter((el) => selectedKeys.includes(el._key)).map(stripKey),
    };
    setHasClipboard(true);
  }, [rooms, siteElements, selectedKeys]);

  const pasteClipboard = useCallback(() => {
    if (locked) return;
    const { rooms: clipRooms, elements: clipElements } = clipboardRef.current;
    if (clipRooms.length === 0 && clipElements.length === 0) return;

    // Offset the pasted copy so it doesn't land exactly on top of the
    // original — same reasoning as the auto-staggered placement used for
    // brand-new rooms/elements elsewhere in this file.
    const OFFSET_FT = 2;
    const newRooms = clipRooms.map((r) => ({
      ...r,
      x: r.x + OFFSET_FT,
      y: r.y + OFFSET_FT,
      _key: Math.random().toString(36).slice(2),
    }));
    const newElements = clipElements.map((el) => {
      const isLine = el.type === "line" || el.type === "dotted_line";
      return {
        ...el,
        x: el.x + OFFSET_FT,
        y: el.y + OFFSET_FT,
        ...(isLine ? { x2: el.x2 + OFFSET_FT, y2: el.y2 + OFFSET_FT } : {}),
        _key: Math.random().toString(36).slice(2),
      };
    });

    commitLayout({
      floors: floors.map((f, i) =>
        i === activeFloorIndex ? { ...f, rooms: [...f.rooms, ...newRooms] } : f
      ),
      elements: [...siteElements, ...newElements],
    });
    setSelectedKeys([...newRooms.map((r) => r._key), ...newElements.map((el) => el._key)]);
  }, [floors, activeFloorIndex, siteElements, locked]);

  useEffect(() => {
    const onKeyDown = (e) => {
      const tag = document.activeElement?.tagName;
      const isTyping = tag === "INPUT" || tag === "TEXTAREA";

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !e.shiftKey) {
        e.preventDefault();
        undo();
      } else if ((e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === "y" || (e.key.toLowerCase() === "z" && e.shiftKey))) {
        e.preventDefault();
        redo();
      } else if ((e.key === "Delete" || e.key === "Backspace") && !isTyping && selectedKeys.length > 0 && !locked) {
        e.preventDefault();
        commitLayout({
          floors: floors.map((f, i) =>
            i === activeFloorIndex
              ? { ...f, rooms: f.rooms.filter((r) => !selectedKeys.includes(r._key)) }
              : f
          ),
          elements: siteElements.filter((el) => !selectedKeys.includes(el._key)),
        });
        setSelectedKeys([]);
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "c" && !isTyping && selectedKeys.length > 0) {
        e.preventDefault();
        copySelection();
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "v" && !isTyping && !locked) {
        e.preventDefault();
        pasteClipboard();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [floors, activeFloorIndex, siteElements, selectedKeys, locked, copySelection, pasteClipboard]);

  const updateRoom = (key, field, value) => {
    const newRooms = rooms.map((r) => (r._key === key ? { ...r, [field]: value } : r));
    if (field === "color") {
      commitRooms(newRooms); // discrete click, not a text field — commit immediately
    } else {
      commitRoomsDebounced(newRooms);
    }
  };

  const addRoom = () => {
    const defaultLength = 10;
    const defaultWidth = 10;
    const gap = 3;
    // Stagger each new room into its own grid cell instead of always
    // defaulting to (0,0) — which made every new room render fully
    // overlapping the previous ones in the live preview until manually
    // repositioned.
    const cols = Math.max(1, Math.floor((plot.plot_length_ft || 40) / (defaultLength + gap)));
    const index = rooms.length;
    const col = index % cols;
    const row = Math.floor(index / cols);
    commitRooms([
      ...rooms,
      {
        ...emptyRoom(),
        x: col * (defaultLength + gap),
        y: row * (defaultWidth + gap),
      },
    ]);
  };

  const removeRoom = (key) => {
    commitRooms(rooms.filter((r) => r._key !== key));
    setSelectedKeys((sk) => sk.filter((k) => k !== key));
  };

  // ---- floor management (item #10 — tabs per floor) ----
  const addFloor = () => {
    const nextNumber = Math.max(...floors.map((f) => f.floor_number)) + 1;
    const newFloors = [
      ...floors,
      { floor_id: null, floor_number: nextNumber, floor_label: `Floor ${nextNumber}`, rooms: [emptyRoom()] },
    ];
    commitLayout({ floors: newFloors });
    setActiveFloorIndex(newFloors.length - 1);
    setSelectedKeys([]);
  };

  const removeFloor = (index) => {
    if (floors.length <= 1) return; // a property must have at least one floor
    const newFloors = floors.filter((_, i) => i !== index);
    commitLayout({ floors: newFloors });
    setActiveFloorIndex((current) => Math.min(current, newFloors.length - 1));
    setSelectedKeys([]);
  };

  const renameFloor = (index, label) => {
    commitLayout({ floors: floors.map((f, i) => (i === index ? { ...f, floor_label: label } : f)) });
  };

  const addElement = (type) => {
    const isLine = type in LINE_ELEMENT_DEFS;
    const newElement = isLine
      ? emptyLineElement(type, plot.plot_length_ft || 40, plot.plot_width_ft || 30)
      : emptyAreaElement(type);
    // Stagger area elements the same way rooms are, so they don't all land
    // stacked at the same spot.
    if (!isLine) {
      const index = siteElements.filter((el) => el.type === type).length;
      const step = 4;
      newElement.x += (index % 5) * step;
      newElement.y += Math.floor(index / 5) * step;
    }
    commitElements([...siteElements, newElement]);
  };

  const updateElement = (key, field, value) => {
    commitElements(siteElements.map((el) => (el._key === key ? { ...el, [field]: value } : el)));
  };

  const removeElement = (key) => {
    commitElements(siteElements.filter((el) => el._key !== key));
    setSelectedKeys((sk) => sk.filter((k) => k !== key));
  };

  const buildPropertyPayload = (name) => ({
    name,
    plot_spec: {
      plot_size_sqft: plotSizeSqft,
      plot_length_ft: plot.plot_length_ft,
      plot_width_ft: plot.plot_width_ft,
      region: plot.region,
      currency: plot.currency,
      entrance_direction: plot.entrance_direction,
      road_facing_side: plot.road_facing_side,
      slope_direction: plot.slope_direction,
      master_plan_elements: plot.master_plan_elements || [],
    },
    selections,
    labor_selections: laborSelections,
    site_elements: siteElements.map(stripKey),
    floors: floors.map((f) => ({
      floor_number: f.floor_number,
      floor_label: f.floor_label,
      rooms: f.rooms.map(stripKey),
    })),
  });

  const handleSaveDesign = async (isAutosave = false) => {
    setSaving(true);
    setSaveStatus(isAutosave ? "Saving..." : "");
    try {
      if (propertyId) {
        // One request for the property fields AND the complete floor set
        // (previously: one update call + one call per floor + a final
        // re-fetch — more requests meant more chances for any single one
        // to fail; this also fixes a real correctness bug where a
        // locally-removed floor was never actually deleted server-side).
        const synced = await studioApi.syncProperty(propertyId, {
          ...buildPropertyPayload(propertyName),
          floors: floors.map((f) => ({
            floor_id: f.floor_id,
            floor_number: f.floor_number,
            floor_label: f.floor_label,
            rooms: f.rooms.map(stripKey),
          })),
        });

        // Validate the response shape HERE, synchronously, inside the
        // try block — if this throws, the catch below actually catches
        // it. A previous version of this code read `synced.floors`
        // straight from inside the setLayoutHistory updater function
        // instead; React invokes that updater during its own
        // reconciliation, OUTSIDE this try/catch's synchronous scope, so
        // a malformed response there produced an UNCAUGHT crash of the
        // whole component (confirmed directly: simulating a malformed
        // /sync response reproduced exactly this — a TypeError from deep
        // inside React's updateReducer, no error boundary, whole tree
        // torn down) rather than the clear save-failed message the user
        // should have seen.
        if (!synced || !Array.isArray(synced.floors)) {
          throw new Error("The server's response was missing expected data — please try saving again.");
        }
        const syncedFloorIds = synced.floors.map((f) => f.floor_id);

        // Pick up server-assigned floor_ids for any newly-created floors
        // so the next save updates them in place instead of duplicating —
        // keep local rooms/_keys as the source of truth, only borrow the
        // id (from the plain array above, not `synced` itself).
        setLayoutHistory((s) => ({
          ...s,
          present: {
            ...s.present,
            floors: s.present.floors.map((f, i) => ({ ...f, floor_id: syncedFloorIds[i] || f.floor_id })),
          },
        }));
        lastSavedSignatureRef.current = JSON.stringify(buildPropertyPayload(propertyName));
        setSaveStatus("Saved.");
      } else {
        const created = await studioApi.createProperty(buildPropertyPayload(propertyName));
        setPropertyId(created.property_id);
        lastSavedSignatureRef.current = JSON.stringify(buildPropertyPayload(propertyName));
        setSaveStatus("Saved.");
      }
      setSaving(false);
      setTimeout(() => setSaveStatus(""), isAutosave ? 2000 : 4000);
    } catch (e) {
      // Only the browser's own network-failure wording counts as "can't
      // reach the server" — matching on `instanceof TypeError` alone was
      // too broad and mislabeled genuine code bugs (which also throw
      // TypeError, e.g. reading a property of an unexpected response
      // shape) as a connectivity problem, hiding the real error.
      const isNetworkFailure = /failed to fetch|networkerror|load failed/i.test(e.message || "");
      // Always log the raw error — the on-screen message is deliberately
      // generic, but the real error (visible in the browser console) is
      // what actually diagnoses a repeat report.
      console.error("Save failed:", e);
      setSaveStatus(
        isNetworkFailure
          ? "Couldn't reach the server. This can happen if the backend just woke up from being idle — wait a few seconds and try Save again."
          : e.message || "Couldn't save this design."
      );
      setSaving(false);
      setTimeout(() => setSaveStatus(""), 10000); // errors stay up longer than the brief "Saved." confirmation — worth reading
    }
  };

  // Autosave — debounced, only once a property has been explicitly saved
  // at least once (propertyId exists; a brand-new never-saved design
  // still requires one deliberate first Save, so exploring the wizard
  // doesn't silently create abandoned properties), never while locked,
  // and never overlapping a save already in flight. Compares against
  // lastSavedSignatureRef so a successful save's own floor_id backfill
  // (which touches layoutHistory, a dependency below) doesn't re-trigger
  // itself — buildPropertyPayload's floors shape never includes floor_id
  // in the first place, so that backfill doesn't even change the
  // signature, but the explicit comparison is what actually prevents
  // any accidental loop regardless.
  useEffect(() => {
    if (!propertyId || locked) return;

    const currentSignature = JSON.stringify(buildPropertyPayload(propertyName));
    if (currentSignature === lastSavedSignatureRef.current) return;

    if (autosaveTimerRef.current) clearTimeout(autosaveTimerRef.current);
    autosaveTimerRef.current = setTimeout(() => {
      if (!saving) handleSaveDesign(true);
    }, 2500);

    return () => {
      if (autosaveTimerRef.current) clearTimeout(autosaveTimerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- buildPropertyPayload/handleSaveDesign close over the same state already listed here; adding them would just re-run this identically on every render
  }, [propertyId, locked, propertyName, plot, selections, laborSelections, layoutHistory.present, siteElements]);

  const handleLock = async () => {
    if (!propertyId) return;
    const updated = await studioApi.lockProperty(propertyId);
    setLocked(updated.locked);
  };

  const handleRequestUnlock = async () => {
    if (!propertyId) return;
    setUnlockError("");
    await studioApi.requestUnlock(propertyId);
    setUnlockStep("code_sent");
  };

  const handleConfirmUnlock = async () => {
    if (!propertyId) return;
    setUnlockError("");
    try {
      const updated = await studioApi.confirmUnlock(propertyId, unlockCode);
      setLocked(updated.locked);
      setUnlockStep(null);
      setUnlockCode("");
    } catch (e) {
      setUnlockError(e.message || "Incorrect or expired code.");
    }
  };

  const generateDesign = async () => {
    setError("");
    setLoading(true);
    try {
      const payload = {
        plot_size_sqft: plotSizeSqft,
        plot_length_ft: plot.plot_length_ft,
        plot_width_ft: plot.plot_width_ft,
        selections,
        labor_selections: laborSelections,
        region: plot.region,
        currency: plot.currency,
        entrance_direction: plot.entrance_direction,
        road_facing_side: plot.road_facing_side,
        slope_direction: plot.slope_direction === "not_available" ? null : plot.slope_direction,
        master_plan_elements: plot.master_plan_elements || [],
        rooms: rooms
          .filter((r) => r.name.trim())
          .map(({ name, x, y, length, width, color }) => ({ name, x, y, length, width, color })),
        site_elements: siteElements.map((el) => {
          const isLine = el.type in LINE_ELEMENT_DEFS;
          return isLine
            ? { type: el.type, x: el.x, y: el.y, x2: el.x2, y2: el.y2, color: el.color }
            : { type: el.type, x: el.x, y: el.y, length: el.length, width: el.width, color: el.color, rotation: el.rotation || 0 };
        }),
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

  // Downloads a plain array of objects as a CSV file via a Blob + temporary
  // link click — standard browser pattern, no extra dependency needed for
  // something this simple.
  const downloadCsv = (filename, rows) => {
    if (!rows.length) return;
    const headers = Object.keys(rows[0]);
    const escape = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
    const csv = [headers.join(","), ...rows.map((row) => headers.map((h) => escape(row[h])).join(","))].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  };

  const fetchBom = async () => {
    setBomBoqLoading("bom");
    setBomBoqError("");
    try {
      const data = await studioApi.getBillOfMaterials({
        plot_size_sqft: plotSizeSqft,
        selections,
        region: plot.region,
        currency: plot.currency,
      });
      setBom(data);
    } catch (e) {
      setBomBoqError(e.message || "Couldn't load the Bill of Materials.");
    } finally {
      setBomBoqLoading(null);
    }
  };

  const fetchBoq = async () => {
    setBomBoqLoading("boq");
    setBomBoqError("");
    try {
      const data = await studioApi.getBillOfQuantities({
        plot_size_sqft: plotSizeSqft,
        selections,
        labor_selections: laborSelections,
        region: plot.region,
        currency: plot.currency,
      });
      setBoq(data);
    } catch (e) {
      setBomBoqError(e.message || "Couldn't load the Bill of Quantities.");
    } finally {
      setBomBoqLoading(null);
    }
  };

  const fetchAdjacencyReport = async () => {
    setAdjacencyReportLoading(true);
    setAdjacencyReportError("");
    try {
      // Deliberately calls the backend endpoint fresh rather than just
      // reusing the already-computed client-side `adjacencyResult` from
      // the Room Layout step — the whole point of the backend and JS
      // engines sharing identical logic is so a written report can
      // genuinely cross-check the live canvas result, not just echo it
      // back from local state.
      const data = await studioApi.checkAdjacency({
        rooms: rooms.filter((r) => r.name.trim()).map(stripKey),
        style: plot.architectural_style,
      });
      setAdjacencyReport(data);
    } catch (e) {
      setAdjacencyReportError(e.message || "Couldn't load the space-planning report.");
    } finally {
      setAdjacencyReportLoading(false);
    }
  };

  const downloadBomCsv = () => {
    if (!bom) return;
    downloadCsv(
      "bill_of_materials.csv",
      bom.items.map((i) => ({
        Material: i.name, Quantity: i.quantity, Unit: i.unit, Suppliers: i.suppliers.join("; "),
      }))
    );
  };

  const downloadBoqCsv = () => {
    if (!boq) return;
    const rows = [];
    for (const trade of boq.trades) {
      for (const item of trade.items) {
        rows.push({
          Trade: trade.trade, Description: item.description, Type: item.kind,
          Quantity: item.quantity, Unit: item.unit,
          "Unit Rate": item.unit_rate_converted.toFixed(2),
          "Line Total": item.line_total_converted.toFixed(2),
        });
      }
    }
    downloadCsv("bill_of_quantities.csv", rows);
  };

  const canProceedFromPlot = plot.plot_length_ft > 0 && plot.plot_width_ft > 0 && plot.city.trim();
  const canProceedFromMaterials = catalog && Object.keys(selections).length > 0;

  // Jumping BACKWARD to an already-visited step is always allowed (no
  // data is lost by going back). Jumping FORWARD is gated by the exact
  // same conditions the "Next" button already uses below, so clicking a
  // step pill directly and clicking Next behave consistently — no new,
  // separate set of rules to keep in sync.
  const canJumpToStep = (targetStep) => {
    if (targetStep <= step) return true;
    if (targetStep >= 1 && !canProceedFromPlot) return false;
    if (targetStep >= 2 && !canProceedFromMaterials) return false;
    return true;
  };

  return (
    <div className="cs-wizard">
      <div className="cs-steps">
        {STEPS.map((label, i) => {
          const clickable = canJumpToStep(i);
          return (
            <span
              key={label}
              className={`cs-step-pill ${i === step ? "cs-step-active" : i < step ? "cs-step-done" : ""} ${clickable ? "cs-step-pill-clickable" : "cs-step-pill-disabled"}`}
              onClick={() => clickable && setStep(i)}
              role="button"
              tabIndex={clickable ? 0 : -1}
              aria-disabled={!clickable}
              title={clickable ? `Go to ${label}` : "Complete the earlier steps first"}
            >
              {i + 1}. {label}
            </span>
          );
        })}
      </div>

      {error && <div className="studio-status-banner" style={{ background: "#fef2f2", borderColor: "#fecaca", color: "#991b1b" }}>{error}</div>}

      <div className="cs-save-bar">
        <input
          type="text"
          className="cs-property-name-input"
          value={propertyName}
          onChange={(e) => setPropertyName(e.target.value)}
          placeholder="Untitled Property"
          readOnly={locked}
        />
        {locked && <span className="studio-design-lock-badge">🔒 Locked</span>}
        <div className="cs-save-bar-actions">
          {saveStatus && <span className="cs-save-status">{saveStatus}</span>}
          {onStartNew && (
            <button
              type="button"
              className="rc-tool-btn"
              onClick={() => {
                if (window.confirm("Start a new design? Any unsaved changes to this one will be lost.")) {
                  onStartNew();
                }
              }}
              title="Start a fresh design without going back to the designs list"
            >
              + New Design
            </button>
          )}
          {!locked && (
            <button type="button" className="rc-tool-btn" onClick={() => handleSaveDesign(false)} disabled={saving}>
              {saving ? "Saving..." : "Save"}
            </button>
          )}
          {propertyId && !locked && (
            <button type="button" className="rc-tool-btn" onClick={handleLock}>
              🔒 Lock
            </button>
          )}
          {propertyId && locked && unlockStep === null && (
            <button type="button" className="rc-tool-btn" onClick={handleRequestUnlock}>
              Unlock...
            </button>
          )}
          {unlockStep === "code_sent" && (
            <div className="cs-unlock-confirm">
              <input
                type="text"
                placeholder="Code from email"
                value={unlockCode}
                onChange={(e) => setUnlockCode(e.target.value)}
              />
              <button type="button" className="rc-tool-btn" onClick={handleConfirmUnlock}>
                Confirm
              </button>
              <button type="button" className="rc-tool-btn" onClick={() => { setUnlockStep(null); setUnlockCode(""); setUnlockError(""); }}>
                Cancel
              </button>
            </div>
          )}
        </div>
        {unlockError && <div className="cs-unlock-error">{unlockError}</div>}
      </div>

      {overflowWarnings.length > 0 && (
        <div className="cs-overflow-banner">
          <strong>⚠ Fix before generating:</strong>
          <ul>
            {overflowWarnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}

      {step === 0 && (
        <div className="cs-card">
          <h3>Plot Details</h3>
          <div className="cs-field-grid">
            <div className="cs-field">
              <label>City</label>
              <input value={plot.city} onChange={(e) => updatePlotField("city", e.target.value)} placeholder="e.g. Hyderabad" />
            </div>
            <div className="cs-field">
              <label>Country</label>
              <input
                value={plot.country}
                onChange={(e) => updatePlotField("country", e.target.value)}
                placeholder="e.g. India"
                title="Typing a recognized country (India, Thailand, USA) automatically sets the matching region, currency, and unit system below"
              />
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
              <label>Unit System</label>
              <select value={plot.unit_system} onChange={(e) => updatePlotField("unit_system", e.target.value)}>
                {UNIT_SYSTEMS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
            <div className="cs-field">
              <label>Plot Length ({lengthUnitLabel(plot.unit_system)})</label>
              <input
                type="number"
                min="0.1"
                step={plot.unit_system === "metric" ? "0.01" : "1"}
                value={feetToDisplay(plot.plot_length_ft, plot.unit_system)}
                onChange={(e) => updatePlotField("plot_length_ft", displayToFeet(Number(e.target.value), plot.unit_system))}
              />
            </div>
            <div className="cs-field">
              <label>Plot Width ({lengthUnitLabel(plot.unit_system)})</label>
              <input
                type="number"
                min="0.1"
                step={plot.unit_system === "metric" ? "0.01" : "1"}
                value={feetToDisplay(plot.plot_width_ft, plot.unit_system)}
                onChange={(e) => updatePlotField("plot_width_ft", displayToFeet(Number(e.target.value), plot.unit_system))}
              />
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
                <option value="not_available">Not available / unknown</option>
              </select>
            </div>
          </div>
          <p className="studio-subtext">Plot area: <strong>{sqftToDisplayArea(plotSizeSqft, plot.unit_system)} {areaUnitLabel(plot.unit_system)}</strong></p>

          <h4 className="cs-list-heading">Surrounding Site Context</h4>
          <p className="studio-subtext">
            What's around the plot, and in which direction — a river to the northeast, a hill to
            the west. Optional, but useful context for site planning.
          </p>
          {(plot.master_plan_elements || []).map((el, i) => (
            <div className="cs-master-plan-row" key={i}>
              <select value={el.type} onChange={(e) => updateMasterPlanElement(i, "type", e.target.value)}>
                {Object.entries(MASTER_PLAN_ELEMENT_TYPES).map(([type, label]) => (
                  <option key={type} value={type}>{label}</option>
                ))}
              </select>
              <select value={el.direction} onChange={(e) => updateMasterPlanElement(i, "direction", e.target.value)}>
                {DIRECTIONS.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
              <button type="button" className="cs-remove-room" onClick={() => removeMasterPlanElement(i)}>Remove</button>
            </div>
          ))}
          <button type="button" className="cs-add-room-btn" onClick={addMasterPlanElement}>+ Add site context</button>
        </div>
      )}

      {step === 1 && (
        <div className="cs-card">
          <div className="studio-designs-header-row">
            <h3>Materials & Suppliers</h3>
            <button
              type="button"
              className="page-refresh-btn"
              onClick={handleCatalogRefreshClick}
              disabled={catalogRefreshing}
              title="Refresh material prices and availability without leaving the page"
            >
              {catalogRefreshing ? "Refreshing..." : "↻ Refresh"}
            </button>
          </div>
          <p className="studio-subtext">
            Pick one material per category — check off your preferred supplier(s) for reference,
            and see exactly what each option adds to your {sqftToDisplayArea(plotSizeSqft, plot.unit_system)} {areaUnitLabel(plot.unit_system)} plot's total.
          </p>
          {!catalog && <p className="studio-subtext">Loading catalog...</p>}
          {catalog && Object.entries(catalog).map(([catId, cat]) => {
            const filteredOptions = getFilteredOptions(catId, cat.options);
            return (
              <div className="cs-material-category" key={catId}>
                <div className="cs-material-category-header">
                  <h4>{cat.label}</h4>
                  <input
                    type="text"
                    className="cs-supplier-search"
                    placeholder="Search suppliers..."
                    value={supplierSearch[catId] || ""}
                    onChange={(e) => setSupplierSearch((s) => ({ ...s, [catId]: e.target.value }))}
                  />
                </div>
                <div className="cs-material-table-wrap">
                  <table className="cs-material-table">
                    <thead>
                      <tr>
                        <th></th>
                        <th>Material</th>
                        <th>Suppliers</th>
                        <th>Price for your plot</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredOptions.length === 0 && (
                        <tr>
                          <td colSpan={4} className="cs-material-no-results">
                            No materials with a matching supplier in {cat.label}.
                          </td>
                        </tr>
                      )}
                      {filteredOptions.map((opt) => {
                      const isSelected = selections[catId] === opt.id;
                      return (
                        <tr
                          key={opt.id}
                          className={isSelected ? "cs-material-row-selected" : ""}
                          onClick={() => toggleMaterial(catId, opt.id)}
                        >
                          <td>
                            <input
                              type="radio"
                              name={`material-${catId}`}
                              checked={isSelected}
                              onChange={() => toggleMaterial(catId, opt.id)}
                            />
                          </td>
                          <td className="cs-material-table-name">
                            {opt.name}
                            <div className="cs-material-table-unit">{formatUnitPrice(opt.base_cost_usd, opt.unit, plot.currency, fxRates)}</div>
                          </td>
                          <td className="cs-supplier-cell" onClick={(e) => e.stopPropagation()}>
                            {opt.suppliers.map((supplier) => {
                              const isChecked = (supplierPreferences[opt.id] || []).includes(supplier);
                              return (
                                <label
                                  key={supplier}
                                  className={`cs-supplier-check ${isChecked ? "cs-supplier-check-active" : ""}`}
                                >
                                  <input
                                    type="checkbox"
                                    checked={isChecked}
                                    onChange={() => toggleSupplierPreference(opt.id, supplier)}
                                  />
                                  {supplier}
                                </label>
                              );
                            })}
                          </td>
                          <td className="cs-material-table-price">
                            {formatLinePrice(opt.base_cost_usd, plotSizeSqft, plot.currency, fxRates, cat.opening_area_fraction)}
                          </td>
                        </tr>
                      );
                    })}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })}

          {laborCatalog && Object.keys(laborCatalog).length > 0 && (
            <div className="cs-labor-section">
              <h3>Contractor & Labor</h3>
              <p className="studio-subtext">
                Civil contractor rates for the three trades quoted separately in Indian residential
                construction. Optional — leave unselected to rely on the general labor estimate only.
              </p>
              {Object.entries(laborCatalog).map(([catId, cat]) => (
                <div className="cs-material-category" key={catId}>
                  <div className="cs-material-category-header">
                    <h4>{cat.label}</h4>
                  </div>
                  <div className="cs-material-table-wrap">
                    <table className="cs-material-table cs-labor-table">
                      <thead>
                        <tr>
                          <th></th>
                          <th>Option</th>
                          <th>Contractor</th>
                          <th>Price for your plot</th>
                        </tr>
                      </thead>
                      <tbody>
                        {cat.options.map((opt) => {
                          const isSelected = laborSelections[catId] === opt.id;
                          return (
                            <tr
                              key={opt.id}
                              className={isSelected ? "cs-material-row-selected" : ""}
                              onClick={() => toggleLabor(catId, opt.id)}
                            >
                              <td>
                                <input
                                  type="radio"
                                  name={`labor-${catId}`}
                                  checked={isSelected}
                                  onChange={() => toggleLabor(catId, opt.id)}
                                />
                              </td>
                              <td className="cs-material-table-name">
                                {opt.name}
                                <div className="cs-material-table-unit">{formatUnitPrice(opt.base_cost_usd, opt.unit, plot.currency, fxRates)}</div>
                              </td>
                              <td>{opt.suppliers.join(", ")}</td>
                              <td className="cs-material-table-price">
                                {formatLinePrice(opt.base_cost_usd, plotSizeSqft, plot.currency, fxRates)}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {step === 2 && (
        <div className="cs-card">
          <h3>Room Layout</h3>
          <p className="studio-subtext">
            Drag rooms into position, resize via the corner handles, and use Ctrl+Z / Ctrl+Y to
            undo/redo. Naming rooms clearly (e.g. "Kitchen", "Master Bedroom", "Pooja Room")
            enables Vastu compliance checks for that room.
          </p>

          <div className="rc-history-toolbar">
            <button type="button" className="rc-tool-btn" onClick={undo} disabled={layoutHistory.past.length === 0}>
              ↶ Undo
            </button>
            <button type="button" className="rc-tool-btn" onClick={redo} disabled={layoutHistory.future.length === 0}>
              ↷ Redo
            </button>
            {selectedKeys.length > 0 && !locked && (
              <button
                type="button"
                className="rc-tool-btn rc-tool-btn-danger"
                onClick={() => {
                  commitLayout({
                    floors: floors.map((f, i) =>
                      i === activeFloorIndex
                        ? { ...f, rooms: f.rooms.filter((r) => !selectedKeys.includes(r._key)) }
                        : f
                    ),
                    elements: siteElements.filter((el) => !selectedKeys.includes(el._key)),
                  });
                  setSelectedKeys([]);
                }}
              >
                Delete selected ({selectedKeys.length})
              </button>
            )}
            {selectedKeys.length > 0 && (
              <button type="button" className="rc-tool-btn" onClick={copySelection}>
                Copy ({selectedKeys.length})
              </button>
            )}
            {hasClipboard && !locked && (
              <button type="button" className="rc-tool-btn" onClick={pasteClipboard}>
                Paste
              </button>
            )}
          </div>

          <div className="cs-adjacency-bar">
            <label>
              Architectural style:{" "}
              <select
                value={plot.architectural_style}
                onChange={(e) => updatePlotField("architectural_style", e.target.value)}
              >
                {Object.entries(ARCHITECTURAL_STYLE_LABELS).map(([id, label]) => (
                  <option key={id} value={id}>{label}</option>
                ))}
              </select>
            </label>
            {adjacencyResult.findings.filter((f) => f.severity === "warning").length > 0 ? (
              <div className="cs-adjacency-summary cs-adjacency-summary-warning">
                <strong>⚠ Space-planning concerns found:</strong>
                <ul>
                  {adjacencyResult.findings
                    .filter((f) => f.severity === "warning")
                    .map((f, i) => (
                      <li key={i}>
                        <strong>{f.rooms.join(" + ")}</strong> — {f.note}
                      </li>
                    ))}
                </ul>
                <span className="cs-adjacency-hint">
                  The room outlined in red below is one of these — try moving it away from the other, or
                  put a hallway/wall between them.
                </span>
              </div>
            ) : rooms.filter((r) => r.name.trim()).length > 1 ? (
              <span className="cs-adjacency-summary cs-adjacency-summary-good">
                ✓ No adjacency issues found for this layout and style.
              </span>
            ) : null}
          </div>

          {liveVastuResult && (
            <div className="cs-vastu-live-section">
              <h4>{liveVastuResult.scope?.startsWith("thai_") ? "Traditional Building Compliance" : "Vastu Compliance"}</h4>
              <p className="studio-subtext" style={{ marginTop: -8, marginBottom: 10 }}>
                Updates live as you edit the plot direction and room layout — always reflects the current design, not a snapshot from when you last clicked Generate.
              </p>
              {liveVastuResult.scope === "full_multi_rule_check" || liveVastuResult.scope === "thai_traditional_full_check" ? (
                liveVastuResult.findings.map((f, i) => (
                  <div
                    key={i}
                    className={`cs-vastu-finding ${
                      f.severity
                        ? f.severity === "warning"
                          ? "cs-vastu-bad"
                          : f.severity === "good"
                          ? "cs-vastu-good"
                          : "cs-vastu-neutral"
                        : f.note.includes("advises against") || f.note.includes("recommends keeping open")
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
                liveVastuResult.notes.map((n, i) => (
                  <div key={i} className="cs-vastu-finding cs-vastu-neutral">{n}</div>
                ))
              )}
            </div>
          )}

          <div className="rc-floor-tabs">
            {floors.map((floor, i) => (
              <div key={floor.floor_id || `new-${i}`} className={`rc-floor-tab ${i === activeFloorIndex ? "rc-floor-tab-active" : ""}`}>
                <input
                  type="text"
                  value={floor.floor_label}
                  onClick={() => {
                    setActiveFloorIndex(i);
                    setSelectedKeys([]);
                  }}
                  onChange={(e) => renameFloor(i, e.target.value)}
                  readOnly={locked}
                />
                {floors.length > 1 && !locked && (
                  <button type="button" className="rc-floor-tab-remove" onClick={() => removeFloor(i)} aria-label={`Remove ${floor.floor_label}`}>
                    ×
                  </button>
                )}
              </div>
            ))}
            {!locked && (
              <button type="button" className="rc-floor-tab-add" onClick={addFloor}>
                + Floor
              </button>
            )}
          </div>

          <div className="rc-element-toolbar">
            <span className="rc-element-toolbar-label">Add to site plan:</span>
            {Object.entries(ELEMENT_DEFS).map(([type, def]) => (
              <button
                key={type}
                type="button"
                className="rc-tool-btn"
                onClick={() => addElement(type)}
                disabled={locked}
                style={{ borderLeft: `4px solid ${def.color}` }}
              >
                {def.label}
              </button>
            ))}
            {Object.entries(LINE_ELEMENT_DEFS).map(([type, def]) => (
              <button key={type} type="button" className="rc-tool-btn" onClick={() => addElement(type)} disabled={locked}>
                {def.label}
              </button>
            ))}
          </div>

          <Suspense fallback={<p className="studio-subtext">Loading room editor...</p>}>
            <RoomCanvas
              plotLengthFt={plot.plot_length_ft}
              plotWidthFt={plot.plot_width_ft}
              roadFacingSide={plot.road_facing_side}
              rooms={rooms}
              onRoomsChange={commitRooms}
              siteElements={siteElements}
              onElementsChange={commitElements}
              selectedKeys={selectedKeys}
              onSelectionChange={setSelectedKeys}
              locked={locked}
              roomAdjacencyStatus={roomAdjacencyStatus}
              architecturalStyle={plot.architectural_style}
              country={plot.country}
              entranceDirection={plot.entrance_direction}
            />
          </Suspense>

          {siteElements.length > 0 && (
            <>
              <h4 className="cs-list-heading">Site Elements</h4>
              <div className="cs-room-table-scroll">
              <div className="cs-room-row cs-room-row-header">
                <span>Element</span><span>Length ({lengthUnitLabel(plot.unit_system)}) / Style</span><span>Width ({lengthUnitLabel(plot.unit_system)}) / Thickness</span><span>Fill / Line color</span><span>Border style</span><span>Border color</span><span>Border thickness</span><span></span>
              </div>
              <div className="cs-scrollable-list">
                {siteElements.map((el) => {
                  const isLine = el.type in LINE_ELEMENT_DEFS;
                  const label = isLine ? LINE_ELEMENT_DEFS[el.type].label : ELEMENT_DEFS[el.type].label;
                  return (
                    <div
                      className={`cs-room-row ${selectedKeys.includes(el._key) ? "cs-room-row-selected" : ""}`}
                      key={el._key}
                      onClick={() => setSelectedKeys([el._key])}
                    >
                      <span className="cs-element-label">{label}</span>
                      {isLine ? (
                        <>
                          <select
                            value={el.dash_style || "solid"}
                            onChange={(e) => updateElement(el._key, "dash_style", e.target.value)}
                            onClick={(e) => e.stopPropagation()}
                          >
                            {Object.entries(LINE_DASH_STYLE_LABELS).map(([style, styleLabel]) => (
                              <option key={style} value={style}>{styleLabel}</option>
                            ))}
                          </select>
                          <input
                            type="number"
                            min="0.5"
                            max="6"
                            step="0.5"
                            value={el.stroke_width || 1.5}
                            title="Thickness (px)"
                            onChange={(e) => updateElement(el._key, "stroke_width", Number(e.target.value))}
                            onClick={(e) => e.stopPropagation()}
                          />
                        </>
                      ) : (
                        <>
                          <input
                            type="number"
                            value={feetToDisplay(el.length, plot.unit_system)}
                            onChange={(e) => updateElement(el._key, "length", displayToFeet(Number(e.target.value), plot.unit_system))}
                          />
                          <input
                            type="number"
                            value={feetToDisplay(el.width, plot.unit_system)}
                            onChange={(e) => updateElement(el._key, "width", displayToFeet(Number(e.target.value), plot.unit_system))}
                          />
                        </>
                      )}
                      {isLine ? (
                        <input
                          type="color"
                          className="cs-line-color-input"
                          value={el.color || "#111827"}
                          onChange={(e) => updateElement(el._key, "color", e.target.value)}
                          onClick={(e) => e.stopPropagation()}
                        />
                      ) : (
                        <span />
                      )}
                      {isLine ? (
                        <>
                          <span /><span /><span />
                        </>
                      ) : (
                        <>
                          <select
                            value={el.border_style || "solid"}
                            onChange={(e) => updateElement(el._key, "border_style", e.target.value)}
                            onClick={(e) => e.stopPropagation()}
                          >
                            {Object.entries(LINE_DASH_STYLE_LABELS).map(([style, styleLabel]) => (
                              <option key={style} value={style}>{styleLabel}</option>
                            ))}
                          </select>
                          <input
                            type="color"
                            className="cs-line-color-input"
                            value={el.border_color || "#6b7280"}
                            title="Border color (leave default to keep the standard look)"
                            onChange={(e) => updateElement(el._key, "border_color", e.target.value)}
                            onClick={(e) => e.stopPropagation()}
                          />
                          <input
                            type="number"
                            min="0.5"
                            max="6"
                            step="0.5"
                            placeholder="auto"
                            value={el.border_width || ""}
                            title="Border thickness (px)"
                            onChange={(e) => updateElement(el._key, "border_width", e.target.value === "" ? null : Number(e.target.value))}
                            onClick={(e) => e.stopPropagation()}
                          />
                        </>
                      )}
                      <button className="cs-remove-room" onClick={() => removeElement(el._key)}>Remove</button>
                    </div>
                  );
                })}
              </div>
              </div>
            </>
          )}

          <h4 className="cs-list-heading">Rooms</h4>
          <div className="cs-room-table-scroll">
          <div className="cs-room-row cs-room-row-header">
            <span>Room name</span><span>Length ({lengthUnitLabel(plot.unit_system)})</span><span>Width ({lengthUnitLabel(plot.unit_system)})</span><span>Fill</span><span>Border style</span><span>Border color</span><span>Thickness</span><span></span>
          </div>
          <div className="cs-scrollable-list">
            {rooms.map((room) => (
              <div
                className={`cs-room-row ${selectedKeys.includes(room._key) ? "cs-room-row-selected" : ""}`}
                key={room._key}
                onClick={() => setSelectedKeys([room._key])}
              >
                <input placeholder="Kitchen" value={room.name} onChange={(e) => updateRoom(room._key, "name", e.target.value)} />
                <input
                  type="number"
                  placeholder={`Length (${lengthUnitLabel(plot.unit_system)})`}
                  value={feetToDisplay(room.length, plot.unit_system)}
                  onChange={(e) => updateRoom(room._key, "length", displayToFeet(Number(e.target.value), plot.unit_system))}
                />
                <input
                  type="number"
                  placeholder={`Width (${lengthUnitLabel(plot.unit_system)})`}
                  value={feetToDisplay(room.width, plot.unit_system)}
                  onChange={(e) => updateRoom(room._key, "width", displayToFeet(Number(e.target.value), plot.unit_system))}
                />
                <div className="cs-room-color-swatches" onClick={(e) => e.stopPropagation()}>
                  {ROOM_COLOR_PALETTE.map((color) => (
                    <button
                      key={color}
                      type="button"
                      className={`cs-room-color-swatch ${room.color === color ? "cs-room-color-swatch-active" : ""}`}
                      style={{ background: color }}
                      onClick={() => updateRoom(room._key, "color", color)}
                      aria-label={`Set room color ${color}`}
                    />
                  ))}
                </div>
                <select
                  value={room.border_style || "solid"}
                  onChange={(e) => updateRoom(room._key, "border_style", e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                >
                  {Object.entries(LINE_DASH_STYLE_LABELS).map(([style, styleLabel]) => (
                    <option key={style} value={style}>{styleLabel}</option>
                  ))}
                </select>
                <input
                  type="color"
                  className="cs-line-color-input"
                  value={room.border_color || "#374151"}
                  title="Border color (leave default to keep the standard wall look)"
                  onChange={(e) => updateRoom(room._key, "border_color", e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                />
                <input
                  type="number"
                  min="0.5"
                  max="6"
                  step="0.5"
                  placeholder="auto"
                  value={room.border_width || ""}
                  title="Border thickness (px) — leave blank to use the real wall thickness"
                  onChange={(e) => updateRoom(room._key, "border_width", e.target.value === "" ? null : Number(e.target.value))}
                  onClick={(e) => e.stopPropagation()}
                />
                <button className="cs-remove-room" onClick={() => removeRoom(room._key)}>Remove</button>
              </div>
            ))}
          </div>
          </div>
          <button className="cs-add-room-btn" onClick={addRoom} disabled={locked}>+ Add room</button>
        </div>
      )}

      {step === 3 && (
        <div className="cs-card">
          <h3>Review & Generate</h3>

          {Object.keys(selections).length > 0 && (
            <div className="cs-bom-boq-section">
              <h4>Documents</h4>
              <p className="studio-subtext">
                A Bill of Materials (what to order, and how much) and a Bill of Quantities (the full
                trade-by-trade cost breakdown for tendering/contracts) — available as soon as materials
                are selected, no need to generate the full design first.
              </p>
              <div className="cs-bom-boq-buttons">
                <button type="button" className="rc-tool-btn" onClick={fetchBom} disabled={bomBoqLoading === "bom"}>
                  {bomBoqLoading === "bom" ? "Loading..." : "View Bill of Materials"}
                </button>
                <button type="button" className="rc-tool-btn" onClick={fetchBoq} disabled={bomBoqLoading === "boq"}>
                  {bomBoqLoading === "boq" ? "Loading..." : "View Bill of Quantities"}
                </button>
              </div>

              {bomBoqError && <div className="studio-status-banner" style={{ background: "#fef2f2", borderColor: "#fecaca", color: "#991b1b" }}>{bomBoqError}</div>}

              {bom && (
                <div className="cs-bom-boq-table-wrap">
                  <div className="cs-bom-boq-table-header">
                    <h5>Bill of Materials</h5>
                    <button type="button" className="rc-tool-btn" onClick={downloadBomCsv}>Download CSV</button>
                  </div>
                  <table className="cs-bom-boq-table">
                    <thead>
                      <tr><th>Material</th><th>Quantity</th><th>Unit</th><th>Suppliers</th></tr>
                    </thead>
                    <tbody>
                      {bom.items.map((item, i) => (
                        <tr key={i}>
                          <td>{item.name}</td>
                          <td>{item.quantity.toLocaleString()}</td>
                          <td>{item.unit}</td>
                          <td>{item.suppliers.join(", ")}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {boq && (
                <div className="cs-bom-boq-table-wrap">
                  <div className="cs-bom-boq-table-header">
                    <h5>Bill of Quantities</h5>
                    <button type="button" className="rc-tool-btn" onClick={downloadBoqCsv}>Download CSV</button>
                  </div>
                  {boq.trades.map((trade, ti) => (
                    <div key={ti} className="cs-boq-trade">
                      <div className="cs-boq-trade-header">
                        <strong>{trade.trade}</strong>
                        <span>{boq.currency} {trade.subtotal_converted.toLocaleString()}</span>
                      </div>
                      <table className="cs-bom-boq-table">
                        <thead>
                          <tr><th>Description</th><th>Type</th><th>Qty</th><th>Unit</th><th>Rate</th><th>Total</th></tr>
                        </thead>
                        <tbody>
                          {trade.items.map((item, i) => (
                            <tr key={i}>
                              <td>{item.description}</td>
                              <td>{item.kind}</td>
                              <td>{item.quantity.toLocaleString()}</td>
                              <td>{item.unit}</td>
                              <td>{item.unit_rate_converted.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                              <td>{item.line_total_converted.toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ))}
                  <div className="cs-boq-grand-total">
                    Grand total: {boq.currency} {boq.grand_total_converted.toLocaleString()}
                  </div>
                </div>
              )}
            </div>
          )}

          {rooms.filter((r) => r.name.trim()).length > 0 && (
            <div className="cs-bom-boq-section">
              <h4>Space-Planning Report</h4>
              <p className="studio-subtext">
                A written, independently-verified check of your room layout against the selected
                architectural style — the same rules shown live on the Room Layout page, confirmed
                fresh here for the record.
              </p>
              <button type="button" className="rc-tool-btn" onClick={fetchAdjacencyReport} disabled={adjacencyReportLoading}>
                {adjacencyReportLoading ? "Loading..." : "View Space-Planning Report"}
              </button>

              {adjacencyReportError && (
                <div className="studio-status-banner" style={{ background: "#fef2f2", borderColor: "#fecaca", color: "#991b1b" }}>
                  {adjacencyReportError}
                </div>
              )}

              {adjacencyReport && (
                <div className="cs-bom-boq-table-wrap">
                  {adjacencyReport.compliant ? (
                    <div className="cs-adjacency-summary cs-adjacency-summary-good">
                      ✓ No space-planning issues found for this layout and style.
                    </div>
                  ) : (
                    <div className="cs-adjacency-summary cs-adjacency-summary-warning">
                      <strong>⚠ Space-planning concerns found:</strong>
                      <ul>
                        {adjacencyReport.findings
                          .filter((f) => f.severity === "warning")
                          .map((f, i) => (
                            <li key={i}>
                              <strong>{f.rooms.join(" + ")}</strong> — {f.note}
                            </li>
                          ))}
                      </ul>
                    </div>
                  )}
                  {adjacencyReport.findings.filter((f) => f.severity === "good").length > 0 && (
                    <div className="cs-adjacency-summary cs-adjacency-summary-good" style={{ marginTop: 10 }}>
                      <strong>✓ Positive placements:</strong>
                      <ul>
                        {adjacencyReport.findings
                          .filter((f) => f.severity === "good")
                          .map((f, i) => (
                            <li key={i}>
                              <strong>{f.rooms.join(" + ")}</strong> — {f.note}
                            </li>
                          ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {!result && (
            <>
              <p className="studio-subtext">
                Plot: {feetToDisplay(plot.plot_length_ft, plot.unit_system)}{lengthUnitLabel(plot.unit_system)} × {feetToDisplay(plot.plot_width_ft, plot.unit_system)}{lengthUnitLabel(plot.unit_system)} in {plot.city || "your city"} ·{" "}
                {Object.keys(selections).length} material{Object.keys(selections).length === 1 ? "" : "s"} selected ·{" "}
                {rooms.filter((r) => r.name.trim()).length} room(s)
              </p>
              <button className="cs-nav-btn cs-nav-primary" onClick={generateDesign} disabled={loading || overflowWarnings.length > 0}>
                {loading ? "Generating..." : overflowWarnings.length > 0 ? "Fix layout errors above first" : "Generate Design"}
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

      <PlotPreview
        plotLengthFt={plot.plot_length_ft}
        plotWidthFt={plot.plot_width_ft}
        roadFacingSide={plot.road_facing_side}
        rooms={rooms}
        siteElements={siteElements}
      />

      {estimate && Object.keys(selections).length > 0 && !result && (
        <div className="cs-floating-total">
          <span className="cs-total-label">Running estimate ({plot.currency})</span>
          <span className="cs-total-value">
            {plot.currency} {estimate.grand_total_converted.toLocaleString()}
          </span>
        </div>
      )}
    </div>
  );
}

export default ConstructionStudio;
