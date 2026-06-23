function AssessmentResult({ result }) {
  if (!result) return null;

  return (
    <div className="card result-card">

      <div className="score-section">

        <div className="score">
          {result.score}
        </div>

        <div className="score-label">
          Buyer Protection Score
        </div>

      </div>

      <div className="result-grid">

        <div>
          <h4>Rating</h4>
          <p>{result.rating}</p>
        </div>

        <div>
          <h4>Fair Value</h4>
          <p>{result.fairValue}</p>
        </div>

        <div>
          <h4>Recommendation</h4>
          <p>{result.recommendation}</p>
        </div>

      </div>

    </div>
  );
}

export default AssessmentResult;