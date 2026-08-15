import { useState } from "react";
import { studioApi, saveSession } from "./studioApi";

function StudioAuth({ onAuthenticated, onBack }) {
  const [step, setStep] = useState("email"); // "email" | "code"
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submitEmail = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setError("");
    setLoading(true);
    try {
      await studioApi.requestOtp(email.trim());
      setStep("code");
    } catch (err) {
      setError(err.message || "Couldn't send the code. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const submitCode = async (e) => {
    e.preventDefault();
    if (!code.trim()) return;
    setError("");
    setLoading(true);
    try {
      const result = await studioApi.verifyOtp(email.trim(), code.trim());
      saveSession(result.session_token, email.trim());
      onAuthenticated(email.trim());
    } catch (err) {
      setError(err.message || "That code didn't work. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  if (step === "email") {
    return (
      <div className="studio-panel">
        <h2>Sign in to PropertyIQ Studio</h2>
        <p className="studio-subtext">
          We'll email you a 6-digit code — no password needed.
        </p>
        <form onSubmit={submitEmail}>
          {error && <div className="studio-error">{error}</div>}
          <input
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoFocus
            required
          />
          <button className="studio-cta-btn" type="submit" disabled={loading} style={{ width: "100%" }}>
            {loading ? "Sending..." : "Send code"}
          </button>
        </form>
        <span className="studio-back-link" onClick={onBack}>← Back to report</span>
      </div>
    );
  }

  return (
    <div className="studio-panel">
      <h2>Enter your code</h2>
      <p className="studio-subtext">
        We sent a 6-digit code to <strong>{email}</strong>. It expires in 10 minutes.
      </p>
      <form onSubmit={submitCode}>
        {error && <div className="studio-error">{error}</div>}
        <input
          type="text"
          inputMode="numeric"
          placeholder="123456"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          autoFocus
          required
        />
        <button className="studio-cta-btn" type="submit" disabled={loading} style={{ width: "100%" }}>
          {loading ? "Verifying..." : "Verify & continue"}
        </button>
      </form>
      <span className="studio-back-link" onClick={() => setStep("email")}>← Use a different email</span>
      {" · "}
      <span className="studio-back-link" onClick={onBack}>← Back to report</span>
    </div>
  );
}

export default StudioAuth;
