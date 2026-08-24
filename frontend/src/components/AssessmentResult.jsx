import { useEffect, useState } from "react";
import FraudIntelligenceStatic from "./FraudIntelligenceStatic";
import CollapsiblePanel from "./CollapsiblePanel";
import StudioPromoCard from "../studio/StudioPromoCard";
import SimilarPropertiesWidget from "../studio/SimilarPropertiesWidget";
import { getGovernmentValueLabel } from "../utils/governmentValueLabels";
import { studioApi, getSession } from "../studio/studioApi";

function AssessmentResult({
  result,
  formData,
  reportId,
  onLaunchStudio
}) {
  const [reportLoading, setReportLoading] = useState(false);

  // Backs a real, reported gap: there was no obvious link between
  // generating a report and buying the Insight Add-on at all — the
  // only path was a collapsed "Similar Property Insights" panel further
  // down the page that, once expanded and clicked, routed to the
  // generic Studio pricing page rather than starting checkout directly.
  // This checks unlock status on load (silently, via getSession — no
  // error shown if not signed in, since that's a normal state here, not
  // a failure) so the purchase button doesn't show for a report that's
  // already unlocked.
  const [insightState, setInsightState] = useState("checking"); // "checking" | "unlocked" | "not_unlocked" | "starting_checkout" | "error"
  const [insightPriceUsd, setInsightPriceUsd] = useState(null);

  useEffect(() => {
    studioApi.getTiers()
      .then((tiers) => setInsightPriceUsd(tiers.insight_addon?.price_usd ?? null))
      .catch(() => {}); // price display is a nice-to-have, not critical path
  }, []);

  useEffect(() => {
    if (!reportId) {
      setTimeout(() => setInsightState("not_unlocked"), 0);
      return;
    }
    if (!getSession()) {
      setTimeout(() => setInsightState("not_unlocked"), 0); // not signed in yet — button still shows, prompts sign-in when clicked
      return;
    }
    let cancelled = false;
    studioApi.getInsightStatus(reportId)
      .then((res) => {
        if (!cancelled) setInsightState(res.unlocked ? "unlocked" : "not_unlocked");
      })
      .catch(() => {
        if (!cancelled) setInsightState("not_unlocked"); // fails open to showing the button, not a hard error state
      });
    return () => { cancelled = true; };
  }, [reportId]);

  const handleBuyInsight = async () => {
    if (!getSession()) {
      onLaunchStudio(); // routes to sign-in first
      return;
    }
    setInsightState("starting_checkout");
    try {
      const res = await studioApi.insightCheckout(reportId);
      if (res.checkout_url) {
        // Backs a real, deliberate fix: without this, the report
        // (which only ever lived in React state, never persisted
        // server-side — reportId itself is a client-generated UUID,
        // not something the backend can look up) was lost entirely on
        // the full-page-reload checkout redirect requires, leaving the
        // user on the plain homepage with only a message telling them
        // to re-enter the whole property form again just to see what
        // they'd paid for. Persisting it here lets the app restore the
        // exact same report automatically on return, already unlocked
        // — no redundant "go redo this" message needed at all.
        sessionStorage.setItem("propertyiq_pending_report", JSON.stringify({ result, formData, reportId }));
        window.location.href = res.checkout_url;
        return;
      }
      // Beta-bypass path (no real checkout_url returned) — access was granted immediately
      setInsightState("unlocked");
    } catch (err) {
      console.warn("Couldn't start Insight Add-on checkout:", err);
      setInsightState("error");
    }
  };

  if (!result) return null;

  // The report's currency should reflect the PROPERTY's country (what
  // the assessment is actually about), not the visitor's own location —
  // someone assessing an Indian property from the US should still see
  // Indian Rupee pricing, not USD. Was previously 100% hardcoded to INR
  // regardless of the property's actual country — a real gap for any
  // non-Indian property (e.g. Thailand, seeded via /th).
  const CURRENCY_BY_COUNTRY = {
    "india": { code: "INR", symbol: "₹", locale: "en-IN" },
    "thailand": { code: "THB", symbol: "฿", locale: "th-TH" },
    "usa": { code: "USD", symbol: "$", locale: "en-US" },
    "united states": { code: "USD", symbol: "$", locale: "en-US" },
    "philippines": { code: "PHP", symbol: "₱", locale: "en-PH" },
    "vietnam": { code: "VND", symbol: "₫", locale: "vi-VN" },
    "indonesia": { code: "IDR", symbol: "Rp", locale: "id-ID" },
  };
  const currencyInfo = CURRENCY_BY_COUNTRY[(formData.country || "").trim().toLowerCase()]
    || { code: "USD", symbol: "$", locale: "en-US" };

  const governmentValueLabel = getGovernmentValueLabel(formData.country);

  const formatCurrency = (value) => {
    if (value === null || value === undefined || isNaN(value)) return `${currencyInfo.symbol}0`;

    // India keeps its own genuinely standard crore/lakh convention —
    // not applicable anywhere else, so only INR uses it. Every other
    // currency uses the widely-understood M/K (million/thousand)
    // abbreviation instead of inventing a India-specific one for them.
    if (currencyInfo.code === "INR") {
      if (value >= 10000000) return `₹${(value / 10000000).toFixed(2)} Cr`;
      if (value >= 100000) return `₹${(value / 100000).toFixed(2)} L`;
      return `₹${new Intl.NumberFormat("en-IN").format(value)}`;
    }

    if (value >= 1000000) return `${currencyInfo.symbol}${(value / 1000000).toFixed(2)}M`;
    if (value >= 1000) return `${currencyInfo.symbol}${(value / 1000).toFixed(1)}K`;
    return `${currencyInfo.symbol}${new Intl.NumberFormat(currencyInfo.locale).format(value)}`;
  };

  const formatPerSqft = (value) => {
    if (value === null || value === undefined || isNaN(value)) return `${currencyInfo.symbol}0 / sqft`;
    return `${currencyInfo.symbol}${value.toLocaleString(currencyInfo.locale)} / sqft`;
  };

  // Kept as an alias so any call site not yet updated below still works
  // correctly rather than throwing — genuinely currency-aware now,
  // despite the India-specific name staying for now to limit the size
  // of this change (a rename sweep can happen separately, unrelated to
  // the actual bug this fixes).
  const formatIndianCurrency = formatCurrency;

  const downloadReport = async () => {
    if (reportLoading) return;

    try {

      setReportLoading(true);

      const response = await fetch(
        "https://propertyiq-api-q21y.onrender.com/generate-report",
        {
          method: "POST",

          headers: {
            "Content-Type": "application/json"
          },

          body: JSON.stringify({
            country: formData.country,

            stateProvince:
                formData.stateProvince,

            city:
                formData.city,

            location:
                formData.location,

            propertyName:
              formData.propertyName,

            propertyType: 
              formData.propertyType,

            developerName:
              formData.developerName,

            quotedPrice:
              Number(formData.quotedPrice),

            governmentGuidance:
              Number(formData.governmentGuidance),

            marketAverage:
              Number(formData.marketAverage),

            unitArea:
              Number(formData.areaValue),

            areaUnit:
              formData.areaUnit,

            monthlyRent:
              Number(formData.monthlyRent || 0),

            totalUnits:
              formData.totalUnits === ""
                  ? null
                  : Number(formData.totalUnits),

          unsoldUnits:
              formData.unsoldUnits === ""
                  ? null
                  : Number(formData.unsoldUnits),

          projectsCompleted:
              formData.projectsCompleted === ""
                  ? null
                  : Number(formData.projectsCompleted),

          projectsDelayed:
              formData.projectsDelayed === ""
                  ? null
                  : Number(formData.projectsDelayed),

          yearsInBusiness:
              formData.yearsInBusiness === ""
                  ? null
                  : Number(formData.yearsInBusiness),

          regulatoryViolations:
              formData.regulatoryViolations === ""
                  ? null
                  : Number(formData.regulatoryViolations),
          })
        }
      );

      if (!response.ok) {
          throw new Error("Failed to generate report.");
      }

      const blob =
        await response.blob();

      const url =
        window.URL.createObjectURL(blob);

      const link =
        document.createElement("a");

      link.href = url;

      link.download =
        "PropertyIQ_Report.pdf";

      document.body.appendChild(link);

      link.click();

      link.remove();

      window.URL.revokeObjectURL(url);

    } catch (error) {

      console.error(error);

      alert("Failed to generate PropertyIQ report.");
    }
    finally {
        setReportLoading(false);
    }
  };

  return (
    <CollapsiblePanel title="Your PropertyIQ Report" defaultOpen={true} color="violet">
    <div className="card result-card">

      <div className="score-section">

        <div
          style={{
            maxWidth: "1000px",
            margin: "0 auto 25px",
            padding: "28px",
            background: "#ffffff",
            border: "2px solid #1e3a8a",
            borderRadius: "18px",
            textAlign: "center"
          }}
        >

          <div
            style={{
              fontSize: "13px",
              letterSpacing: "2px",
              color: "#64748b",
              fontWeight: "700"
            }}
          >
            PROPERTYIQ DECISION SUMMARY
          </div>

          <div
            style={{
              marginTop: "20px",
              padding: "18px",
              background: "#f8fafc",
              borderRadius: "12px",
              textAlign: "left"
            }}
          >

            <div
              style={{
                fontSize: "20px",
                fontWeight: "700",
                marginBottom: "12px",
                color: "#1e3a8a"
              }}
            >
              {result.decision.category}
            </div>

            <div
              style={{
                display: "flex",
                gap: "12px",
                marginTop: "14px",
                marginBottom: "18px",
                flexWrap: "wrap"
              }}
            >

              <div
                style={{
                  background: "#dcfce7",
                  color: "#166534",
                  padding: "8px 14px",
                  borderRadius: "20px",
                  fontWeight: "700",
                  fontSize: "14px"
                }}
              >
                ✓ {result.decision.propertyQuality}
              </div>

              <div
                style={{
                  background: "#fef3c7",
                  color: "#92400e",
                  padding: "8px 14px",
                  borderRadius: "20px",
                  fontWeight: "700",
                  fontSize: "14px"
                }}
              >
                ⚠ {result.decision.dealQuality}
              </div>

            </div>    

            <div
              style={{
                color: "#475569",
                lineHeight: "1.8",
                fontSize: "15px"
              }}
            >
              {result.decision.narrative}
            </div>

          </div>

          <div
          style={{
            marginTop: "18px",
            fontSize: "15px",
            color: "#475569"
          }}
        >
          <strong>Recommended Action</strong>

          <div
            style={{
              fontSize: "22px",
              fontWeight: "700",
              marginTop: "6px"
            }}
          >
            {result.decision.action}
          </div>
        </div>

           <div
            style={{
              fontSize: "58px",
              fontWeight: "800",
              color: "#1e3a8a",
              marginTop: "18px"
            }}
          >
            {result.score}
          </div>

          <div
            style={{
              fontSize: "18px",
              color: "#64748b",
              marginTop: "6px"
            }}
          >
            Buyer Protection Score
          </div>

          <div
            style={{
              display: "inline-block",
              marginTop: "16px",
              padding: "8px 18px",
              borderRadius: "20px",
              background: "#dcfce7",
              fontWeight: "700",
              color: "#166534"
            }}
          >
            {result.rating}
          </div>    


        </div>

        <div
          style={{
            maxWidth: "700px",
            margin: "20px auto",
            padding: "24px",
            background: "#ffffff",
            border: "1px solid #e5e7eb",
            borderRadius: "16px"
          }}
        >

          <div
            style={{
              fontSize: "12px",
              letterSpacing: "2px",
              fontWeight: "700",
              color: "#64748b",
              marginBottom: "18px"
            }}
          >
            PRICING INTELLIGENCE
          </div>

          <div className="finding-item">
            <strong>Quoted Price</strong>
            <p>{formatIndianCurrency(formData.quotedPrice)}</p>
          </div>

          <div className="finding-item">
            <strong>Quoted Price / sqft</strong>
            <p>
              {formatPerSqft(result.quotedPricePerSqft)}
            </p>
          </div>

          <div className="finding-item">
            <strong>PropertyIQ Fair Value</strong>
            <p>{formatIndianCurrency(result.fairValue)}</p>
          </div>

          <div className="finding-item">
            <strong>Fair Value / sqft</strong>
            <p>
              {formatPerSqft(result.fairValuePerSqft)}
            </p>
          </div>

          <div className="finding-item">
            <strong>City Comparable Benchmark</strong>
            <p>
              {formatPerSqft(result.marketAveragePricePerSqft)}
            </p>
          </div>

          <div className="finding-item">
            <strong>{governmentValueLabel.shortLabel}</strong>
            <p>
              {formatPerSqft(result.governmentRatePerUnit)}
            </p>
          </div>

          <div
            style={{
              marginTop: "18px",
              padding: "16px",
              background: "#f8fafc",
              borderRadius: "10px",
              color: "#475569",
              lineHeight: "1.7",
              fontSize: "14px"
            }}
          >
            <strong>PropertyIQ Insight</strong>

            <br /><br />

            The quoted price is approximately{" "}
            <strong>
              {(() => {

                  const difference =
                      (
                          (Number(formData.quotedPrice) - result.fairValue)
                          / result.fairValue
                      ) * 100;

                  if (difference >= 0) {
                      return (
                          <>
                              <strong>{difference.toFixed(2)}%</strong> above the estimated fair value.
                          </>
                      );
                  }

                  return (
                      <>
                          <strong>{Math.abs(difference).toFixed(2)}%</strong> below the estimated fair value.
                      </>
                  );

              })()}
            </strong>
            {" "}

            Government guidance values are primarily used
            for property registration and should not be
            interpreted as market value.
          </div>

        </div> 

        <div
          style={{
            maxWidth: "700px",
            margin: "35px auto 0",
            padding: "24px",
            background: "#f8fafc",
            border: "1px solid #e5e7eb",
            borderRadius: "16px"
          }}
        >

          <div
            style={{
              fontSize: "12px",
              letterSpacing: "2px",
              fontWeight: "700",
              color: "#64748b",
              marginBottom: "10px"
            }}
          >
            DEAL QUALITY
          </div>

          <div
            style={{
              fontSize: "28px",
              fontWeight: "800",
              color: "#0f172a",
              marginBottom: "12px"
            }}
          >
            {result.dealQuality}
          </div>

          <div
            style={{
              color: "#64748b",
              lineHeight: "1.7",
              fontSize: "15px"
            }}
          >
            {result.dealQualityReason}
          </div>

        </div>

      </div>

      <div
        style={{
          maxWidth: "700px",
          margin: "20px auto",
          padding: "24px",
          background: "#ffffff",
          border: "1px solid #e5e7eb",
          borderRadius: "16px"
        }}
      >

        <div
          style={{
            fontSize: "12px",
            letterSpacing: "2px",
            fontWeight: "700",
            color: "#64748b",
            marginBottom: "18px"
          }}
        >
          GOVERNMENT INTELLIGENCE
        </div>

        <div className="finding-item">
          <strong>{governmentValueLabel.label}</strong>
          <p>
            {formatPerSqft(result.governmentRatePerUnit)}
          </p>
        </div>

        <div className="finding-item">
          <strong>Estimated Government Value</strong>
          <p>
            {formatIndianCurrency(result.governmentPropertyValue)}
          </p>
        </div>

        <div className="finding-item">
          <strong>Government Source</strong>
          <p>{result.governmentReference}</p>
        </div>

        <div className="finding-item">
          <strong>Data Confidence</strong>
          <p>{result.governmentConfidence}</p>
        </div>

        <div
          style={{
            marginTop: "18px",
            padding: "16px",
            background: "#f8fafc",
            borderRadius: "10px",
            color: "#475569",
            lineHeight: "1.7",
            fontSize: "14px"
          }}
        >
          <strong>PropertyIQ Insight</strong>

          <br /><br />

          {result.governmentBuyerObservation}
        </div>

      </div>

      <div
        style={{
          maxWidth: "700px",
          margin: "20px auto 0",
          padding: "24px",
          background: "#eff6ff",
          border: "1px solid #bfdbfe",
          borderRadius: "16px"
        }}
      >

        <div
          style={{
            fontSize: "12px",
            letterSpacing: "2px",
            fontWeight: "700",
            color: "#1d4ed8",
            marginBottom: "10px"
          }}
        >
          NEGOTIATION ADVISOR
        </div>

        <div
          style={{
            fontSize: "28px",
            fontWeight: "800",
            color: "#0f172a",
            marginBottom: "15px"
          }}
        >
          {result.negotiationPosition}
        </div>

        <p
          style={{
            color: "#64748b",
            lineHeight: "1.7",
            marginBottom: "15px"
          }}
        >
          {result.negotiationReason}
        </p>

        <div style={{ marginTop: "15px" }}>

          <div className="finding-item">
            <strong>Target Purchase Price</strong>
            <p>{formatIndianCurrency(result.targetPrice)}</p>
          </div>

          <div className="finding-item">
            <strong>Recommended Negotiation Range</strong>
            <p>
              {formatIndianCurrency(result.lowOffer)}
              {" - "}
              {formatIndianCurrency(result.highOffer)}
            </p>
          </div>

          <div className="finding-item">
            <strong>Estimated Buyer Savings</strong>
            <p>{formatIndianCurrency(result.potentialSavings)}</p>
          </div>

      </div>

      </div>      


      <div
        style={{
          maxWidth: "700px",
          margin: "20px auto 0",
          padding: "24px",
          background: "#f0fdf4",
          border: "1px solid #bbf7d0",
          borderRadius: "16px"
        }}
      >

        <div
          style={{
            fontSize: "12px",
            letterSpacing: "2px",
            fontWeight: "700",
            color: "#15803d",
            marginBottom: "10px"
          }}
        >
          BUYER ADVANTAGE METER
        </div>

        <div
          style={{
            fontSize: "42px",
            fontWeight: "800",
            color: "#0f172a"
          }}
        >
          {result.buyerAdvantageScore} / 100
        </div>

        <div
          style={{
            fontSize: "22px",
            fontWeight: "700",
            color: "#15803d",
            marginTop: "8px",
            marginBottom: "15px"
          }}
        >
          {result.buyerAdvantageRating}
        </div>

        <div
          style={{
            color: "#64748b",
            lineHeight: "1.7",
            fontSize: "15px"
          }}
        >
          {result.buyerAdvantageReason}
        </div>

      </div>    

      <div
  style={{
    maxWidth: "700px",
    margin: "20px auto 0",
    padding: "24px",
    background: "#eff6ff",
    border: "1px solid #bfdbfe",
    borderRadius: "16px"
  }}
>

      <div
        style={{
          fontSize: "12px",
          letterSpacing: "2px",
          fontWeight: "700",
          color: "#2563eb",
          marginBottom: "10px"
        }}
      >
        RECOMMENDATION CONFIDENCE
      </div>

      <div
        style={{
          fontSize: "42px",
          fontWeight: "800",
          color: "#0f172a"
        }}
      >
        {result.recommendationConfidenceScore} / 100
      </div>

      <div
        style={{
          fontSize: "22px",
          fontWeight: "700",
          color: "#2563eb",
          marginTop: "8px",
          marginBottom: "15px"
        }}
      >
        {result.recommendationConfidenceRating}
      </div>

      <div
        style={{
          color: "#64748b",
          lineHeight: "1.7",
          fontSize: "15px"
        }}
      >
        {result.recommendationConfidenceReason}
      </div>

    </div>    


      <div className="metrics-grid">

        <div className="metric-card">
          <h4>Fair Value</h4>
          <p>
            {formatIndianCurrency(
              result.fairValue
            )}
          </p>
        </div>

        <div className="metric-card">
          <h4>Developer Rating</h4>
          <p>
            {result.developerRating === "NOT_ASSESSED"
              ? "Not Assessed"
              : result.developerRating}
          </p>
        </div>

        <div className="metric-card">
          <h4>Inventory Risk</h4>
          <p>
            {result.inventoryRisk === "NOT_ASSESSED"
              ? "Not Assessed"
              : result.inventoryRisk}
          </p>
        </div>

      </div>



      <div className="report-sections-grid">

      <CollapsiblePanel title="Score Breakdown" defaultOpen={true} color="neutral">
        <div className="finding-item">
          <strong>
            Valuation Analysis
          </strong>
          <p>
            {result.valuationScore}
          </p>
        </div>

        <div className="finding-item">
          <strong>
            Inventory Risk
          </strong>
          <p>
            {result.inventoryScore}
          </p>
        </div>

        <div className="finding-item">
          <strong>
            Developer Quality
          </strong>
          <p>
            {result.developerScore}
          </p>
        </div>

        <div
      style={{
        marginTop: "15px",
        fontSize: "14px",
        color: "#6b7280",
        lineHeight: "1.7"
      }}
    >
      Scores range from 0–100.
      Higher scores indicate lower buyer risk.

      <br /><br />

      90–100 → Excellent
      <br />
      80–89 → Strong
      <br />
      70–79 → Fair
      <br />
      60–69 → Caution
      <br />
      Below 60 → High Risk
    </div>

      </CollapsiblePanel>

      <CollapsiblePanel title="Why This Recommendation" defaultOpen={true} color="neutral">
        {result.recommendationReasons?.map(
          (reason, index) => (
            <div
              key={index}
              className="finding-item"
            >
              <p>
                • {reason}
              </p>
            </div>
          )
        )}

      </CollapsiblePanel>

<CollapsiblePanel title="City Comparable Benchmarks" defaultOpen={false} color="neutral">
  <div className="finding-item">

    <strong>
      Average City Comparable Price
    </strong>

    <p>
      {result.marketAveragePricePerSqft > 0
        ? formatPerSqft(result.marketAveragePricePerSqft)
        : "Not Available"}
    </p>

  </div>

  <div className="finding-item">

    <strong>
      Comparable Market Value
    </strong>

    <p>
      {result.marketAveragePricePerSqft > 0
        ? formatIndianCurrency(
            result.marketAveragePricePerSqft *
            (
              formData.areaUnit === "acre"
                ? Number(formData.areaValue) * 43560
                : Number(formData.areaValue || 0)
            )
          )
        : "Not Available"}
    </p>

  </div>

    {result.comparables?.length === 0 && (

      <div
        className="finding-item"
      >
        <p>
          No comparable projects are currently
          available for this property type.
        </p>
      </div>

    )}

  {result.comparables?.map(
    (project, index) => (
      <div
        key={index}
        className="finding-item"
      >

        <strong>
          {project.projectName}
        </strong>

        <p>
          {project.developer}
          <br />
          {formatPerSqft(project.pricePerSqft)}
        </p>

      </div>
    )
  )}

    <div
    style={{
      marginTop: "15px",
      fontSize: "14px",
      color: "#6b7280",
      lineHeight: "1.7"
    }}
  >

    PropertyIQ Fair Value is derived using the user-provided market average together with 
    applicable valuation models such as rental yield when sufficient 
    evidence is available. {governmentValueLabel.shortLabel} is reported separately as regulatory 
    reference information and is not used to determine Fair Value.

    <br /><br />

    Market asking prices reflect current
    seller expectations and may differ
    from intrinsic value.

  </div>

</CollapsiblePanel>

<CollapsiblePanel title="How PropertyIQ Works" defaultOpen={false} color="neutral">
  <div className="finding-item">

    <strong>
      Buyer Protection Score
    </strong>

    <p>
      ✓ Valuation Analysis (50%)
      <br />
      ✓ Inventory Risk (30%)
      <br />
      ✓ Developer Quality (20%)
    </p>

    <p
      style={{
        marginTop: "12px",
        color: "#6b7280",
        fontSize: "14px",
        lineHeight: "1.7"
      }}
    >
      Valuation receives the highest
      weight because purchase price
      has the largest direct impact on
      buyer outcomes.

      <br /><br />

      Inventory risk influences future
      appreciation potential and resale
      liquidity.

      <br /><br />

      Developer quality evaluates
      delivery history, execution
      capability, and regulatory
      compliance.
    </p>

  </div>

  <div className="finding-item">

    <strong>
      Valuation Approach
    </strong>

    <p>
      User Market Average
      <br />
      <br />

      Supporting Valuation Models
      <br />
      • Comparable Sales (when available)
      <br />
      • Rental Yield (when available)
      <br />
      • Replacement Cost (when available)
    </p>

  </div>

  <div className="finding-item">

    <strong>
      Inventory Analysis
    </strong>

    <p>
      Total Units
      <br />
      Unsold Units
    </p>

  </div>

  <div className="finding-item">

    <strong>
      Developer Analysis
    </strong>

    <p>
      Delivery History
      <br />
      Years In Business
      <br />
      Regulatory Compliance
    </p>

  </div>

  <div
    style={{
      marginTop: "20px",
      paddingTop: "15px",
      borderTop: "1px solid #e5e7eb",
      fontSize: "13px",
      color: "#6b7280",
      fontStyle: "italic"
    }}
  >
    These weights represent the current
    PropertyIQ assessment methodology
    and may evolve as additional market
    intelligence and performance data
    become available.
  </div>

</CollapsiblePanel>

      <CollapsiblePanel title="Key Findings" defaultOpen={true} color="neutral">

        <div className="finding-item">
          <strong>
            Pricing Analysis
          </strong>
          <p>
            {result.findings?.pricing}
          </p>
        </div>

        <div className="finding-item">
          <strong>
            Inventory Analysis
          </strong>
          <p>
            {result.findings?.inventory}
          </p>
        </div>

        <div className="finding-item">
          <strong>
            Developer Analysis
          </strong>
          <p>
            {result.findings?.developer}
          </p>
        </div>

      </CollapsiblePanel>

      </div>

      <div className="recommendation-card">

        <div className="recommendation-title">
          FINAL RECOMMENDATION
        </div>

        <div className="recommendation-value">
          {result.recommendation}
        </div>

        <div className="recommendation-text">
          {result.findings?.overall}
        </div>

        <button
          className="download-report-btn"
          onClick={downloadReport}
          disabled={true}
        >
          {reportLoading && (
            <span className="spinner"></span>
          )}

          {reportLoading
            ? "Generating Report..."
            : "Download PropertyIQ Report"}
        </button>

        {insightState === "unlocked" ? (
          <p className="recommendation-insight-unlocked">
            ✅ Similar-property insights are unlocked for this report — see them further down the page.
          </p>
        ) : (
          <div className="recommendation-insight-cta">
            <p className="recommendation-insight-desc">
              See how this property's price compares to similar ones nearby, with real
              comparable pricing from actual listings{insightPriceUsd != null ? ` — one-time $${insightPriceUsd}` : ""}.
            </p>
            <button
              className="download-report-btn recommendation-insight-btn"
              onClick={handleBuyInsight}
              disabled={insightState === "starting_checkout"}
            >
              {insightState === "starting_checkout" && <span className="spinner"></span>}
              {insightState === "starting_checkout"
                ? "Starting checkout..."
                : "Unlock Similar-Property Insights"}
            </button>
          </div>
        )}
        {insightState === "error" && (
          <p className="recommendation-insight-error">
            Couldn't start checkout — please try again in a moment.
          </p>
        )}

      </div>


      <CollapsiblePanel title="Similar Property Insights" defaultOpen={false} color="blue">
        <SimilarPropertiesWidget
          reportId={reportId}
          city={formData.city}
          propertyType={formData.propertyType}
          subjectPricePerSqft={result.quotedPricePerSqft}
        />
      </CollapsiblePanel>

      <CollapsiblePanel title="PropertyIQ Studio" defaultOpen={false} color="purple">
        <StudioPromoCard onLaunch={onLaunchStudio} />
      </CollapsiblePanel>

      <CollapsiblePanel title="Fraud Intelligence" defaultOpen={false} color="red">
        <FraudIntelligenceStatic />
      </CollapsiblePanel>

    </div>
    </CollapsiblePanel>
  );
}

export default AssessmentResult;