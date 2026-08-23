import { useEffect, useMemo, useState } from "react";
import "./App.css";
import "./studio/studio.css";

import PropertyForm from "./components/PropertyForm";
import CollapsiblePanel from "./components/CollapsiblePanel";
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

// URL-based country context: visiting /th loads the whole app pre-set
// for Thailand — the main property form defaults to Thailand/THB, and
// starting a NEW Construction Studio design (not resuming an existing
// one, which keeps its own saved country) is pre-seeded with Thailand's
// region/currency/unit system. Deliberately a small, extensible map —
// more country codes (/in, /us, etc, per the stated plan) get added
// here later without restructuring anything.
// Each entry: currency/unit_system/region are always set — every
// country gets a real, working experience with these. `language` is
// deliberately a SEPARATE decision per country, not an automatic
// consequence of visiting /<code> — checked against real research for
// each one rather than assumed:
//   - Thailand: Thai is overwhelmingly dominant, forcing it is correct.
//   - Vietnam: Vietnamese is the unambiguous dominant language across
//     government/education/media/business — forcing it is correct.
//   - Indonesia: same — Bahasa Indonesia is the clear national language.
//   - Philippines: genuinely different. English is CO-OFFICIAL, not a
//     second-class fallback — used throughout government, law,
//     business, and education, with ~90%+ comprehension nationally.
//     Forcing Filipino here would be a wrong default for exactly the
//     reason English exists as a first-class option: `language` is
//     left unset, so the page's normal language handling (IP-based
//     detection, manual selector) applies rather than being overridden.
//
// `region` (materials-catalog scoping) is ALSO a deliberately separate
// decision from country: each supported country now has real researched
// material brands/pricing (cement/steel/sand/aggregate/bricks) tied to
// its own dedicated region, rather than falling back to the generic
// "global" catalog. Country-level behavior (currency, unit system, form
// defaults, and — on the backend — which traditional-building validation
// engine applies, if any real one exists for that country) is fully
// wired alongside it.
const COUNTRY_CODE_MAP = {
  th: { name: "Thailand", currency: "THB", stateProvince: "", city: "", language: "th", region: "thailand", unit_system: "metric" },
  ph: { name: "Philippines", currency: "PHP", stateProvince: "", city: "", region: "philippines", unit_system: "metric" },
  vn: { name: "Vietnam", currency: "VND", stateProvince: "", city: "", language: "vi", region: "vietnam", unit_system: "metric" },
  id: { name: "Indonesia", currency: "IDR", stateProvince: "", city: "", language: "id", region: "indonesia", unit_system: "metric" },
};

// Read once at initial load (a useState lazy initializer calls this
// exactly once, before any view-switching effects run) — the country
// code is a startup context, not something that needs to keep
// rewriting the URL as the user navigates between views afterward.
function detectCountryCodeFromUrl() {
  if (typeof window === "undefined") return null;
  const match = window.location.pathname.match(/^\/([a-z]{2})\/?$/i);
  if (!match) return null;
  const code = match[1].toLowerCase();
  return COUNTRY_CODE_MAP[code] ? { code, ...COUNTRY_CODE_MAP[code] } : null;
}

// Drives Google Translate's hidden injected <select class="goog-te-combo">
// directly (setting its value + dispatching "change" is how that widget's
// own API expects to be driven programmatically). Module-level, not a
// component method, since it needs no component state — just the target
// language code — which is what let it live in two separate, drifting
// copies before (one inline inside the auto-detect effect, one inside
// the manual language-selector handler). Retries after a short delay
// since the widget's <select> isn't guaranteed to exist in the DOM yet
// the moment this runs (it's injected asynchronously by Google's script).
function triggerGoogleTranslation(languageCode) {
  // No early-return for "en" here — that was the actual bug: switching
  // BACK to English after the page had already been translated needs
  // Google Translate's widget to be told explicitly to revert. Google
  // Translate doesn't undo itself just because no new (non-English)
  // language was requested — it only reverts when its own <select> is
  // driven to "en" and a real "change" event fires, same as any other
  // language switch. Skipping that call for "en" left the page stuck on
  // whatever language it was last translated to.
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

function App() {
  // Memoized (not just a plain const) since it's referenced inside a
  // useEffect dependency array below — without memoizing, a fresh object
  // literal on every render would make that effect re-fire every render
  // instead of the intended once-per-language-change, even though the
  // underlying URL/pathname never actually changes during a session.
  const urlCountryContext = useMemo(() => detectCountryCodeFromUrl(), []);

  const [formData, setFormData] = useState({
    country: urlCountryContext ? urlCountryContext.name : "India",
    stateProvince: urlCountryContext ? urlCountryContext.stateProvince : "Telangana",
    city: urlCountryContext ? urlCountryContext.city : "Hyderabad",
    location: "",
    governmentGuidance: "",
    marketAverage: "",
    propertyType: "Apartment",

    propertyName: "",
    developerName: "",

    quotedPrice: "",

    areaValue: "",
    areaUnit: urlCountryContext?.unit_system === "metric" ? "sq meter" : "sqft",

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
  // "/" (no specific country code) is the main site and defaults to
  // India in every aspect, not a generic global default — currency
  // included. IP-based geolocation can still adjust this afterward for
  // the general "/" visitor (a separate, already-established mechanism,
  // unlike /th etc which deliberately skip geo-detection entirely since
  // visiting a specific country code is itself an explicit signal) —
  // this only fixes the STARTING value before that runs.
  const [currency, setCurrency] = useState(urlCountryContext ? urlCountryContext.currency : "INR");

  // Keep the URL bar in sync with the admin view, and support the browser
  // back/forward buttons. A real reported bug: this previously always
  // computed "/" as the target for any non-admin view, which rewrote
  // /th back to / the instant the app mounted (studioView starts as
  // "main"), silently stripping the country code from the address bar
  // and losing it entirely if the page was then reloaded. Now preserves
  // an active URL country context (e.g. /th) as the legitimate URL for
  // the main view, instead of unconditionally forcing "/".
  useEffect(() => {
    const mainPath = urlCountryContext ? `/${urlCountryContext.code}` : "/";
    const targetPath = studioView === "admin" ? "/admin" : mainPath;
    if (window.location.pathname !== targetPath) {
      window.history.pushState({}, "", targetPath);
    }
  }, [studioView, urlCountryContext]);

  useEffect(() => {
    const onPopState = () => {
      setStudioView(window.location.pathname === "/admin" ? "admin" : "main");
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  // Google Translate's own mutation observer doesn't reliably catch the
  // large, SPA-style full-view DOM swaps this app does when navigating
  // between Studio pages (auth -> pricing -> designs -> construction,
  // etc) — a real reported bug where the selected language only applied
  // to whichever view was on screen at the moment it was picked, and
  // silently reverted to English (or just didn't translate at all) on
  // every subsequent navigation. Re-triggering translation explicitly
  // whenever the view changes closes that gap.
  useEffect(() => {
    if (language !== "en" && window.location.pathname !== "/admin") {
      triggerGoogleTranslation(language);
    }
  }, [studioView, language]);

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
      triggerGoogleTranslation(normalized);
    };

    const detect = async () => {
      // A URL country context (visiting /th) is an explicit, deliberate
      // signal — the whole point of visiting /th is to see the page in
      // Thai, not just get Thailand's region/currency defaults with an
      // English page around them. This should win outright, skipping
      // IP-geolocation entirely, rather than just being one more input
      // that geo-detection could still override.
      if (urlCountryContext?.language) {
        applyLanguage(urlCountryContext.language);
        return;
      }

      try {
        const response = await fetch("https://ipapi.co/json/", { cache: "no-store" });
        if (response.ok) {
          const data = await response.json();
          // A URL country context (visiting /th) is an explicit, deliberate
          // signal — it should win over IP-based geolocation, not get
          // silently overridden by wherever the visitor actually is.
          if (data.currency && !cancelled && !urlCountryContext) setCurrency(data.currency);
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
  }, [urlCountryContext]);

  // Handles the redirect back from Dodo's hosted checkout for the
  // one-time report-unlock payment — a real, confirmed gap this closes:
  // there was no code at all handling ?payment=return before, so a user
  // could pay and be redirected back to a page that gave no
  // acknowledgment the payment happened at all. Polls the order-status
  // endpoint a few times since the webhook that actually marks the
  // order paid can take a moment to arrive after the redirect completes
  // — genuinely still "processing" for a few seconds is a normal,
  // expected state here, not a failure.
  const [paymentReturnMessage, setPaymentReturnMessage] = useState(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const paymentParam = params.get("payment");
    const orderId = params.get("order_id");
    if (!paymentParam || !orderId) return;

    // Clean the query params from the URL immediately so a page reload
    // doesn't re-trigger this same check against an already-resolved order.
    const cleanUrl = window.location.pathname;
    window.history.replaceState({}, "", cleanUrl);

    if (paymentParam === "cancelled") {
      setTimeout(() => setPaymentReturnMessage({ tone: "neutral", text: "Payment was cancelled — no charge was made." }), 0);
      return;
    }
    if (paymentParam !== "return") return;

    let cancelled = false;
    const pollOrderStatus = async (attemptsLeft) => {
      if (cancelled) return;
      try {
        const result = await studioApi.getOrderStatus(orderId);
        if (cancelled) return;
        if (result.status === "paid") {
          setPaymentReturnMessage({ tone: "success", text: "Payment successful! Your report is unlocked." });
          return;
        }
        if (result.status === "payment_failed") {
          setPaymentReturnMessage({ tone: "error", text: "The payment didn't go through. Please try again." });
          return;
        }
      } catch (error) {
        console.warn("Couldn't check payment order status:", error);
      }
      if (attemptsLeft > 0) {
        setTimeout(() => pollOrderStatus(attemptsLeft - 1), 1500);
      } else {
        setPaymentReturnMessage({
          tone: "neutral",
          text: "Still confirming your payment — this can take a few extra seconds. Refresh in a moment if this doesn't update.",
        });
      }
    };

    setTimeout(() => setPaymentReturnMessage({ tone: "neutral", text: "Confirming your payment..." }), 0);
    pollOrderStatus(5);

    return () => { cancelled = true; };
  }, []);

  // Same gap, same fix, for the subscription and Insight Add-on
  // checkout flows — both previously redirected to a path this SPA has
  // no route for at all (/studio and /report/{id}), with zero frontend
  // code reading either return query param, so a real, successful
  // payment for either one gave the user no acknowledgment whatsoever.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);

    if (params.get("subscribed") === "1") {
      window.history.replaceState({}, "", window.location.pathname);
      let cancelled = false;
      const pollSubscription = async (attemptsLeft) => {
        if (cancelled) return;
        try {
          const result = await studioApi.getStatus();
          if (cancelled) return;
          if (result.tier_id) {
            setPaymentReturnMessage({ tone: "success", text: `Subscribed! Your ${result.tier_id.replace(/_/g, " ")} plan is now active.` });
            return;
          }
        } catch (error) {
          console.warn("Couldn't check subscription status:", error);
        }
        if (attemptsLeft > 0) {
          setTimeout(() => pollSubscription(attemptsLeft - 1), 1500);
        } else {
          setPaymentReturnMessage({
            tone: "neutral",
            text: "Still confirming your subscription — this can take a few extra seconds. Refresh in a moment if this doesn't update.",
          });
        }
      };
      setTimeout(() => setPaymentReturnMessage({ tone: "neutral", text: "Confirming your subscription..." }), 0);
      pollSubscription(5);
      return () => { cancelled = true; };
    }

    if (params.get("insight") === "1") {
      const reportId = params.get("report_id");
      window.history.replaceState({}, "", window.location.pathname);
      if (!reportId) return;
      let cancelled = false;
      const pollInsight = async (attemptsLeft) => {
        if (cancelled) return;
        try {
          const result = await studioApi.getInsightStatus(reportId);
          if (cancelled) return;
          if (result.unlocked) {
            // A known, honest limitation, not fully solved here: the
            // original computed report lived only in React state and
            // doesn't survive the full page reload checkout requires,
            // so there's no way to redisplay it automatically —
            // re-submitting the same property form will show it again,
            // now correctly unlocked.
            setPaymentReturnMessage({
              tone: "success",
              text: "Payment successful! Similar-property insights are unlocked — re-run your property assessment to see them.",
            });
            return;
          }
        } catch (error) {
          console.warn("Couldn't check insight status:", error);
        }
        if (attemptsLeft > 0) {
          setTimeout(() => pollInsight(attemptsLeft - 1), 1500);
        } else {
          setPaymentReturnMessage({
            tone: "neutral",
            text: "Still confirming your payment — this can take a few extra seconds.",
          });
        }
      };
      setTimeout(() => setPaymentReturnMessage({ tone: "neutral", text: "Confirming your payment..." }), 0);
      pollInsight(5);
      return () => { cancelled = true; };
    }
  }, []);

  const changeLanguage = (event) => {
    const selected = event.target.value;
    setLanguage(selected);
    document.documentElement.lang = selected;
    triggerGoogleTranslation(selected);
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
  // Bumped every time "start a new design" is triggered — used as
  // ConstructionStudio's React key below so a fresh instance is always
  // mounted with clean default state, even for two consecutive
  // "start new" clicks in a row (resumePropertyId alone would stay null
  // both times, which React's key comparison would treat as "no change,
  // don't remount" — the nonce guarantees a real remount every time).
  const [studioResetNonce, setStudioResetNonce] = useState(0);
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
          urlCountryContext={urlCountryContext}
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
          key={studioResetNonce}
          onBack={() => setStudioView("designs")}
          onQuotaExceeded={handleQuotaExceeded}
          resumePropertyId={resumePropertyId}
          urlCountryContext={urlCountryContext}
          onStartNew={() => {
            setResumePropertyId(null);
            setStudioResetNonce((n) => n + 1);
          }}
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

  // Deliberately separate from the language dropdown above (per an
  // explicit earlier clarification: switching site/country is NOT the
  // same axis as picking a display language) — this is the one and
  // only place a user can move between country sites (/th, /vn, etc)
  // WITHIN the app itself. Switching requires a real page reload
  // (window.location.href, not client-side state) so the whole app
  // restarts cleanly with the new country's currency/region/unit-system
  // — the same safe, full-reset mechanism that already protects
  // existing saved designs from being mislabeled by whatever site the
  // browser happens to be on (see the ConstructionStudio hydration fix).
  const SITE_OPTIONS = [
    ["", "Global (no specific country)"],
    ...Object.entries(COUNTRY_CODE_MAP).map(([code, info]) => [code, info.name]),
  ];

  const switchSite = (event) => {
    const newCode = event.target.value;
    const currentCode = urlCountryContext?.code || "";
    if (newCode === currentCode) return;

    const currentInfo = urlCountryContext || { name: "Global (no specific country)", currency: "USD (or your detected local currency)", region: "the general catalog", unit_system: "imperial (feet/sqft)" };
    const newInfo = newCode ? COUNTRY_CODE_MAP[newCode] : { name: "Global (no specific country)", currency: "USD (or your detected local currency)", region: "the general catalog", unit_system: "imperial (feet/sqft)" };

    const changes = [
      `• Currency: ${currentInfo.currency} → ${newInfo.currency}`,
      `• Materials & pricing catalog: ${currentInfo.region === "global" || !currentInfo.region ? "the general catalog" : currentInfo.name} → ${newInfo.region === "global" || !newInfo.region ? "the general catalog" : newInfo.name}`,
      `• Measurement units: ${currentInfo.unit_system === "metric" ? "meters/sqm" : "feet/sqft"} → ${newInfo.unit_system === "metric" ? "meters/sqm" : "feet/sqft"}`,
    ];
    if (newInfo.language) {
      changes.push(`• Page language will switch to ${LANGUAGE_OPTIONS.find(([v]) => v === newInfo.language)?.[1] || newInfo.language}`);
    } else if (currentInfo.language) {
      changes.push(`• Page language will no longer be forced — normal detection applies`);
    }

    const message =
      `Switching to ${newInfo.name} will change:\n\n${changes.join("\n")}\n\n` +
      `This starts a fresh session for ${newInfo.name} — it will NOT affect any of your existing saved designs from other countries, which keep their own saved settings regardless of what site you're on. Continue?`;

    if (window.confirm(message)) {
      window.location.href = newCode ? `/${newCode}` : "/";
    }
  };

  return (
    <div className="app">

      <SessionBar onSignOut={() => handleSignOut("main")} />

      {paymentReturnMessage && (
        <div
          className={`payment-return-banner payment-return-banner-${paymentReturnMessage.tone}`}
          role="status"
        >
          {paymentReturnMessage.text}
        </div>
      )}

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

      <div className="site-switch-bar" aria-label="Country site selection" title="Switching sites changes currency, materials catalog, and units for THIS session going forward — it does not affect your existing saved designs from other countries">
        <label htmlFor="propertyiq-site">Site</label>
        <select
          id="propertyiq-site"
          value={urlCountryContext?.code || ""}
          onChange={switchSite}
        >
          {SITE_OPTIONS.map(([code, label]) => (
            <option key={code || "global"} value={code}>{label}</option>
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

      </div>

      <div className="feature-strip" onClick={launchStudio} role="button" tabIndex={0}>
        <span className="feature-strip-icon">🏗</span>
        <span className="feature-strip-text">
          <strong>Construction Studio</strong> — design your build, place rooms on a real floor plan, get live cost estimates, and export a DXF, no property report needed.
        </span>
        <span className="feature-strip-arrow">→</span>
      </div>

      <div className="mission-section">
        <div className="mission-content">
          {formData.country === "India" ? (
            <>
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
            </>
          ) : (
            <>
              <h2>Why PropertyIQ exists</h2>
              <p>
                Buying property runs on trust that's rarely earned back. Developers routinely quote areas
                and per-unit rates with no defensible basis, describe the same living space very differently
                depending on which measurement convention favors the sale, and bury cost-escalation or
                change-of-plan clauses in agreements few buyers ever read closely. Asking prices are often
                little more than "what the market will bear" — copied from a neighboring project, adjusted
                for a broker's commission, with no real grounding in construction cost, land value, or
                genuinely comparable sales data.
              </p>
              <p>
                The common loopholes are well known inside the industry and almost invisible outside it:
                permits and registrations that don't quite match what's actually being delivered, official
                appraisal or guidance values quoted selectively depending on whether they favor a lower tax
                bill or a higher resale price, and floor-area figures that shift depending on which
                convention a developer chooses to use that day. A buyer evaluating a single property has no
                independent way to catch any of this before money changes hands.
              </p>
              <p>
                PropertyIQ exists to close that information gap. Every assessment cross-references public
                government records, fraud-pattern databases, and comparable transaction data for your
                property's country — the same kind of scrutiny a careful lawyer or engineer would apply,
                made accessible before you commit, not after a dispute. Construction Studio goes a step
                further: instead of trusting a developer's quoted rate, it prices your build from real,
                locally-researched material and labor costs, so you have an independent number to compare
                against what you're being asked to pay.
              </p>
            </>
          )}
          <p className="mission-tagline">
            Independent. Evidence-based. Built for the buyer, not the builder.
          </p>
        </div>
      </div>

      <div className="property-assessment-wrap">
        <CollapsiblePanel title="Property Assessment" defaultOpen={true} color="violet">
          <PropertyForm
            formData={formData}
            handleChange={handleChange}
            generateAssessment={generateAssessment}
            loading={loading}
          />
        </CollapsiblePanel>
      </div>

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