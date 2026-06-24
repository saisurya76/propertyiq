function AssessmentResult({
  result,
  formData
}) {
  if (!result) return null;

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
    try {

      const response = await fetch(
        "http://127.0.0.1:8000/generate-report",
        {
          method: "POST",

          headers: {
            "Content-Type": "application/json"
          },

          body: JSON.stringify({
            country: formData.country,
            city: formData.city,

            propertyName:
              formData.propertyName,

            developerName:
              formData.developerName,

            quotedPrice:
              Number(formData.quotedPrice),

            unitArea:
              Number(formData.areaValue),

            areaUnit:
              formData.areaUnit,

            monthlyRent:
              Number(formData.monthlyRent || 0),

            totalUnits:
              Number(formData.totalUnits || 100),

            unsoldUnits:
              Number(formData.unsoldUnits || 20),

            projectsCompleted:
              Number(formData.projectsCompleted || 10),

            projectsDelayed:
              Number(formData.projectsDelayed || 1),

            yearsInBusiness:
              Number(formData.yearsInBusiness || 15),

            regulatoryViolations:
              Number(formData.regulatoryViolations || 0)
          })
        }
      );

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

      alert(
        "Failed to download report"
      );
    }
  };

  return (
    <div className="card result-card">

      <div className="score-section">

        <div className="score">
          {result.score}
        </div>

        <div className="score-label">
          Buyer Protection Score
        </div>

        <div className="rating-pill">
          {result.rating}
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
            {result.developerRating}
          </p>
        </div>

        <div className="metric-card">
          <h4>Inventory Risk</h4>
          <p>
            {result.inventoryRisk}
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
    MARKET INTELLIGENCE
  </div>

  <div className="finding-item">

    <strong>
      Market Average Price
    </strong>

    <p>
      ₹{result.marketAveragePricePerSqft?.toLocaleString("en-IN")} / sqft
    </p>

  </div>

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
      Valuation Analysis — 50%
      <br />
      Inventory Risk — 30%
      <br />
      Developer Quality — 20%
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
      Valuation Model
    </strong>

    <p>
      Comparable Sales
      <br />
      Rental Yield
      <br />
      Replacement Cost
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
        >
          Download PropertyIQ Report
        </button>

      </div>

    </div>
  );
}

export default AssessmentResult;