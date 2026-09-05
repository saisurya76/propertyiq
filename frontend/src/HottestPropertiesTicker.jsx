import { useEffect, useState } from "react";

const API_BASE = "https://propertyiq-api-q21y.onrender.com";

const CURRENCY_SYMBOL_BY_COUNTRY = {
  india: "₹", thailand: "฿", philippines: "₱", vietnam: "₫", indonesia: "Rp",
};

function HottestPropertiesTicker({ country }) {
  const [properties, setProperties] = useState(null);
  const currencySymbol = CURRENCY_SYMBOL_BY_COUNTRY[(country || "").toLowerCase()] || "";

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/api/homepage/hottest-properties?country=${encodeURIComponent(country)}&limit=10`)
      .then((res) => res.json())
      .then((data) => { if (!cancelled) setProperties(data.properties); })
      .catch(() => { if (!cancelled) setProperties([]); });
    return () => { cancelled = true; };
  }, [country]);

  // Genuinely no data for this country (not yet covered by the real,
  // static comparables dataset this pulls from) -- the ticker simply
  // doesn't render, rather than showing an empty or broken bar.
  if (!properties || properties.length === 0) return null;

  // Duplicated once so the CSS marquee animation can scroll from 0% to
  // -50% and loop seamlessly, instead of visibly snapping back to the
  // start every cycle.
  const doubled = [...properties, ...properties];

  return (
    <div className="hottest-ticker" aria-label={`Featured property listings in ${country}, by price per square foot`}>
      <span className="hottest-ticker-label">🔥 Featured in {country}</span>
      <div className="hottest-ticker-track-wrap">
        <div className="hottest-ticker-track">
          {doubled.map((p, i) => (
            <span className="hottest-ticker-item" key={i}>
              <strong>{p.project_name}</strong> · {p.city} · {currencySymbol}{p.price_per_sqft.toLocaleString()}/sqft
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

export default HottestPropertiesTicker;
