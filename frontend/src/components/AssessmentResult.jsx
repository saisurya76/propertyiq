function AssessmentResult({ result }) {
  if (!result) return null;

  const formatCurrency = (value) => {
    return new Intl.NumberFormat("en-IN").format(value);
  };

  const formatIndianCurrency = (value) => {
  if (value >= 10000000) {
    return `₹${(value / 10000000).toFixed(2)} Cr`;
  }

  if (value >= 100000) {
    return `₹${(value / 100000).toFixed(2)} L`;
  }

  return `₹${new Intl.NumberFormat("en-IN").format(value)}`;
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
          {formatIndianCurrency(result.fairValue)}
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

      <div className="recommendation-card">

        <div className="recommendation-title">
          FINAL RECOMMENDATION
        </div>

        <div className="recommendation-value">
          {result.recommendation}
        </div>

        <div className="recommendation-text">
          This recommendation is derived from
          valuation analysis, inventory risk,
          developer quality, and buyer protection scoring.
        </div>

      </div>

    </div>
  );
}

export default AssessmentResult;