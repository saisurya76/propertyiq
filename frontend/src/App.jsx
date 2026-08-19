import { useEffect, useState } from "react";
import "./App.css";
import "./studio/studio.css";

import PropertyForm from "./components/PropertyForm";
import AssessmentResult from "./components/AssessmentResult";
import Disclaimer from "./components/Disclaimer";
import StudioAuth from "./studio/StudioAuth";
import StudioPricing from "./studio/StudioPricing";
import ConstructionStudio from "./studio/ConstructionStudio";
import StudioDesigns from "./studio/StudioDesigns";
import ScrollToTopBottom from "./components/ScrollToTopBottom";
import AdminPanel from "./studio/AdminPanel";
import SessionBar from "./studio/SessionBar";
import StudioTopBar from "./studio/StudioTopBar";
import { getSession, clearSession, studioApi } from "./studio/studioApi";


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

function normalizeLanguage(code) {
  if (!code) return "en";
  const lower = code.toLowerCase();
  if (lower === "zh-cn" || lower === "zh-sg") return "zh-CN";
  if (lower === "zh-tw" || lower === "zh-hk") return "zh-TW";
  const base = lower.split("-")[0];
  return LANGUAGE_OPTIONS.some(([value]) => value.toLowerCase() === base) ? base : "en";
}

function App() {
  const [formData, setFormData] = useState({
    country: "India",
    stateProvince: "Telangana",
    city: "Hyderabad",
    location: "",
    governmentGuidance: "",
    marketAverage: "",
    propertyType: "Apartment",

    propertyName: "",
    developerName: "",

    quotedPrice: "",

    areaValue: "",
    areaUnit: "sqft",

    monthlyRent: "",

    totalUnits: "",
    unsoldUnits: "",

    projectsCompleted: "",
    projectsDelayed: "",
    yearsInBusiness: "",
    regulatoryViolations: "",

    additionalInformation: ""
  });

  const [result, setResult] = useState(null);
  const [reportId, setReportId] = useState(null);
  const [studioView, setStudioView] = useState(() => {
    // Real URL access: hitting /admin directly loads straight into the
    // admin view (paired with vercel.json's SPA rewrite so this doesn't 404).
    if (typeof window !== "undefined" && window.location.pathname === "/admin") {
      return "admin";
    }
    return "main";
  }); // "main" | "auth" | "pricing" | "construction" | "admin"
  const [loading, setLoading] = useState(false);
  const [language, setLanguage] = useState("en");
  const [languageReady, setLanguageReady] = useState(false);
  const [currency, setCurrency] = useState("USD");

  // Keep the URL bar in sync with the admin view, and support the browser
  // back/forward buttons.
  useEffect(() => {
    const targetPath = studioView === "admin" ? "/admin" : "/";
    if (window.location.pathname !== targetPath) {
      window.history.pushState({}, "", targetPath);
    }
  }, [studioView]);

  useEffect(() => {
    const onPopState = () => {
      setStudioView(window.location.pathname === "/admin" ? "admin" : "main");
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  useEffect(() => {
    // Admin dashboard stays English-only — no auto-detection, no Google
    // Translate widget triggering, regardless of visitor IP/browser locale.
    // (languageReady/language React state is irrelevant here since the
    // admin view never renders the language selector.)
    if (window.location.pathname === "/admin") {
      document.documentElement.lang = "en";
      return;
    }

    let cancelled = false;

    const applyLanguage = (code) => {
      if (cancelled) return;
      const normalized = normalizeLanguage(code);
      setLanguage(normalized);
      document.documentElement.lang = normalized;
      setLanguageReady(true);

      if (normalized !== "en") {
        const applyGoogleTranslation = () => {
          const select = document.querySelector(".goog-te-combo");
          if (!select) return false;
          select.value = normalized;
          select.dispatchEvent(new Event("change"));
          return true;
        };
        if (!applyGoogleTranslation()) {
          window.setTimeout(applyGoogleTranslation, 500);
          window.setTimeout(applyGoogleTranslation, 1500);
        }
      }
    };

    const detect = async () => {
      try {
        const response = await fetch("https://ipapi.co/json/", { cache: "no-store" });
        if (response.ok) {
          const data = await response.json();
          if (data.currency && !cancelled) setCurrency(data.currency);
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

  const changeLanguage = (event) => {
    const selected = event.target.value;
    setLanguage(selected);
    document.documentElement.lang = selected;

    const applyGoogleTranslation = () => {
      const select = document.querySelector(".goog-te-combo");
      if (!select) return;
      select.value = selected;
      select.dispatchEvent(new Event("change"));
    };
    applyGoogleTranslation();
    window.setTimeout(applyGoogleTranslation, 300);
  };


  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const buildRequestPayload = () => ({
    country: formData.country,
    stateProvince: formData.stateProvince || "",

    city: formData.city,
    location: formData.location,
    governmentGuidance:
      formData.governmentGuidance === ""
        ? null
        : Number(formData.governmentGuidance),

    marketAverage:
      formData.marketAverage === ""
        ? null
        : Number(formData.marketAverage),

    propertyName: formData.propertyName,
    propertyType: formData.propertyType,
    
    developerName: formData.developerName,

    quotedPrice: Number(formData.quotedPrice),

    unitArea: Number(formData.areaValue),

    areaUnit: formData.areaUnit,

    monthlyRent: Number(formData.monthlyRent || 0),

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
    
  });

  const generateAssessment = async () => {
    if (loading) return;
    if (
      !formData.country ||
      !formData.stateProvince ||
      !formData.city ||
      !formData.location ||

      !formData.propertyType ||

      !formData.propertyName ||
      !formData.developerName ||

      !formData.quotedPrice ||

      !formData.areaValue ||

      !formData.governmentGuidance ||

      !formData.marketAverage
    ) {
      alert("Please complete all mandatory valuation fields.");
      return;
    }

    try {
      setLoading(true);
      const response = await fetch(
        "https://propertyiq-api-q21y.onrender.com/assess",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify(
              buildRequestPayload()
          )
        }
      );

      if (!response.ok) {
          throw new Error("Assessment failed.");
      }

      const data = await response.json();

      setResult(data);
      setReportId(
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `report_${Date.now()}_${Math.random().toString(36).slice(2)}`
      );

    } catch (error) {

      console.error(error);

      alert(
        "Failed to connect to PropertyIQ API"
      );
    }
    finally{
        setLoading(false);
    }
  };

  const [quotaMessage, setQuotaMessage] = useState("");
  const [resumePropertyId, setResumePropertyId] = useState(null);
  const [checkingSession, setCheckingSession] = useState(false);

  const launchStudio = async () => {
    const session = getSession();
    if (!session) {
      setStudioView("auth");
      return;
    }

    // The cached session might be stale (e.g. from before a backend data
    // reset) — validate it before trusting it, instead of showing a false
    // "signed in" state that only fails later on some other action.
    setCheckingSession(true);
    try {
      await studioApi.getStatus();
      // If the user was actively editing a specific saved design when they
      // left (resumePropertyId still set — only true after explicitly
      // opening a saved design, never for "start new"), take them straight
      // back to it instead of routing through Pricing -> Designs -> click
      // the same design again. That multi-click detour was the actual
      // "no seamless experience" bug — the design was always reachable via
      // the saved-designs list, just never in one click.
      setStudioView(resumePropertyId ? "construction" : "pricing");
    } catch (err) {
      if (err.status === 401) {
        clearSession();
        setStudioView("auth");
      } else {
        setStudioView("pricing"); // some other error — let the pricing page surface it
      }
    } finally {
      setCheckingSession(false);
    }
  };

  const handleStudioAuthenticated = () => {
    setStudioView("pricing");
  };

  const backToReport = () => {
    setStudioView("main");
  };

  const launchConstructionStudio = () => {
    setQuotaMessage("");
    setStudioView("designs");
  };

  const handleQuotaExceeded = (message) => {
    setQuotaMessage(message);
    setStudioView("pricing");
  };

  const handleSignOut = (targetView = "auth") => {
    clearSession();
    setStudioView(targetView);
  };

  if (checkingSession) {
    return (
      <div className="app">
        <div className="studio-panel">
          <p className="studio-subtext">Checking your session...</p>
        </div>
        <ScrollToTopBottom />
      </div>
    );
  }

  if (studioView === "auth") {
    return (
      <div className="app">
        <StudioAuth onAuthenticated={handleStudioAuthenticated} onBack={backToReport} />
        <ScrollToTopBottom />
      </div>
    );
  }

  if (studioView === "pricing") {
    return (
      <div className="app">
        <StudioTopBar onBackToReport={backToReport} onSignOut={() => handleSignOut("main")} />
        {quotaMessage && (
          <div
            className="studio-status-banner"
            style={{ background: "#fef2f2", borderColor: "#fecaca", color: "#991b1b", maxWidth: 1100, margin: "0 auto 20px" }}
          >
            {quotaMessage}
          </div>
        )}
        <StudioPricing reportId={reportId} currency={currency} onBack={backToReport} onLaunchConstructionStudio={launchConstructionStudio} onSignOut={handleSignOut} />
        <ScrollToTopBottom />
      </div>
    );
  }

  if (studioView === "designs") {
    return (
      <div className="app">
        <StudioTopBar onBackToReport={backToReport} onSignOut={() => handleSignOut("main")} />
        <StudioDesigns
          onStartNew={() => {
            setResumePropertyId(null);
            setStudioView("construction");
          }}
          onResume={(propertyId) => {
            setResumePropertyId(propertyId);
            setStudioView("construction");
          }}
        />
        <ScrollToTopBottom />
      </div>
    );
  }

  if (studioView === "construction") {
    return (
      <div className="app">
        <StudioTopBar onBackToReport={backToReport} onSignOut={() => handleSignOut("main")} />
        <ConstructionStudio
          onBack={() => setStudioView("designs")}
          onQuotaExceeded={handleQuotaExceeded}
          resumePropertyId={resumePropertyId}
        />
        <ScrollToTopBottom />
      </div>
    );
  }

  if (studioView === "admin") {
    return (
      <div className="app">
        <StudioTopBar onBackToReport={backToReport} onSignOut={() => handleSignOut("main")} />
        <AdminPanel onBack={backToReport} />
        <ScrollToTopBottom />
      </div>
    );
  }

  return (
    <div className="app">

      <SessionBar onSignOut={() => handleSignOut("main")} />

      <div className="language-bar" aria-label="Language selection">
        <label htmlFor="propertyiq-language">Language</label>
        <select
          id="propertyiq-language"
          value={language}
          onChange={changeLanguage}
          disabled={!languageReady}
        >
          {LANGUAGE_OPTIONS.map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </div>

      <div className="hero hero-banner">

       <div className="hero-brand-row">

        <div className="hero-brand">
          PROPERTYIQ
        </div>

        <span className="beta-badge">
          BETA
        </span>

      </div>

      <div className="hero-subtitle">
        Independent Property Intelligence
      </div>

      <h1>
        Know Before You Buy.
      </h1>

      <p>
        Make informed property decisions using
        independent, explainable and evidence-based intelligence.
      </p>

      <div className="hero-studio-cta">
        <div className="hero-studio-cta-text">
          <span className="hero-studio-cta-badge">Construction Studio</span>
          <p>Design your build, place rooms on a real floor plan, get live cost estimates, and export a DXF — no property report needed.</p>
        </div>
        <button type="button" className="hero-studio-cta-btn" onClick={launchStudio}>
          Open Construction Studio →
        </button>
      </div>

      </div>

      <div className="mission-section">
        <div className="mission-content">
          <h2>Why PropertyIQ exists</h2>
          <p>
            Real estate in India runs on trust that's rarely earned. Builders routinely inflate carpet
            area against sanctioned plans, quote per-square-foot rates with no defensible basis, and bury
            change-of-plan or cost-escalation clauses deep in agreements few buyers ever read closely.
            Pricing itself is often little more than "what the market will bear" — copied from a
            neighboring project, adjusted for a broker's commission, with no grounding in actual
            construction cost, land value, or comparable sales data.
          </p>
          <p>
            The common loopholes are well known inside the industry and almost invisible outside it:
            RERA registration numbers that don't match the actual project, occupancy certificates
            obtained for a different building configuration than what's delivered, and "super built-up
            area" quoted with a loading factor that can run anywhere from 20% to 40%+ over actual carpet
            area with no consistent standard — meaning two builders can describe the exact same living
            space with very different-sounding square footage. A buyer evaluating a single property has
            no independent way to catch any of this before money changes hands.
          </p>
          <p>
            PropertyIQ exists to close that information gap. Every assessment cross-references public
            government records, fraud-pattern databases, and comparable transaction data — the same kind
            of scrutiny a careful lawyer or engineer would apply, made accessible before you commit, not
            after a dispute. Construction Studio goes a step further: instead of trusting a builder's
            quoted rate, it prices your build from real material and labor costs, region by region, so
            you have an independent number to compare against what you're being asked to pay.
          </p>
          <p className="mission-tagline">
            Independent. Evidence-based. Built for the buyer, not the builder.
          </p>
        </div>
      </div>

      <PropertyForm
        formData={formData}
        handleChange={handleChange}
        generateAssessment={generateAssessment}
        loading={loading}
      />

      <AssessmentResult
        result={result}
        formData={formData}
        reportId={reportId}
        onLaunchStudio={launchStudio}
      />

      <Disclaimer />

      <footer className="footer">

      <p>PropertyIQ v1.0.0 Beta</p>

      <p>Independent Property Intelligence</p>

      <p>© 2026 PropertyIQ</p>

    </footer>

    <ScrollToTopBottom />

    </div>
  );
}

export default App;