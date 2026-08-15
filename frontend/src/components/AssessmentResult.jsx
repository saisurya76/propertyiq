import { useState } from "react";
import FraudIntelligenceStatic from "./FraudIntelligenceStatic";
import StudioPromoCard from "../studio/StudioPromoCard";

function AssessmentResult({
  result,
  formData,
  onLaunchStudio
}) {
  if (!result) return null;

  const [reportLoading, setReportLoading] = useState(false);

  const formatIndianCurrency = (value) => {
    if (value >= 10000000) {
      return `₹${(value / 10000000).toFixed(2)} Cr`;
    }

    if (value >= 100000) {
      return `₹${(value / 100000).toFixed(2)} L`;
    }

    return `₹${new Intl.NumberFormat("en-IN").format(value)}`;
  };

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
    <div className="card result-card">

      <div className="score-section">

        <div
          style={{
            maxWidth: "700px",
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
              ₹{result.quotedPricePerSqft?.toLocaleString("en-IN")} / sqft
            </p>
          </div>

          <div className="finding-item">
            <strong>PropertyIQ Fair Value</strong>
            <p>{formatIndianCurrency(result.fairValue)}</p>
          </div>

          <div className="finding-item">
            <strong>Fair Value / sqft</strong>
            <p>
              ₹{result.fairValuePerSqft?.toLocaleString("en-IN")} / sqft
            </p>
          </div>

          <div className="finding-item">
            <strong>City Comparable Benchmark</strong>
            <p>
              ₹{result.marketAveragePricePerSqft?.toLocaleString("en-IN")} / sqft
            </p>
          </div>

          <div className="finding-item">
            <strong>Government Guidance</strong>
            <p>
              ₹{result.governmentRatePerUnit?.toLocaleString("en-IN")} / sqft
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
          <strong>Government Guidance Rate</strong>
          <p>
            ₹{result.governmentRatePerUnit?.toLocaleString("en-IN")} / sqft
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



      <div className="findings-card">

        <div className="findings-title">
          SCORE BREAKDOWN
        </div>

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

      </div>

      <div className="findings-card">

        <div className="findings-title">
          WHY THIS RECOMMENDATION
        </div>

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

      </div>

<div className="findings-card">

  <div className="findings-title">
    CITY COMPARABLE BENCHMARKS
  </div>

  <div className="finding-item">

    <strong>
      Average City Comparable Price
    </strong>

    <p>
      {result.marketAveragePricePerSqft > 0
        ? `₹${result.marketAveragePricePerSqft.toLocaleString("en-IN")} / sqft`
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
          ₹{project.pricePerSqft.toLocaleString("en-IN")} / sqft
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
    evidence is available. Government Guidance is reported separately as regulatory 
    reference information and is not used to determine Fair Value.

    <br /><br />

    Market asking prices reflect current
    seller expectations and may differ
    from intrinsic value.

  </div>

</div>

<div className="findings-card">

  <div className="findings-title">
    HOW PROPERTYIQ WORKS
  </div>

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

</div>

      <div className="findings-card">

        <div className="findings-title">
          KEY FINDINGS
        </div>

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

      </div>


      <StudioPromoCard onLaunch={onLaunchStudio} />

      <FraudIntelligenceStatic />

    </div>
  );
}

export default AssessmentResult;