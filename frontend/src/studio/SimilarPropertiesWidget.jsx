import { useState } from "react";
import { studioApi, getSession } from "./studioApi";

function SimilarPropertiesWidget({ reportId, city, propertyType, subjectPricePerSqft, onNeedAccess }) {
  const [state, setState] = useState("idle"); // "idle" | "loading" | "locked" | "loaded" | "error"
  const [data, setData] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");

  const load = async () => {
    setState("loading");
    setErrorMessage("");
    try {
      const result = await studioApi.getSimilarProperties(reportId, { city, propertyType, subjectPricePerSqft });
      setData(result);
      setState("loaded");
    } catch (err) {
      if (err.status === 403) {
        setState("locked");
      } else if (err.status === 401) {
        setState("locked"); // not signed in — same CTA path (sign in, then unlock)
      } else {
        setErrorMessage(err.message || "Couldn't load similar properties.");
        setState("error");
      }
    }
  };

  const handleUnlock = () => {
    if (!getSession()) {
      onNeedAccess(); // routes to sign-in first
      return;
    }
    onNeedAccess(); // routes to pricing to buy the Insight Add-on
  };

  if (state === "idle") {
    return (
      <div className="sp-widget">
        <p className="studio-subtext">
          See how this property compares to others like it on price per sqft.
        </p>
        <button className="studio-cta-btn" onClick={load}>
          View Similar Properties
        </button>
      </div>
    );
  }

  if (state === "loading") {
    return (
      <div className="sp-widget">
        <p className="studio-subtext">Loading...</p>
      </div>
    );
  }

  if (state === "locked") {
    return (
      <div className="sp-widget">
        <div className="sp-locked">
          <p>
            Unlock similar property suggestions for this report with the Insight Add-on,
            or with any active PropertyIQ Studio subscription.
          </p>
          <button className="studio-cta-btn" onClick={handleUnlock}>
            Unlock Similar Property Insights
          </button>
        </div>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="sp-widget">
        <p className="studio-subtext">{errorMessage}</p>
      </div>
    );
  }

  // state === "loaded"
  if (data.coverage === "unsupported") {
    return (
      <div className="sp-widget">
        <div className="sp-unsupported">
          We don't have comparable property data for {city} yet, so we can't show similar
          properties for this report. This coverage is expanding — check back for this city soon.
        </div>
      </div>
    );
  }

  return (
    <div className="sp-widget">
      <p className="sp-market-avg">
        Market average in {city}: <strong>₹{data.market_average_price_per_sqft?.toLocaleString("en-IN")}/sqft</strong>
      </p>
      <div className="sp-list">
        {data.suggestions.map((s, i) => (
          <div className="sp-row" key={i}>
            <div>
              <div className="sp-name">{s.project_name}</div>
              <div className="sp-developer">{s.developer}</div>
            </div>
            <div className="sp-price">
              ₹{s.price_per_sqft?.toLocaleString("en-IN")}/sqft
              <div className={s.price_diff_percent <= 0 ? "sp-diff-cheaper" : "sp-diff-pricier"}>
                {s.price_diff_percent > 0 ? "+" : ""}
                {s.price_diff_percent}% vs your price
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default SimilarPropertiesWidget;
