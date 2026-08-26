import { useEffect, useState } from "react";
import { studioApi } from "./studio/studioApi";
import "./App.css";

// The recipient's side of "Should I Buy This?" — a completely standalone
// page (not part of the main app's navigation), reached at
// /challenge/{id}. No account needed to view the property card or make
// the initial guess, matching the feature's own explicit design. Routed
// here directly from main.jsx, before the main App component's own
// routing/URL-sync logic even initializes, since that logic actively
// rewrites the URL back to "/" for anything it doesn't recognize as one
// of its own views.
function ChallengeView({ challengeId }) {
  const [challenge, setChallenge] = useState(null);
  const [loadState, setLoadState] = useState("loading"); // "loading" | "loaded" | "not_found" | "error"
  const [guessInput, setGuessInput] = useState("");
  const [reveal, setReveal] = useState(null);
  const [guessState, setGuessState] = useState("idle"); // "idle" | "loading" | "done" | "error"
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    studioApi.getChallenge(challengeId)
      .then((data) => {
        setChallenge(data);
        setLoadState("loaded");
      })
      .catch((err) => {
        setLoadState(err.status === 404 ? "not_found" : "error");
      });
  }, [challengeId]);

  const handleGuess = async () => {
    if (!guessInput) return;
    setGuessState("loading");
    setErrorMessage("");
    try {
      const data = await studioApi.guessChallenge(challengeId, Number(guessInput));
      setReveal(data);
      setGuessState("done");
    } catch (err) {
      setErrorMessage(err.message || "Couldn't check your guess right now.");
      setGuessState("error");
    }
  };

  if (loadState === "loading") {
    return <div className="challenge-view-wrap"><p className="challenge-view-status">Loading challenge...</p></div>;
  }

  if (loadState === "not_found") {
    return (
      <div className="challenge-view-wrap">
        <p className="challenge-view-status">This challenge doesn't exist or may have expired.</p>
        <a href="/" className="challenge-view-home-link">Go to PropertyIQ</a>
      </div>
    );
  }

  if (loadState === "error") {
    return (
      <div className="challenge-view-wrap">
        <p className="challenge-view-status">Couldn't load this challenge right now — please try again.</p>
      </div>
    );
  }

  return (
    <div className="challenge-view-wrap">
      <div className="challenge-view-header">
        <h1>🏠 Should I Buy This?</h1>
        <p>Someone's challenging you to guess this property's real value.</p>
      </div>

      <div className="challenge-view-property-card">
        <div className="challenge-view-card-row"><span>Price</span><strong>{challenge.price.toLocaleString()}</strong></div>
        <div className="challenge-view-card-row"><span>Location</span><strong>{challenge.city}</strong></div>
        <div className="challenge-view-card-row"><span>Type</span><strong>{challenge.property_type}</strong></div>
        <div className="challenge-view-card-row"><span>Area</span><strong>{challenge.area_value} {challenge.area_unit}</strong></div>
      </div>

      {guessState !== "done" && (
        <div className="challenge-view-guess-section">
          <p className="challenge-view-question">What would YOU pay for this property?</p>
          <div className="challenge-view-guess-row">
            <input
              type="number"
              min="0"
              value={guessInput}
              onChange={(e) => setGuessInput(e.target.value)}
              placeholder="Your estimate"
            />
            <button type="button" className="challenge-view-guess-btn" onClick={handleGuess} disabled={guessState === "loading" || !guessInput}>
              {guessState === "loading" ? "Checking..." : "See how close you are"}
            </button>
          </div>
          {guessState === "error" && <p className="challenge-view-error">{errorMessage}</p>}
        </div>
      )}

      {guessState === "done" && reveal && (
        <div className="challenge-view-reveal">
          {reveal.coverage === "unsupported" ? (
            <p className="challenge-view-unsupported">{reveal.reason}</p>
          ) : (
            <>
              <div className="challenge-view-reveal-row">
                <span>Your guess</span>
                <strong>{reveal.guessed_price.toLocaleString()}</strong>
              </div>
              <div className="challenge-view-reveal-row">
                <span>PropertyIQ Fair Value</span>
                <strong>{reveal.fair_value.toLocaleString()}</strong>
              </div>
              <div className="challenge-view-reveal-row">
                <span>Market Position</span>
                <strong>{reveal.market_position} ({reveal.score}/100)</strong>
              </div>
              <div className="challenge-view-reveal-row">
                <span>Your guess vs. Fair Value</span>
                <strong>{reveal.guess_diff_percent > 0 ? "+" : ""}{reveal.guess_diff_percent}%</strong>
              </div>

              <p className="challenge-view-findings-heading">Key risks & findings:</p>
              {reveal.findings.map((finding, i) => (
                <div key={i} className="challenge-view-finding">
                  <div className="challenge-view-finding-title">{finding.icon} {finding.title}</div>
                  <p className="challenge-view-finding-detail">{finding.detail}</p>
                </div>
              ))}
            </>
          )}

          <p className="challenge-view-cta">
            Want the full picture on any property? Run a complete PropertyIQ assessment.
          </p>
          <a href="/" className="challenge-view-home-link">Try PropertyIQ</a>
        </div>
      )}
    </div>
  );
}

export default ChallengeView;
