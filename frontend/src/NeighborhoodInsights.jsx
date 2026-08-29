import { useState, useRef, useEffect } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "./App.css";

const API_BASE = "https://propertyiq-api-q21y.onrender.com";

// Same LocationIQ endpoints/key convention AccidentIQ's own Travel Safety
// page uses (confirmed directly from that page's real source, shared by
// the user) — NOT Google Places. Autocomplete, nearby-place search, and
// map tiles all come from LocationIQ; Leaflet (a free, keyless library)
// does the actual map rendering.
// Map tiles are still loaded with the key directly in the URL (an
// inherent, industry-wide pattern for slippy-map tile layers — even
// Google Maps' own JS API keys are visible in page source the same
// way); mitigated by restricting the key to this app's own domain(s)
// in LocationIQ's dashboard, not by hiding it from client code, which
// isn't possible for a tile URL. Autocomplete and nearby-place lookups
// go through this app's own backend instead (see api.py's own comment
// for why: LocationIQ's CORS policy blocks direct browser fetch() calls
// to those endpoints from this app's domain — confirmed directly, not
// assumed — and proxying through the backend also keeps the key out of
// those specific requests' client-side code).
const LOCATIONIQ_TILE_KEY = "pk.8ef6f17e9de67368976f46de2135d2d9";

// Same OSM-style "key:value" tag format LocationIQ's own /nearby endpoint
// expects (confirmed from AccidentIQ's real POI_CATEGORIES) — adapted to
// the 7 categories relevant to buying a property, not traveling one.
const POI_CATEGORIES = [
  { key: "hospital", label: "Hospitals", tag: "amenity:hospital", color: "#D14343", icon: "🏥" },
  { key: "school", label: "Schools", tag: "amenity:school", color: "#2A9D8F", icon: "🏫" },
  { key: "market", label: "Markets", tag: "shop:supermarket", color: "#C9821E", icon: "🛒" },
  { key: "bank", label: "Banks/ATMs", tag: "amenity:bank", color: "#7B61FF", icon: "🏦" },
  { key: "police", label: "Police", tag: "amenity:police", color: "#0F2540", icon: "👮" },
  { key: "transport", label: "Public Transport", tag: "amenity:bus_station", color: "#1D6FB8", icon: "🚌" },
  { key: "park", label: "Parks", tag: "leisure:park", color: "#059669", icon: "🌳" },
];

const CHECKLIST_ITEMS = [
  "Verify the title deed and confirm a clear, marketable title with no encumbrances",
  "Check RERA registration for the project (for under-construction or recently completed properties)",
  "Confirm the occupancy certificate (OC) and completion certificate (CC) have been issued",
  "Get an encumbrance certificate covering at least the last 13-30 years",
  "Review property tax receipts to confirm they're current and in the seller's name",
  "Check for any pending litigation or disputes tied to the property or land",
  "Confirm the approved building plan matches the actual construction",
  "Verify khata/mutation records reflect the current owner correctly",
];

const AUTHORITY_CONTACTS = [
  { label: "RERA (state) helpline", detail: "Varies by state — search \"[your state] RERA helpline\"" },
  { label: "Sub-Registrar's Office", detail: "Handles registration and encumbrance certificates" },
  { label: "Municipal Corporation / Panchayat", detail: "Property tax records, building plan approvals" },
  { label: "State Consumer Helpline", detail: "1915" },
];

function timeoutFetch(url, ms = 6000) {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), ms);
  return fetch(url, { signal: controller.signal }).finally(() => clearTimeout(t));
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function gmapsPlaceLink(name, lat, lon) {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(name)}+${lat},${lon}`;
}

// Standalone page, not part of the main app's navigation, reached at
// /neighborhood-insights. Mirrors the structure of the sibling AccidentIQ
// product's own Travel Safety page (same section order, same standalone-
// tool-that-cross-sells-the-main-product pattern), with PropertyIQ's own
// navy/emerald theme. The map/nearby-places feature below reuses
// AccidentIQ's own real LocationIQ-based approach (confirmed from its
// actual source, not guessed) rather than the Google Places API
// originally (and wrongly) assumed before that source was shared.
function NeighborhoodInsights() {
  // Deliberately separate from the geocoded search below: a property's
  // own name/label is never required to exist in any map database (a
  // brand-new, not-yet-built project genuinely won't), so it's plain
  // free text here — purely for display, never sent to LocationIQ.
  const [propertyName, setPropertyName] = useState("");
  const [addressQuery, setAddressQuery] = useState("");
  const [addressSuggestions, setAddressSuggestions] = useState([]);
  const [selectedPlace, setSelectedPlace] = useState(null); // { label, lat, lon }
  const [city, setCity] = useState("");
  const [propertyType, setPropertyType] = useState("Apartment");
  const [submitted, setSubmitted] = useState(false);
  const [resaleSignal, setResaleSignal] = useState(null);
  const [resaleState, setResaleState] = useState("idle"); // "idle" | "loading" | "done" | "error"
  const [validationError, setValidationError] = useState("");

  const [poiState, setPoiState] = useState("idle"); // "idle" | "loading" | "done"
  const [poiDataByCat, setPoiDataByCat] = useState({});
  const [failedCategories, setFailedCategories] = useState([]);
  const [activeCategory, setActiveCategory] = useState(null);

  const mapRef = useRef(null);
  const mapContainerRef = useRef(null);
  const markersByCatRef = useRef({});
  const debounceRef = useRef(null);

  // Autocomplete against LocationIQ, same debounce/limit/countrycodes
  // pattern as AccidentIQ's own attachAutocomplete.
  const handleAddressInput = (value) => {
    setAddressQuery(value);
    setSelectedPlace(null);
    clearTimeout(debounceRef.current);
    if (value.trim().length < 3) {
      setAddressSuggestions([]);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const url = `${API_BASE}/api/neighborhood-insights/autocomplete?q=${encodeURIComponent(value)}`;
        const res = await fetch(url);
        const data = await res.json();
        setAddressSuggestions(Array.isArray(data) ? data : []);
      } catch {
        setAddressSuggestions([]);
      }
    }, 300);
  };

  const selectSuggestion = (item) => {
    const label = item.display_name || item.display_place || addressQuery;
    setAddressQuery(label);
    setSelectedPlace({ label, lat: parseFloat(item.lat), lon: parseFloat(item.lon) });
    setAddressSuggestions([]);
  };

  const handleShowInsights = async () => {
    if (!selectedPlace || !city.trim()) {
      setValidationError("Please select a nearby known address/locality from the suggestions (even for a brand-new project, search the closest main road or area name), and enter a city, to see neighborhood insights.");
      return;
    }
    setValidationError("");
    setSubmitted(true);
    setResaleState("loading");
    try {
      const res = await fetch(`${API_BASE}/api/neighborhood-insights/resale-signal?city=${encodeURIComponent(city)}&property_type=${encodeURIComponent(propertyType)}`);
      const data = await res.json();
      setResaleSignal(data);
      setResaleState("done");
    } catch {
      setResaleState("error");
    }
  };

  // Loads the map + all category markers once a place has been submitted
  // — same overall shape as AccidentIQ's renderRouteAndPOIs + loadPOIs,
  // adapted from a multi-waypoint route to a single property point.
  useEffect(() => {
    if (!submitted || !selectedPlace) return;

    let justCreated = false;
    if (!mapRef.current) {
      justCreated = true;
      mapRef.current = L.map(mapContainerRef.current).setView([selectedPlace.lat, selectedPlace.lon], 15);
      L.tileLayer(`https://{s}-tiles.locationiq.com/v3/streets/r/{z}/{x}/{y}.png?key=${LOCATIONIQ_TILE_KEY}`, {
        attribution: '&copy; <a href="https://locationiq.com">LocationIQ</a> &copy; OpenStreetMap contributors',
        maxZoom: 19,
      }).addTo(mapRef.current);
    } else {
      mapRef.current.setView([selectedPlace.lat, selectedPlace.lon], 15);
    }

    if (justCreated) {
      // A real, well-known Leaflet issue, not a guess: a map created the
      // instant its container is mounted often measures that container
      // as zero-size (the browser hasn't finished laying it out yet),
      // which is what "loads broken/partial until you interact with it"
      // actually is. invalidateSize() forces Leaflet to re-measure and
      // redraw against the container's real, final dimensions. Called
      // once immediately and once after a short delay to also catch the
      // results section's own scroll-into-view, which can still be
      // settling the layout a beat later.
      mapRef.current.invalidateSize();
      setTimeout(() => mapRef.current && mapRef.current.invalidateSize(), 300);
    }

    const markerLabel = propertyName.trim() || selectedPlace.label;
    L.marker([selectedPlace.lat, selectedPlace.lon]).addTo(mapRef.current).bindPopup(`<b>${markerLabel}</b><br>${selectedPlace.label}`);

    let cancelled = false;

    const loadPOIs = async () => {
      setPoiState("loading");
      setActiveCategory(null);
      const newMarkersByCat = {};
      const newDataByCat = {};
      const newFailed = [];

      const loadOneCategory = async (cat) => {
        newMarkersByCat[cat.key] = [];
        newDataByCat[cat.key] = [];
        try {
          const url = `${API_BASE}/api/neighborhood-insights/nearby?lat=${selectedPlace.lat}&lon=${selectedPlace.lon}&tag=${encodeURIComponent(cat.tag)}&radius=2000`;
          const res = await timeoutFetch(url, 6000);
          const data = await res.json();
          if (Array.isArray(data)) {
            data.slice(0, 8).forEach((place) => {
              if (place.lat && place.lon && !cancelled) {
                const marker = L.circleMarker([place.lat, place.lon], {
                  radius: 6, color: cat.color, fillColor: cat.color, fillOpacity: 0.85, weight: 1,
                }).addTo(mapRef.current).bindPopup(`${cat.icon} <b>${place.name || cat.label}</b>`);
                newMarkersByCat[cat.key].push(marker);
                newDataByCat[cat.key].push({ name: place.name || cat.label, lat: parseFloat(place.lat), lon: parseFloat(place.lon) });
              }
            });
            return true;
          }
          return false;
        } catch {
          return false;
        }
      };

      // LocationIQ's free tier allows roughly 2 requests/second (same
      // limit AccidentIQ's own loadPOIs paces against) — fetching 2
      // categories at once, then pausing, respects that same real
      // constraint while roughly halving the previous fully-sequential
      // wait (7 categories x 550ms was several real seconds on its own,
      // before any network time — a genuine, reported slowness this
      // batching directly addresses). Markers appear on the map after
      // each batch, not only once all 7 finish, so the map visibly does
      // something well before the whole sequence completes.
      const BATCH_SIZE = 2;
      for (let i = 0; i < POI_CATEGORIES.length; i += BATCH_SIZE) {
        const batch = POI_CATEGORIES.slice(i, i + BATCH_SIZE);
        const results = await Promise.all(batch.map(loadOneCategory));
        batch.forEach((cat, idx) => {
          if (!results[idx]) newFailed.push(cat.key);
        });
        if (cancelled) return;
        // Progressive update so the map/legend reflect what's loaded so
        // far, not just the final state once every category is done.
        markersByCatRef.current = { ...markersByCatRef.current, ...newMarkersByCat };
        setPoiDataByCat((prev) => ({ ...prev, ...newDataByCat }));
        if (i + BATCH_SIZE < POI_CATEGORIES.length) await sleep(550);
      }

      if (cancelled) return;
      setFailedCategories(newFailed);
      setPoiState("done");
    };

    loadPOIs();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- propertyName is intentionally excluded: it only affects the marker popup's label text, and adding it here would re-run the entire map/POI-loading sequence (a fresh round of nearby-place API calls) just because the user edited a display label, not the actual location being searched
  }, [submitted, selectedPlace]);

  const resetHighlighting = () => {
    Object.values(markersByCatRef.current).forEach((markers) => {
      markers.forEach((m) => m.setStyle({ radius: 6, fillOpacity: 0.85, weight: 1 }));
    });
  };

  // Same toggle-highlight-and-list behavior as AccidentIQ's own
  // selectCategory: clicking the active category again clears it;
  // clicking a different one highlights its markers, dims the rest, and
  // lists its real places with a "Directions" link per place.
  const selectCategory = (catKey) => {
    if (activeCategory === catKey) {
      resetHighlighting();
      setActiveCategory(null);
      return;
    }
    setActiveCategory(catKey);
    Object.entries(markersByCatRef.current).forEach(([key, markers]) => {
      markers.forEach((m) => {
        if (key === catKey) {
          m.setStyle({ radius: 9, fillOpacity: 1, weight: 2 });
          m.bringToFront();
        } else {
          m.setStyle({ radius: 6, fillOpacity: 0.15, weight: 1 });
        }
      });
    });
  };

  const googleMapsUrl = selectedPlace
    ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(selectedPlace.label)}`
    : "#";
  const shareText = propertyName.trim()
    ? `Check out the neighborhood insights for ${propertyName.trim()} before buying: https://propertyiqweb.com/neighborhood-insights.html`
    : `Check out this neighborhood insights tool before buying a property: https://propertyiqweb.com/neighborhood-insights.html`;
  const activeCat = POI_CATEGORIES.find((c) => c.key === activeCategory);
  const activePlaces = activeCategory ? poiDataByCat[activeCategory] || [] : [];

  return (
    <div className="ni-page">
      <div className="ni-top-banner">
        🏠 Ready to buy? <a href="/">Get your free Instant Property Score with PropertyIQ →</a>
      </div>

      <div className="ni-nav">
        <span className="ni-nav-brand">LivingIQ · Neighborhood Insights</span>
        <div className="ni-nav-links">
          <a href="https://livingiqweb.com">← Back to LivingIQ</a>
          <a href="/">PropertyIQ →</a>
        </div>
      </div>

      <div className="ni-hero">
        <h1>Know your neighborhood, before you buy</h1>
        <p>
          See hospitals, schools, markets, banks, and public transport near a property, plus a
          buyer's due-diligence checklist and resale demand signal — all in one place, before you decide.
        </p>
      </div>

      <div className="ni-form-card">
        <div className="ni-form-row">
          <div className="ni-form-field">
            <label>Property / project name <span className="ni-optional-tag">(optional)</span></label>
            <input value={propertyName} onChange={(e) => setPropertyName(e.target.value)} placeholder="e.g. Prestige Skyline (fine even if it's a new launch, not yet mapped)" />
          </div>
        </div>
        <div className="ni-form-row">
          <div className="ni-form-field ni-autocomplete-field">
            <label>Nearest known address, road, or locality</label>
            <input value={addressQuery} onChange={(e) => handleAddressInput(e.target.value)} placeholder="e.g. Kompally, or the nearest main road" autoComplete="off" />
            <p className="ni-field-hint">For a brand-new project not yet on the map, search the closest known area or road instead — insights are about the surrounding neighborhood either way.</p>
            {addressSuggestions.length > 0 && (
              <div className="ni-autocomplete-list">
                {addressSuggestions.map((s, i) => (
                  <div key={i} className="ni-autocomplete-item" onClick={() => selectSuggestion(s)}>
                    {s.display_name || s.display_place}
                  </div>
                ))}
              </div>
            )}
          </div>
          <div className="ni-form-field">
            <label>City</label>
            <input value={city} onChange={(e) => setCity(e.target.value)} placeholder="e.g. Hyderabad" />
          </div>
        </div>
        <div className="ni-form-row">
          <div className="ni-form-field">
            <label>Property type</label>
            <select value={propertyType} onChange={(e) => setPropertyType(e.target.value)}>
              <option>Apartment</option>
              <option>Villa</option>
              <option>Plot</option>
            </select>
          </div>
        </div>
        <button className="ni-primary-btn" onClick={handleShowInsights}>Show neighborhood insights</button>
        {validationError && <p className="ni-validation-error">{validationError}</p>}
      </div>

      {submitted && (
        <>
          <div className="ni-map-card">
            <h3>Your neighborhood</h3>
            <div className="ni-category-chips">
              {POI_CATEGORIES.map((c) => (
                <button
                  key={c.key}
                  type="button"
                  className={`ni-chip ni-chip-btn ${activeCategory === c.key ? "ni-chip-active" : ""}`}
                  onClick={() => selectCategory(c.key)}
                  disabled={poiState !== "done"}
                >
                  <span className="ni-chip-dot" style={{ background: c.color }} /> {c.icon} {c.label}
                </button>
              ))}
            </div>

            {poiState === "loading" && <p className="ni-coming-soon">Loading nearby places...</p>}

            <div ref={mapContainerRef} className="ni-leaflet-map" />

            {activeCategory && (
              <div className="ni-poi-details">
                <div className="ni-poi-details-header">
                  <strong>{activeCat.icon} {activeCat.label} near this property</strong>
                  <button type="button" className="ni-poi-details-close" onClick={() => selectCategory(activeCategory)}>×</button>
                </div>
                {activePlaces.length === 0 ? (
                  <p className="ni-coming-soon">No live results for this category right now — try the link below instead.</p>
                ) : (
                  <ul className="ni-poi-details-list">
                    {activePlaces.map((p, i) => (
                      <li key={i}>
                        <span>{p.name}</span>
                        <a href={gmapsPlaceLink(p.name, p.lat, p.lon)} target="_blank" rel="noopener noreferrer">Directions →</a>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {poiState === "done" && failedCategories.length > 0 && selectedPlace && (
              <div className="ni-poi-fallback-grid">
                {failedCategories.map((key) => {
                  const cat = POI_CATEGORIES.find((c) => c.key === key);
                  return (
                    <a key={key} className="ni-fallback-btn" href={gmapsPlaceLink(cat.label, selectedPlace.lat, selectedPlace.lon)} target="_blank" rel="noopener noreferrer">
                      {cat.icon} Find {cat.label.toLowerCase()} →
                    </a>
                  );
                })}
              </div>
            )}

            <a href={googleMapsUrl} target="_blank" rel="noopener noreferrer" className="ni-text-link">Open this location in Google Maps →</a>
          </div>

          <div className="ni-card">
            <h3>☔ Flood & waterlogging risk</h3>
            <p className="ni-coming-soon">Coming soon — this needs a municipal drainage/flood-history data source this app doesn't have connected yet.</p>
          </div>

          <div className="ni-card">
            <h3>🏗️ Upcoming infrastructure</h3>
            <p className="ni-coming-soon">Coming soon — metro lines, highways, and planned commercial development near this address, once a data source is connected.</p>
          </div>

          <div className="ni-card">
            <h3>📈 Resale demand signal</h3>
            {resaleState === "loading" && <p>Checking comparable listings...</p>}
            {resaleState === "error" && <p className="ni-coming-soon">Couldn't load this right now — please try again.</p>}
            {resaleState === "done" && resaleSignal && resaleSignal.has_data && (
              <div className="ni-resale-result">
                <div className="ni-resale-stat">
                  <span className="ni-resale-number">{resaleSignal.comparable_count}</span>
                  <span className="ni-resale-label">comparable {propertyType.toLowerCase()} listing{resaleSignal.comparable_count === 1 ? "" : "s"} tracked in {city}</span>
                </div>
                <div className="ni-resale-stat">
                  <span className="ni-resale-number">₹{resaleSignal.average_price_per_sqft.toLocaleString("en-IN")}</span>
                  <span className="ni-resale-label">average price/sq ft ({resaleSignal.data_source === "live" ? "live market data" : "recent snapshot"})</span>
                </div>
              </div>
            )}
            {resaleState === "done" && resaleSignal && !resaleSignal.has_data && (
              <p className="ni-coming-soon">No comparable listing data for {city} yet — this app currently covers a growing set of cities, not all of them.</p>
            )}
          </div>

          <div className="ni-card">
            <h3>✅ Buyer's due-diligence checklist</h3>
            <ul className="ni-checklist">
              {CHECKLIST_ITEMS.map((item) => <li key={item}>{item}</li>)}
            </ul>
          </div>

          <div className="ni-card">
            <h3>📞 Local authority contacts</h3>
            <ul className="ni-contact-list">
              {AUTHORITY_CONTACTS.map((c) => (
                <li key={c.label}><strong>{c.label}:</strong> {c.detail}</li>
              ))}
            </ul>
          </div>

          <div className="ni-cta-card">
            <h3>📋 PropertyIQ — Instant Property Score</h3>
            <p>Get a full price, location, and red-flag check on this property — free, no signup needed for the first check.</p>
            <ul>
              <li>🤖 AI-powered price and location scoring in seconds</li>
              <li>🚩 Red flags checked against real comparable listings</li>
              <li>📊 Backed by the same data shown in this report</li>
            </ul>
            <a href="/" className="ni-primary-btn ni-cta-btn">Try PropertyIQ →</a>
          </div>

          <div className="ni-share-card">
            <h3>👨‍👩‍👧 Share this neighborhood report</h3>
            <p>Let your family or co-buyer see this before you decide — it takes 10 seconds.</p>
            <div className="ni-share-buttons">
              <a href={`https://wa.me/?text=${encodeURIComponent(shareText)}`} target="_blank" rel="noopener noreferrer" className="ni-share-btn">Share via WhatsApp</a>
              <a href={`sms:?body=${encodeURIComponent(shareText)}`} className="ni-share-btn">Share via SMS</a>
            </div>
          </div>
        </>
      )}

      <div className="ni-footer">
        A free tool by PropertyIQ — Know Before You Buy.
      </div>
    </div>
  );
}

export default NeighborhoodInsights;
