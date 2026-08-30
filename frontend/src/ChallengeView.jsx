import { useEffect, useState } from "react";
import { studioApi } from "./studio/studioApi";
import "./App.css";

// Same real geolocation-based language map App.jsx's own detect()
// fallback path uses — a genuinely separate copy (not shared/imported),
// same reasoning as neighborhood-insights.html needing its own Google
// Translate script: this is a separate entry point rendered before App
// ever mounts, sharing index.html's own Google Translate widget script/
// div but not any of App.jsx's own JS. Unlike /th/neighborhood-insights,
// a shared challenge link (/challenge/{id}) carries NO country/language
// signal of its own at all — challenge_store.py stores no such field —
// so IP-based geolocation (App.jsx's own fallback for exactly this
// "no URL signal" case) is the only real option here, not a URL-derived
// shortcut.
const COUNTRY_LANGUAGE_MAP = {
  IN: "en", US: "en", GB: "en", CA: "en", AU: "en", NZ: "en", IE: "en",
  SG: "en", MY: "ms", ID: "id", TH: "th", VN: "vi", PH: "fil", JP: "ja",
  KR: "ko", CN: "zh-CN", TW: "zh-TW", HK: "zh-TW", AE: "ar", SA: "ar",
  QA: "ar", KW: "ar", BH: "ar", OM: "ar", EG: "ar", IL: "he", IR: "fa",
  TR: "tr", RU: "ru", UA: "uk", PL: "pl", CZ: "cs", SK: "sk", HU: "hu",
  RO: "ro", BG: "bg", RS: "sr", HR: "hr", SI: "sl", DE: "de", AT: "de",
  CH: "de", FR: "fr", BE: "fr", ES: "es", MX: "es", AR: "es", CL: "es",
  CO: "es", PE: "es", BR: "pt", PT: "pt", IT: "it", NL: "nl", SE: "sv",
  DK: "da", NO: "no", FI: "fi", GR: "el", ZA: "en", KE: "sw", TZ: "sw",
  ET: "am", GE: "ka", AM: "hy", AZ: "az", KZ: "kk", UZ: "uz"
};

const LANGUAGE_OPTIONS = [
  ["en", "English"], ["hi", "हिन्दी"], ["bn", "বাংলা"], ["te", "తెలుగు"],
  ["ta", "தமிழ்"], ["mr", "मराठी"], ["gu", "ગુજરાતી"], ["kn", "ಕನ್ನಡ"],
  ["ml", "മലയാളം"], ["pa", "ਪੰਜਾਬੀ"], ["ur", "اردو"], ["as", "অসমীয়া"],
  ["or", "ଓଡ଼ିଆ"], ["ne", "नेपाली"], ["si", "සිංහල"], ["th", "ไทย"],
  ["id", "Bahasa Indonesia"], ["ms", "Bahasa Melayu"], ["vi", "Tiếng Việt"],
  ["zh-CN", "简体中文"], ["zh-TW", "繁體中文"], ["ja", "日本語"], ["ko", "한국어"],
  ["ar", "العربية"], ["fa", "فارسی"], ["he", "עברית"], ["tr", "Türkçe"],
  ["ru", "Русский"], ["uk", "Українська"], ["pl", "Polski"], ["cs", "Čeština"],
  ["sk", "Slovenčina"], ["hu", "Magyar"], ["ro", "Română"], ["bg", "Български"],
  ["sr", "Српски"], ["hr", "Hrvatski"], ["sl", "Slovenščina"], ["de", "Deutsch"],
  ["fr", "Français"], ["es", "Español"], ["pt", "Português"], ["it", "Italiano"],
  ["nl", "Nederlands"], ["sv", "Svenska"], ["da", "Dansk"], ["no", "Norsk"],
  ["fi", "Suomi"], ["el", "Ελληνικά"], ["ca", "Català"], ["eu", "Euskara"],
  ["gl", "Galego"], ["af", "Afrikaans"], ["sw", "Kiswahili"], ["am", "አማርኛ"],
  ["zu", "isiZulu"], ["xh", "isiXhosa"], ["fil", "Filipino"], ["my", "မြန်မာ"],
  ["km", "ខ្មែរ"], ["lo", "ລາວ"], ["mn", "Монгол"], ["ka", "ქართული"],
  ["hy", "Հայերեն"], ["az", "Azərbaycan"], ["kk", "Қазақша"], ["uz", "O‘zbek"],
  ["sq", "Shqip"], ["bs", "Bosanski"], ["mk", "Македонски"], ["is", "Íslenska"],
  ["ga", "Gaeilge"], ["cy", "Cymraeg"], ["mt", "Malti"], ["la", "Latin"],
  ["eo", "Esperanto"]
];

function normalizeLanguage(code) {
  if (!code) return "en";
  const lower = code.toLowerCase();
  if (lower === "zh-cn" || lower === "zh-sg") return "zh-CN";
  if (lower === "zh-tw" || lower === "zh-hk") return "zh-TW";
  const base = lower.split("-")[0];
  return LANGUAGE_OPTIONS.some(([value]) => value.toLowerCase() === base) ? base : "en";
}

// Exact same real mechanism App.jsx's own triggerGoogleTranslation
// uses — drives the widget's hidden .goog-te-combo <select>
// programmatically, since Google Translate exposes no other public
// API for this. Kept identical (including the "no early-return for a
// falsy/English language" behavior) rather than a slightly different
// reimplementation.
function triggerGoogleTranslation(languageCode) {
  const apply = () => {
    const select = document.querySelector(".goog-te-combo");
    if (!select) return false;
    select.value = languageCode;
    select.dispatchEvent(new Event("change"));
    return true;
  };

  if (!apply()) {
    window.setTimeout(apply, 500);
    window.setTimeout(apply, 1500);
  }
}

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

  // The real, previously-missing fix: this page had no translation
  // logic at all. Since a shared challenge link carries no
  // country/language signal of its own (unlike /th/neighborhood-insights,
  // which has an explicit URL code), this mirrors App.jsx's own
  // geolocation-based FALLBACK path specifically — the one it uses when
  // there's no URL country context — rather than its URL-context path,
  // which doesn't apply here at all.
  useEffect(() => {
    let cancelled = false;

    const applyLanguage = (code) => {
      if (cancelled) return;
      const normalized = normalizeLanguage(code);
      document.documentElement.lang = normalized;
      triggerGoogleTranslation(normalized);
    };

    const detect = async () => {
      try {
        const response = await fetch("https://ipapi.co/json/", { cache: "no-store" });
        if (response.ok) {
          const data = await response.json();
          const mapped = COUNTRY_LANGUAGE_MAP[data.country_code];
          const geoLanguage = (data.languages || "").split(",")[0]?.trim();
          if (mapped) {
            applyLanguage(mapped);
            return;
          }
          if (geoLanguage) {
            applyLanguage(geoLanguage);
            return;
          }
        }
      } catch (error) {
        console.warn("Automatic language detection unavailable:", error);
      }
      applyLanguage(navigator.language || "en");
    };

    detect();
    return () => { cancelled = true; };
  }, []);

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
        <div className="challenge-view-card-row"><span>City</span><strong>{challenge.city}</strong></div>
        {challenge.location && (
          <div className="challenge-view-card-row"><span>Locality</span><strong>{challenge.location}</strong></div>
        )}
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
