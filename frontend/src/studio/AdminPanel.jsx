import WindDownPanel from "./WindDownPanel";
import AdminManual from "./AdminManual";
import { Fragment, useEffect, useMemo, useState } from "react";
import { studioApi } from "./studioApi";
import WorldUsersMap from "./WorldUsersMap";

const TIER_ORDER = ["insight_addon", "studio_starter", "studio_pro", "studio_unlimited"];

// The menu items shown on the admin landing screen, matching
// AccidentIQ's own real admin-dashboard.html pattern exactly: a
// label, a short description, and a `screen` key the tile navigates
// to on click — clean segregation into sections, each reached by
// clicking its own tile, rather than one long page with everything
// visible at once.
// Human-readable labels for the fixed reason codes refund_store.py's
// VALID_REASON_CODES defines — matches the real refund policy clauses
// exactly (see refund_request_module_spec.md section 3), not invented
// separately from what the backend actually validates against.
const REFUND_REASON_LABELS = {
  report_never_generated: "Report never generated",
  duplicate_charge: "Duplicate charge",
  report_incorrect: "Report materially incorrect",
  insight_addon_technical_failure: "Quick Analysis didn't unlock",
  first_month_guarantee: "First-month guarantee",
  charged_after_cancellation: "Charged after cancellation",
  wrong_plan_charged: "Charged for the wrong plan",
  other: "Other",
};

const MENU_ITEMS = [
  { screen: "overview", label: "Overview & Analytics", desc: "Subscription counts, insight purchases, and estimated revenue." },
  { screen: "tiers", label: "Tier Configuration", desc: "Prices, quotas, and which features each tier includes." },
  { screen: "gemini", label: "Property URL Import — Gemini API Key", desc: "The LLM fallback key used when free structured-data extraction isn't enough." },
  { screen: "loan-eligibility", label: "Loan Eligibility — Thresholds", desc: "The real, configurable lending criteria (debt-to-income, loan-to-value, age cap, minimum credit rating) used for eligibility estimates." },
  { screen: "neighborhood", label: "Neighborhood Insights — Page Sections", desc: "Show or hide any section of the public Neighborhood Insights page." },
  { screen: "homepage", label: "Homepage — Free Quick-Check Panels", desc: "Show or hide any homepage panel or feature strip, and edit each feature strip's excitement-sticker wording." },
  { screen: "subscriptions", label: "Active Subscriptions", desc: "Browse current subscription records and their status." },
  { screen: "grants", label: "Quick Analysis Grants", desc: "Every Quick Analysis purchase and who it was granted to." },
  { screen: "refunds", label: "Refunds", desc: "Issue a real refund via Dodo, record one Dodo missed, and see refund history." },
  { screen: "refund-requests", label: "Refund Requests", desc: "Review and act on refund requests customers have actually submitted." },
  { screen: "manual", label: "User Manual", desc: "How every admin screen works, step-by-step runbooks (refunds, launch mode, wind-down, Dodo) and what to do when something goes wrong." },
  { screen: "reset-quota", label: "Reset User Quota", desc: "Give a user a fresh monthly design quota without waiting for the month to roll over." },
];

function AdminPanel({ onBack }) {
  const [password, setPassword] = useState("");
  const [authed, setAuthed] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [screen, setScreen] = useState("menu");

  const [tierConfig, setTierConfig] = useState(null);
  const [subscriptions, setSubscriptions] = useState([]);
  const [grants, setGrants] = useState([]);
  const [saveMessage, setSaveMessage] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [refreshTick, setRefreshTick] = useState(0);
  const [allFeatures, setAllFeatures] = useState([]);
  const [freeFeatures, setFreeFeatures] = useState([]);
  const [launchMode, setLaunchMode] = useState({ active: false, active_since: null, warnings: [] });
  const [launchModeMessage, setLaunchModeMessage] = useState("");
  const [freeEligible, setFreeEligible] = useState([]);
  const [freeMessage, setFreeMessage] = useState("");
  const [geminiKeyConfigured, setGeminiKeyConfigured] = useState(false);
  const [geminiKeyInput, setGeminiKeyInput] = useState("");
  const [geminiSaveMessage, setGeminiSaveMessage] = useState("");
  const [loanEligibilitySettings, setLoanEligibilitySettings] = useState(null);
  const [loanEligibilitySaveMessage, setLoanEligibilitySaveMessage] = useState("");
  const [niSectionVisibility, setNiSectionVisibility] = useState(null);
  const [niVisibilitySaveMessage, setNiVisibilitySaveMessage] = useState("");
  const [homepagePanelVisibility, setHomepagePanelVisibility] = useState(null);
  const [featureUsage, setFeatureUsage] = useState(null);
  const [techStack, setTechStack] = useState([]);
  const [usersByCountry, setUsersByCountry] = useState([]);
  const [homepageVisibilitySaveMessage, setHomepageVisibilitySaveMessage] = useState("");
  const [featureStickerText, setFeatureStickerText] = useState(null);
  const [stickerSaveMessage, setStickerSaveMessage] = useState("");

  // Refunds screen state
  const [refundLookupEmail, setRefundLookupEmail] = useState("");
  const [refundPayments, setRefundPayments] = useState(null);
  const [refundLookupNote, setRefundLookupNote] = useState("");
  const [refundHistory, setRefundHistory] = useState([]);
  const [refundMessage, setRefundMessage] = useState("");
  const [manualRefundForm, setManualRefundForm] = useState({ email: "", amount: "", currency: "USD", reason: "", note: "" });

  // Refund Requests screen state
  const [refundRequests, setRefundRequests] = useState([]);
  const [refundRequestsFilter, setRefundRequestsFilter] = useState("pending");
  const [refundRequestsMessage, setRefundRequestsMessage] = useState("");
  const [expandedRequestId, setExpandedRequestId] = useState(null);
  const [decisionForms, setDecisionForms] = useState({});

  // Reset User Quota screen state
  const [quotaLookupEmail, setQuotaLookupEmail] = useState("");
  const [quotaInfo, setQuotaInfo] = useState(null);
  const [quotaResetNote, setQuotaResetNote] = useState("");
  const [quotaMessage, setQuotaMessage] = useState("");

  // Everything the overview call returns, in one place, so login and Refresh
  // can never drift apart (Refresh used to update only some of it).
  const applyOverview = (data) => {
    setTierConfig(data.tier_config);
    setSubscriptions(data.subscriptions);
    setGrants(data.insight_grants);
    setAllFeatures(data.all_features || []);
    setFreeFeatures(data.free_features || []);
    setLaunchMode(data.launch_mode || { active: false, active_since: null, warnings: [] });
    setFreeEligible(data.free_eligible_features || []);
    setGeminiKeyConfigured(!!data.gemini_api_key_configured);
    setNiSectionVisibility(data.ni_section_visibility || null);
    setHomepagePanelVisibility(data.homepage_panel_visibility || null);
    setFeatureStickerText(data.feature_sticker_text || null);
    setFeatureUsage(data.feature_usage || null);
    setTechStack(data.tech_stack || []);
    setUsersByCountry(data.users_by_country || []);
  };

  const login = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await studioApi.adminOverview(password);
      applyOverview(data);
      setAuthed(true);
    } catch (err) {
      setError(err.message || "Incorrect password.");
    } finally {
      setLoading(false);
    }
  };

  const updateTierField = (tierId, field, value) => {
    setTierConfig((cfg) => ({
      ...cfg,
      [tierId]: { ...cfg[tierId], [field]: value },
    }));
  };

  // Toggling here only changes in-memory state — nothing takes effect
  // system-wide until "Save Changes" below actually persists it via
  // adminUpdateTiers, same as every other tier field on this page.
  // "Coming soon" disables buying a tier (pricing-page button AND the
  // server-side checkout). Always confirmed with a pop-up, in both
  // directions, since it changes what the public can buy the moment the
  // admin saves. Existing buyers/subscribers keep access either way.
  const toggleComingSoon = (tierId) => {
    const tier = tierConfig[tierId];
    const turningOn = !tier.coming_soon;
    const name = tier.label || tierId;
    const msg = turningOn
      ? `Mark "${name}" as COMING SOON?\n\nCustomers will no longer be able to buy it — the button turns into a disabled "Coming soon". People who already have it keep their access, and existing subscriptions keep renewing.\n\nThis takes effect for everyone once you click Save Changes.`
      : `Make "${name}" AVAILABLE TO BUY?\n\nCustomers will be able to purchase it (and be charged real money) as soon as you click Save Changes.`;
    if (!window.confirm(msg)) return;
    updateTierField(tierId, "coming_soon", turningOn);
  };

  // Opens a feature to every signed-in user with no purchase (or closes it
  // again). Saved immediately, behind a confirmation, because it changes
  // what the public can do the moment it's confirmed — it is NOT part of
  // the "Save Changes" tier batch below.
  const toggleFreeFeature = async (feature) => {
    const turningOn = !freeFeatures.includes(feature);
    const label = feature.replace(/_/g, " ");
    const msg = turningOn
      ? `Make "${label}" FREE for every signed-in user?\n\nAnyone with an account will be able to use it without buying anything. This takes effect immediately.`
      : `Stop giving "${label}" away for free?\n\nIt goes back to requiring a purchase or a subscription that includes it. This takes effect immediately.`;
    if (!window.confirm(msg)) return;
    const next = turningOn ? [...freeFeatures, feature] : freeFeatures.filter((f) => f !== feature);
    setFreeMessage("");
    setError("");
    try {
      const res = await studioApi.adminUpdateSettings(password, undefined, undefined, undefined, undefined, next);
      setFreeFeatures(res.free_features || next);
      setFreeMessage(`${label} is now ${turningOn ? "free for all signed-in users" : "back to paid-only"}.`);
    } catch (err) {
      setError(err.message || "Couldn't update free features.");
    }
  };

  // Master switch for a launch where only Quick Analysis is for sale. The
  // server applies (or restores) every related setting together and keeps
  // the previous state, so nothing is left to do by hand. After it runs,
  // everything on this page is re-read from the server so the screens show
  // the real current state.
  const toggleLaunchMode = async () => {
    const turningOn = !launchMode.active;
    const msg = turningOn
      ? "Turn ON Quick Analysis-only launch mode?\n\nThis stops NEW subscriptions and nothing else. Immediately, for everyone:\n• Studio Starter, Pro and Unlimited show as COMING SOON and can't be bought\n• The property assessment becomes FREE for signed-in users\n• Every Studio-linked panel (Construction Studio, Agent Intelligence, AI Advisor, Price Drop Alert, and the Neighborhood Insights tools like EMI, price trends, cost of living) is hidden from people who don't already have it\n\nPeople who already have a plan keep all their features, limits, renewals and panels.\n\nWhile it is ON, a safety monitor refuses any admin change that would open new subscriptions or take something away from a subscriber."
      : "Turn OFF launch mode?\n\nWhat it changed is undone: the Studio tiers become buyable again (if they were before), the assessment stops being free (if it wasn't before), and the home page strips return for everyone. Anything else you changed in the meantime is left alone.";
    if (!window.confirm(msg)) return;
    setLaunchModeMessage("");
    setError("");
    setLoading(true);
    try {
      const status = await studioApi.adminSetLaunchMode(password, turningOn);
      const data = await studioApi.adminOverview(password);
      setTierConfig(data.tier_config);
      setFreeFeatures(data.free_features || []);
      setHomepagePanelVisibility(data.homepage_panel_visibility || null);
      setLaunchMode(data.launch_mode || status);
      setLaunchModeMessage(turningOn ? "Launch mode is ON." : "Launch mode is OFF — previous settings restored.");
    } catch (err) {
      setError(err.message || "Couldn't change launch mode.");
    } finally {
      setLoading(false);
    }
  };

  const toggleTierFeature = (tierId, feature) => {
    setTierConfig((cfg) => {
      const current = cfg[tierId].features || [];
      const next = current.includes(feature)
        ? current.filter((f) => f !== feature)
        : [...current, feature];
      return { ...cfg, [tierId]: { ...cfg[tierId], features: next } };
    });
  };

  // A real, explicit admin control: removes a feature from every tier
  // at once, matching what the report page checks to decide whether to
  // show the feature at all — "hiding" a feature IS unchecking it
  // everywhere, not a separate flag, so the per-tier checkboxes below
  // correctly show as unchecked immediately, with no separate state to
  // keep in sync. Same in-memory-until-saved convention as every other
  // field here.
  const hideFeatureEverywhere = (feature) => {
    setTierConfig((cfg) => {
      const next = { ...cfg };
      for (const tierId of Object.keys(next)) {
        next[tierId] = {
          ...next[tierId],
          features: (next[tierId].features || []).filter((f) => f !== feature),
        };
      }
      return next;
    });
  };

  const saveTiers = async () => {
    setSaveMessage("");
    setError("");
    setLoading(true);
    try {
      await studioApi.adminUpdateTiers(password, tierConfig);
      setSaveMessage("Tier config saved.");
    } catch (err) {
      setError(err.message || "Couldn't save changes.");
    } finally {
      setLoading(false);
    }
  };

  // Backs the property_url_import feature's LLM fallback (used only
  // when the free structured-data extraction path doesn't find enough)
  // — a real, explicit request: making this key admin-configurable at
  // runtime rather than only an env var, so it can be changed without a
  // redeploy. The backend never returns the actual key value back, even
  // here — only whether one is currently configured.
  const saveGeminiKey = async () => {
    setGeminiSaveMessage("");
    setError("");
    if (!geminiKeyInput.trim()) return;
    setLoading(true);
    try {
      const res = await studioApi.adminUpdateSettings(password, geminiKeyInput.trim());
      setGeminiKeyConfigured(!!res.gemini_api_key_configured);
      setGeminiKeyInput("");
      setGeminiSaveMessage("Gemini API key saved.");
    } catch (err) {
      setError(err.message || "Couldn't save the Gemini API key.");
    } finally {
      setLoading(false);
    }
  };

  // Only sends the one field that actually changed -- the backend's
  // own partial-update handling means the other 3 thresholds stay
  // exactly as an admin already configured them.
  const saveLoanEligibilitySetting = async (field, value) => {
    setLoanEligibilitySaveMessage("");
    setError("");
    setLoading(true);
    try {
      const updated = await studioApi.adminUpdateLoanEligibilitySettings(password, { [field]: value });
      setLoanEligibilitySettings(updated);
      setLoanEligibilitySaveMessage("Saved.");
    } catch (err) {
      setError(err.message || "Couldn't save this threshold.");
    } finally {
      setLoading(false);
    }
  };

  // Toggling here only changes in-memory state — nothing takes effect
  // on the live page until "Save" below actually persists it, same
  // pattern as every other admin setting on this page.
  const toggleNiSection = (section) => {
    setNiSectionVisibility((prev) => ({ ...prev, [section]: !prev[section] }));
  };

  const saveNiSectionVisibility = async () => {
    setNiVisibilitySaveMessage("");
    setError("");
    setLoading(true);
    try {
      const res = await studioApi.adminUpdateSettings(password, undefined, niSectionVisibility);
      setNiSectionVisibility(res.ni_section_visibility || niSectionVisibility);
      setNiVisibilitySaveMessage("Section visibility saved.");
    } catch (err) {
      setError(err.message || "Couldn't save section visibility.");
    } finally {
      setLoading(false);
    }
  };

  const toggleHomepagePanel = (panel) => {
    setHomepagePanelVisibility((prev) => ({ ...prev, [panel]: !prev[panel] }));
  };

  const saveHomepagePanelVisibility = async () => {
    setHomepageVisibilitySaveMessage("");
    setError("");
    setLoading(true);
    try {
      const res = await studioApi.adminUpdateSettings(password, undefined, undefined, homepagePanelVisibility);
      setHomepagePanelVisibility(res.homepage_panel_visibility || homepagePanelVisibility);
      setHomepageVisibilitySaveMessage("Panel visibility saved.");
    } catch (err) {
      setError(err.message || "Couldn't save panel visibility.");
    } finally {
      setLoading(false);
    }
  };

  // Toggling here only changes in-memory state — nothing takes effect
  // on the live homepage until "Save" below actually persists it, same
  // in-memory-until-saved convention as every other field on this page.
  const updateStickerText = (panel, text) => {
    setFeatureStickerText((prev) => ({ ...prev, [panel]: text }));
  };

  const saveFeatureStickerText = async () => {
    setStickerSaveMessage("");
    setError("");
    setLoading(true);
    try {
      const res = await studioApi.adminUpdateSettings(password, undefined, undefined, undefined, featureStickerText);
      setFeatureStickerText(res.feature_sticker_text || featureStickerText);
      setStickerSaveMessage("Sticker text saved.");
    } catch (err) {
      setError(err.message || "Couldn't save sticker text.");
    } finally {
      setLoading(false);
    }
  };

  const loadRefundHistory = async () => {
    try {
      const res = await studioApi.adminListRefunds(password);
      setRefundHistory(res.refunds || []);
    } catch (err) {
      setError(err.message || "Couldn't load refund history.");
    }
  };

  useEffect(() => {
    if (screen === "refunds" && authed) {
      Promise.resolve().then(loadRefundHistory);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- deliberately only re-runs on screen change, not on every password/authed re-render — loadRefundHistory itself is stable enough here and re-fetching on unrelated state changes isn't needed
  }, [screen]);

  useEffect(() => {
    if (screen === "loan-eligibility" && authed && !loanEligibilitySettings) {
      studioApi.getLoanEligibilitySettings().then(setLoanEligibilitySettings).catch((err) => setError(err.message || "Couldn't load loan eligibility settings."));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [screen, authed]);

  const loadRefundRequests = async (statusFilter) => {
    try {
      const res = await studioApi.adminListRefundRequests(password, statusFilter || undefined);
      setRefundRequests(res.requests || []);
    } catch (err) {
      setError(err.message || "Couldn't load refund requests.");
    }
  };

  useEffect(() => {
    if (screen === "refund-requests" && authed) {
      Promise.resolve().then(() => loadRefundRequests(refundRequestsFilter));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- re-runs on screen entry and on filter change; loadRefundRequests itself is stable here
  }, [screen, refundRequestsFilter]);

  const updateDecisionForm = (requestId, patch) => {
    setDecisionForms((prev) => ({ ...prev, [requestId]: { ...(prev[requestId] || {}), ...patch } }));
  };

  const approveViaDodo = async (requestId) => {
    const form = decisionForms[requestId] || {};
    if (!form.paymentId?.trim()) {
      setError("Enter the Dodo payment_id to refund.");
      return;
    }
    if (!window.confirm("Issue a real refund through Dodo for this request? This actually moves money and can't be undone from here.")) return;
    setRefundRequestsMessage("");
    setError("");
    setLoading(true);
    try {
      await studioApi.adminApproveRefundRequestViaDodo(password, requestId, form.paymentId.trim(), form.response?.trim() || undefined);
      setRefundRequestsMessage("Refund issued and request approved.");
      await loadRefundRequests(refundRequestsFilter);
    } catch (err) {
      setError(err.message || "Couldn't approve via Dodo.");
    } finally {
      setLoading(false);
    }
  };

  const approveManually = async (requestId) => {
    const form = decisionForms[requestId] || {};
    if (!form.amount || !form.note?.trim()) {
      setError("Amount and a note on how it was actually refunded are both required for a manual approval.");
      return;
    }
    setRefundRequestsMessage("");
    setError("");
    setLoading(true);
    try {
      await studioApi.adminApproveRefundRequestManually(password, requestId, Number(form.amount), form.currency || "USD", form.note.trim(), form.response?.trim() || undefined);
      setRefundRequestsMessage("Manual refund recorded and request approved.");
      await loadRefundRequests(refundRequestsFilter);
    } catch (err) {
      setError(err.message || "Couldn't record the manual approval.");
    } finally {
      setLoading(false);
    }
  };

  const denyRequest = async (requestId) => {
    const form = decisionForms[requestId] || {};
    if (!form.response?.trim()) {
      setError("A reason is required when denying a request — it's shown back to the customer.");
      return;
    }
    setRefundRequestsMessage("");
    setError("");
    setLoading(true);
    try {
      await studioApi.adminDenyRefundRequest(password, requestId, form.response.trim());
      setRefundRequestsMessage("Request denied.");
      await loadRefundRequests(refundRequestsFilter);
    } catch (err) {
      setError(err.message || "Couldn't deny the request.");
    } finally {
      setLoading(false);
    }
  };

  const lookupQuota = async () => {
    setQuotaMessage("");
    setError("");
    setQuotaInfo(null);
    if (!quotaLookupEmail.trim()) return;
    setLoading(true);
    try {
      const res = await studioApi.adminLookupQuota(password, quotaLookupEmail.trim());
      setQuotaInfo(res);
    } catch (err) {
      setError(err.message || "Couldn't look up this user's quota.");
    } finally {
      setLoading(false);
    }
  };

  const resetQuota = async () => {
    setQuotaMessage("");
    setError("");
    if (!window.confirm(`Reset the monthly design quota for ${quotaLookupEmail.trim()}? They'll be able to generate again immediately.`)) return;
    setLoading(true);
    try {
      const res = await studioApi.adminResetQuota(password, quotaLookupEmail.trim(), quotaResetNote.trim() || undefined);
      setQuotaMessage(`Quota reset — ${res.user_email} now shows ${res.designs_used_this_month} used this month.`);
      setQuotaResetNote("");
      await lookupQuota();
    } catch (err) {
      setError(err.message || "Couldn't reset the quota.");
    } finally {
      setLoading(false);
    }
  };

  const lookupPayments = async () => {
    setRefundMessage("");
    setError("");
    setRefundPayments(null);
    if (!refundLookupEmail.trim()) return;
    setLoading(true);
    try {
      const res = await studioApi.adminLookupPayments(password, refundLookupEmail.trim());
      setRefundPayments(res.payments || []);
      setRefundLookupNote(res.note || "");
    } catch (err) {
      setError(err.message || "Couldn't look up payments.");
    } finally {
      setLoading(false);
    }
  };

  const issueRefund = async (paymentId) => {
    setRefundMessage("");
    setError("");
    // A real, irreversible action — this actually moves money back to
    // the customer via Dodo, so confirming here matters more than for
    // most other admin actions on this page.
    if (!window.confirm(`Issue a full refund for payment ${paymentId}? This actually refunds the customer through Dodo — it can't be undone from here.`)) return;
    setLoading(true);
    try {
      await studioApi.adminIssueRefund(password, paymentId, refundLookupEmail.trim(), "Refunded via admin panel");
      setRefundMessage(`Refund issued for ${paymentId}.`);
      await loadRefundHistory();
      await lookupPayments();
    } catch (err) {
      setError(err.message || "Couldn't issue refund.");
    } finally {
      setLoading(false);
    }
  };

  const submitManualRefund = async () => {
    setRefundMessage("");
    setError("");
    const { email, amount, currency, reason, note } = manualRefundForm;
    if (!email.trim() || !amount || !reason.trim() || !note.trim()) {
      setError("Email, amount, reason, and a note are all required for a manual refund record.");
      return;
    }
    setLoading(true);
    try {
      await studioApi.adminRecordManualRefund(password, email.trim(), Number(amount), currency, reason.trim(), note.trim());
      setRefundMessage("Manual refund recorded.");
      setManualRefundForm({ email: "", amount: "", currency: "USD", reason: "", note: "" });
      await loadRefundHistory();
    } catch (err) {
      setError(err.message || "Couldn't record manual refund.");
    } finally {
      setLoading(false);
    }
  };

  // Re-reads everything on the current screen from the server and says so.
  // (It used to update only part of the data and show nothing, so it looked
  // dead.) Anything typed but not yet saved on the tier screen is replaced
  // by what the server has, which is what a refresh means.
  const refresh = async () => {
    if (refreshing) return;
    setRefreshing(true);
    setError("");
    setSaveMessage("");
    try {
      // true: bypasses the 15-minute Dodo price cache, since Refresh is the
      // moment a just-changed Dodo price is most wanted.
      applyOverview(await studioApi.adminOverview(password, true));
      if (screen === "refunds") await loadRefundHistory();
      if (screen === "refund-requests") await loadRefundRequests(refundRequestsFilter);
      if (screen === "loan-eligibility") setLoanEligibilitySettings(await studioApi.getLoanEligibilitySettings());
      setRefreshTick((n) => n + 1);
      setSaveMessage(`Refreshed at ${new Date().toLocaleTimeString()}.`);
    } catch (err) {
      setError(err.message || "Couldn't refresh.");
    } finally {
      setRefreshing(false);
    }
  };

  const activeSubCount = useMemo(
    () => subscriptions.filter((s) => s.status === "active").length,
    [subscriptions]
  );

  // Estimated revenue analytics — computed from configured list prices ×
  // real counts, same as AccidentIQ's admin analytics. This is NOT pulled
  // from live Dodo transaction data (no such integration exists), so it's
  // an estimate: it won't reflect discounts, refunds, or mid-cycle changes.
  const revenueAnalytics = useMemo(() => {
    if (!tierConfig) return null;

    const subscriptionTiers = TIER_ORDER.filter(
      (id) => tierConfig[id] && tierConfig[id].billing === "subscription"
    ).map((tierId) => {
      const activeCount = subscriptions.filter((s) => s.status === "active" && s.tier_id === tierId).length;
      const priceUsd = tierConfig[tierId].price_usd;
      return {
        tierId,
        label: tierConfig[tierId].label,
        activeCount,
        priceUsd,
        subtotalUsd: activeCount * priceUsd,
      };
    });

    const estimatedMrrUsd = subscriptionTiers.reduce((sum, t) => sum + t.subtotalUsd, 0);
    const insightPriceUsd = tierConfig.insight_addon?.price_usd || 0;
    const insightRevenueUsd = grants.length * insightPriceUsd;
    const insightLabel = tierConfig.insight_addon?.label || "Quick Analysis";

    return { subscriptionTiers, estimatedMrrUsd, insightRevenueUsd, insightPriceUsd, insightLabel };
  }, [tierConfig, subscriptions, grants]);

  if (!authed) {
    return (
      <div className="admin-login-wrap">
        <div className="admin-login-card">
          <h2>Admin Access</h2>
          <p className="admin-login-subtitle">Enter the admin password to manage tiers and view activity.</p>
          <form onSubmit={login}>
            {error && <div className="admin-login-error">{error}</div>}
            <input
              type="password"
              placeholder="Admin password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoFocus
              required
            />
            <button className="admin-login-btn" type="submit" disabled={loading}>
              {loading ? "Checking..." : "Enter"}
            </button>
          </form>
          <span className="admin-login-back" onClick={onBack}>← Back</span>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-dashboard">
      <div className="admin-dashboard-header">
        <div>
          <div className="admin-dashboard-eyebrow">PropertyIQWeb Studio</div>
          <h2>{screen === "menu" ? "Admin Dashboard" : MENU_ITEMS.find((i) => i.screen === screen)?.label}</h2>
        </div>
        <button type="button" className="page-refresh-btn admin-refresh-btn" onClick={refresh} disabled={refreshing}>{refreshing ? "Refreshing…" : "⟳ Refresh"}</button>
      </div>

      {error && (
        <div className="studio-status-banner" style={{ background: "#fef2f2", borderColor: "#fecaca", color: "#991b1b" }}>
          {error}
        </div>
      )}
      {saveMessage && <div className="studio-status-banner">{saveMessage}</div>}

      {screen === "menu" && (
        <>
          <p className="admin-menu-subtitle">Choose a section.</p>
          <div className="admin-menu-grid">
            {MENU_ITEMS.map((item) => (
              <div key={item.screen} className="menu-tile" onClick={() => setScreen(item.screen)}>
                <div className="menu-tile-label">{item.label}</div>
                <div className="menu-tile-desc">{item.desc}</div>
              </div>
            ))}
          </div>
        </>
      )}

      {screen === "overview" && (
        <>
          <button type="button" className="admin-subscreen-back" onClick={() => setScreen("menu")}>← Back to menu</button>

          <div className="admin-stats-row">
            <div className="admin-stat-card admin-stat-purple">
              <div className="admin-stat-value">{activeSubCount}</div>
              <div className="admin-stat-label">Active Subscriptions</div>
            </div>
            <div className="admin-stat-card admin-stat-blue">
              <div className="admin-stat-value">{subscriptions.length}</div>
              <div className="admin-stat-label">Total Subscription Records</div>
            </div>
            <div className="admin-stat-card admin-stat-green">
              <div className="admin-stat-value">{grants.length}</div>
              <div className="admin-stat-label">{revenueAnalytics?.insightLabel || "Quick Analysis"} Purchases</div>
            </div>
            <div className="admin-stat-card admin-stat-slate">
              <div className="admin-stat-value">{TIER_ORDER.filter((id) => tierConfig?.[id]).length}</div>
              <div className="admin-stat-label">Configured Tiers</div>
            </div>
          </div>

          {revenueAnalytics && (
            <div className="admin-section admin-section-amber">
              <h3>Revenue Analytics</h3>
              <p className="admin-empty-note" style={{ marginTop: -6, marginBottom: 16 }}>
                Estimated from configured list prices × real counts — not live Dodo transaction
                data, so this won't reflect discounts, refunds, or mid-cycle plan changes.
              </p>

              <div className="admin-stats-row" style={{ marginBottom: 20 }}>
                <div className="admin-stat-card admin-stat-purple">
                  <div className="admin-stat-value">${revenueAnalytics.estimatedMrrUsd.toLocaleString()}</div>
                  <div className="admin-stat-label">Estimated MRR (subscriptions)</div>
                </div>
                <div className="admin-stat-card admin-stat-green">
                  <div className="admin-stat-value">${revenueAnalytics.insightRevenueUsd.toLocaleString()}</div>
                  <div className="admin-stat-label">{revenueAnalytics.insightLabel} Revenue (one-time, all-time)</div>
                </div>
              </div>

              <div className="admin-table-scroll">
                <table className="admin-table">
                  <thead>
                    <tr><th>Tier</th><th>Active Subscribers</th><th>Price (USD/mo)</th><th>Subtotal (USD/mo)</th></tr>
                  </thead>
                  <tbody>
                    {revenueAnalytics.subscriptionTiers.map((t) => (
                      <tr key={t.tierId}>
                        <td>{t.label}</td>
                        <td>{t.activeCount}</td>
                        <td>${t.priceUsd}</td>
                        <td>${t.subtotalUsd.toLocaleString()}</td>
                      </tr>
                    ))}
                    <tr>
                      <td><strong>{revenueAnalytics.insightLabel}</strong></td>
                      <td>{grants.length} purchase{grants.length === 1 ? "" : "s"}</td>
                      <td>${revenueAnalytics.insightPriceUsd}</td>
                      <td>${revenueAnalytics.insightRevenueUsd.toLocaleString()}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {revenueAnalytics && (
            <div className="admin-section admin-section-purple">
              <h3>Users by Tier</h3>
              <div className="admin-tier-bar-chart">
                {revenueAnalytics.subscriptionTiers.map((t) => {
                  const maxCount = Math.max(1, ...revenueAnalytics.subscriptionTiers.map((x) => x.activeCount));
                  return (
                    <div key={t.tierId} className="admin-tier-bar-row">
                      <span className="admin-tier-bar-label">{t.label}</span>
                      <div className="admin-tier-bar-track">
                        <div className="admin-tier-bar-fill" style={{ width: `${(t.activeCount / maxCount) * 100}%` }} />
                      </div>
                      <span className="admin-tier-bar-count">{t.activeCount}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {featureUsage && (
            <div className="admin-section admin-section-blue">
              <h3>Usage Stats per Feature</h3>
              <p className="admin-section-note" style={{ marginTop: -8 }}>
                Real counts from the database — a row only exists here if a user actually used that feature.
              </p>
              <div className="admin-table-scroll">
                <table className="admin-table">
                  <thead><tr><th>Feature</th><th>Real Usage Count</th></tr></thead>
                  <tbody>
                    {Object.entries(featureUsage.counts).map(([label, count]) => (
                      <tr key={label}><td>{label}</td><td>{count}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {featureUsage.not_tracked?.length > 0 && (
                <p className="admin-empty-note" style={{ marginTop: 12 }}>
                  Not tracked yet (on-demand features with no saved record): {featureUsage.not_tracked.join(", ")}
                </p>
              )}
            </div>
          )}

          {techStack.length > 0 && (
            <div className="admin-section admin-section-green">
              <h3>Tech Stack Status</h3>
              <div className="admin-tech-stack-grid">
                {techStack.map((s) => (
                  <div key={s.name} className={`admin-tech-stack-item ${s.configured ? "admin-tech-ok" : "admin-tech-missing"}`}>
                    <span>{s.configured ? "✓" : "✗"}</span> {s.name}
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="admin-section admin-section-slate">
            <h3>Subscribers by Location</h3>
            <p className="admin-section-note" style={{ marginTop: -8 }}>
              Captured from a visitor's own real location at sign-in, going forward only — not retroactive for users who signed in before this was added.
            </p>
            <WorldUsersMap usersByCountry={usersByCountry} />
          </div>
        </>
      )}

      {screen === "tiers" && (
        <>
          <button type="button" className="admin-subscreen-back" onClick={() => setScreen("menu")}>← Back to menu</button>

          <div className="admin-section admin-section-purple">
            <h3>Quick Analysis-only launch mode</h3>
            <p className="admin-section-note" style={{ marginTop: -8 }}>
              One switch for a launch where only Quick Analysis is for sale. It stops NEW subscriptions
              and nothing else. ON: Studio tiers become Coming soon, the property assessment becomes free
              for signed-in users, and every Studio-linked panel is hidden from people who don't already have it.
              Existing subscribers keep everything. A safety monitor refuses any change made while it is ON that would
              open new subscriptions or take something from a subscriber. OFF: all of that is undone.
            </p>
            <label className="admin-feature-checkbox" style={{ fontWeight: 600 }}>
              <input type="checkbox" checked={launchMode.active} onChange={toggleLaunchMode} disabled={loading} />
              Quick Analysis-only launch mode is {launchMode.active ? "ON" : "OFF"}
              {launchMode.active && launchMode.active_since ? ` (since ${new Date(launchMode.active_since).toLocaleString()})` : ""}
            </label>
            {(launchMode.warnings || []).map((w) => (
              <div key={w} className="studio-status-banner" style={{ background: "#fef2f2", borderColor: "#fecaca", color: "#991b1b" }}>⚠ {w}</div>
            ))}
            {launchModeMessage && <div className="studio-status-banner">{launchModeMessage}</div>}
            {(launchMode.safety_events || []).length > 0 && (
              <details style={{ marginTop: 8 }}>
                <summary>Safety monitor log ({launchMode.safety_events.length} recent)</summary>
                <ul style={{ fontSize: 13, margin: "6px 0 0 16px" }}>
                  {launchMode.safety_events.map((e) => (
                    <li key={e.at + e.detail}>
                      {new Date(e.at).toLocaleString()} — <strong>{e.kind}</strong>: {e.detail}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </div>

          <WindDownPanel password={password} refreshTick={refreshTick} />

          <div className="admin-section admin-section-purple">
            <h3>Tier Configuration</h3>
            <div className="admin-tier-row admin-tier-row-header">
              <span>Tier</span><span>Price (from Dodo)</span><span>Generate/mo (blank = unlimited, 0 = one-time)</span><span>Saved designs (blank = unlimited)</span><span>Max price watches (blank = unlimited)</span><span>Agent clients (blank = unlimited)</span><span>Properties per client (blank = unlimited)</span><span>Label</span>
            </div>
            <p className="admin-section-note" style={{ marginTop: -8 }}>
              Price is read directly from Dodo Payments — the real, actual amount a customer is
              charged — and can't be edited here. Change it in the Dodo dashboard instead; editing a
              locally-stored number here could never actually change what anyone pays, since checkout
              only ever sends Dodo a product ID, not a price.
            </p>
            {TIER_ORDER.filter((id) => tierConfig?.[id]).map((tierId) => {
              const tier = tierConfig[tierId];
              return (
                <Fragment key={tierId}>
                  <div className="admin-tier-row">
                    <span className="admin-tier-row-name" data-label="Tier">{tierId}</span>
                    <span data-label="Price (from Dodo)" title={tier.price_source === "dodo" ? "Live value from Dodo Payments" : "Dodo price unavailable right now — showing the last known/local fallback value"}>
                      <input
                        type="text"
                        disabled
                        value={`$${tier.price_usd}${tier.price_source === "dodo" ? "" : " (fallback)"}`}
                      />
                    </span>
                    <span data-label="Generate/mo">
                    <input
                      type="number"
                      value={tier.design_quota_per_month ?? ""}
                      placeholder="unlimited"
                      onChange={(e) =>
                        updateTierField(tierId, "design_quota_per_month", e.target.value === "" ? null : Number(e.target.value))
                      }
                    />
                    </span>
                    <span data-label="Saved designs">
                    <input
                      type="number"
                      value={tier.saved_designs_limit ?? ""}
                      placeholder="unlimited"
                      onChange={(e) =>
                        updateTierField(tierId, "saved_designs_limit", e.target.value === "" ? null : Number(e.target.value))
                      }
                    />
                    </span>
                    <span data-label="Max price watches">
                    <input
                      type="number"
                      value={tier.max_price_watches ?? ""}
                      placeholder="unlimited watches"
                      title="Max active Price Drop Alert watches this tier can have at once — leave blank for unlimited"
                      onChange={(e) =>
                        updateTierField(tierId, "max_price_watches", e.target.value === "" ? null : Number(e.target.value))
                      }
                    />
                    </span>
                    <span data-label="Agent clients">
                    <input
                      type="number"
                      value={tier.max_agent_clients ?? ""}
                      placeholder="unlimited clients"
                      title="Max clients an Agent Intelligence user on this tier can add at once — leave blank for unlimited"
                      onChange={(e) =>
                        updateTierField(tierId, "max_agent_clients", e.target.value === "" ? null : Number(e.target.value))
                      }
                    />
                    </span>
                    <span data-label="Properties per client">
                    <input
                      type="number"
                      value={tier.max_properties_per_client ?? ""}
                      placeholder="unlimited properties"
                      title="Max properties per client this tier's Agent Intelligence users can add — leave blank for unlimited"
                      onChange={(e) =>
                        updateTierField(tierId, "max_properties_per_client", e.target.value === "" ? null : Number(e.target.value))
                      }
                    />
                    </span>
                    <span data-label="Label">
                    <input
                      type="text"
                      placeholder="Label"
                      value={tier.label}
                      onChange={(e) => updateTierField(tierId, "label", e.target.value)}
                    />
                    </span>
                  </div>
                  <div className="admin-tier-features-row">
                    <span className="admin-tier-features-label">Features:</span>
                    {allFeatures.map((feature) => (
                      <label key={feature} className="admin-feature-checkbox" title={`Toggle ${feature} for this tier — takes effect immediately everywhere once saved`}>
                        <input
                          type="checkbox"
                          checked={(tier.features || []).includes(feature)}
                          onChange={() => toggleTierFeature(tierId, feature)}
                        />
                        {feature}
                      </label>
                    ))}
                  </div>
                  <div className="admin-tier-features-row" title="Coming soon: the tier stays listed on the pricing page but can't be bought — the button is disabled and the server rejects checkout. Existing buyers and subscribers are not affected.">
                    <span className="admin-tier-features-label">Availability:</span>
                    <label className="admin-feature-checkbox">
                      <input
                        type="checkbox"
                        checked={tier.coming_soon === true}
                        onChange={() => toggleComingSoon(tierId)}
                      />
                      Coming soon (purchases disabled)
                    </label>
                  </div>
                  {tierId === "insight_addon" && (
                    <div className="admin-tier-features-row" title="Free: similar-property suggestions are available to everyone, no purchase — the buy button disappears. Paid: the current behavior — a purchase or active subscription is required, and the panel stays hidden until unlocked.">
                      <span className="admin-tier-features-label">Mode:</span>
                      <label className="admin-feature-checkbox">
                        <input
                          type="radio"
                          name="insight-addon-mode"
                          checked={(tier.mode ?? "paid") === "paid"}
                          onChange={() => updateTierField(tierId, "mode", "paid")}
                        />
                        Paid (default — requires purchase or subscription)
                      </label>
                      <label className="admin-feature-checkbox">
                        <input
                          type="radio"
                          name="insight-addon-mode"
                          checked={tier.mode === "free"}
                          onChange={() => updateTierField(tierId, "mode", "free")}
                        />
                        Free (available to everyone, no purchase)
                      </label>
                    </div>
                  )}
                </Fragment>
              );
            })}
            <div className="admin-tier-features-row" style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--grey-200, #d6e4ec)" }} title="Features ticked here are available to every signed-in user with no purchase. Takes effect immediately (with a confirmation) — not part of Save Changes.">
              <span className="admin-tier-features-label">Free for all signed-in users:</span>
              {freeEligible.map((feature) => (
                <label key={feature} className="admin-feature-checkbox">
                  <input
                    type="checkbox"
                    checked={freeFeatures.includes(feature)}
                    onChange={() => toggleFreeFeature(feature)}
                  />
                  {feature}
                </label>
              ))}
            </div>
            {freeMessage && <div className="studio-status-banner">{freeMessage}</div>}
            <div className="admin-tier-features-row" style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--grey-200, #d6e4ec)" }}>
              <span className="admin-tier-features-label">Hide from main page (all tiers):</span>
              {allFeatures.map((feature) => (
                <button
                  key={feature}
                  type="button"
                  className="admin-feature-hide-btn"
                  title={`Removes ${feature} from every tier at once, hiding it from the main page entirely — same as unchecking it above on each tier, just in one click. Requires Save Changes below to take effect.`}
                  onClick={() => hideFeatureEverywhere(feature)}
                >
                  Hide {feature}
                </button>
              ))}
            </div>
            <button className="cs-nav-btn cs-nav-primary" style={{ marginTop: 16 }} onClick={saveTiers} disabled={loading}>
              {loading ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </>
      )}

      {screen === "gemini" && (
        <>
          <button type="button" className="admin-subscreen-back" onClick={() => setScreen("menu")}>← Back to menu</button>

          <div className="admin-section admin-section-purple">
            <h3>Property URL Import — Gemini API Key</h3>
            <p className="admin-section-note">
              Used only as a fallback when the free structured-data extraction path (schema.org / Open Graph
              metadata already on the page) doesn't find enough — many imports cost nothing at all beyond this.
              Status: <strong>{geminiKeyConfigured ? "Configured" : "Not set"}</strong> (the key itself is never
              shown back once saved, for security).
            </p>
            <div className="admin-tier-row" style={{ gridTemplateColumns: "1fr auto" }}>
              <input
                type="password"
                placeholder={geminiKeyConfigured ? "Enter a new key to replace the current one" : "Enter your Gemini API key"}
                value={geminiKeyInput}
                onChange={(e) => setGeminiKeyInput(e.target.value)}
              />
              <button className="cs-nav-btn cs-nav-primary" onClick={saveGeminiKey} disabled={loading || !geminiKeyInput.trim()}>
                {loading ? "Saving..." : "Save Key"}
              </button>
            </div>
            {geminiSaveMessage && <div className="studio-status-banner">{geminiSaveMessage}</div>}
          </div>
        </>
      )}

      {screen === "loan-eligibility" && (
        <>
          <button type="button" className="admin-subscreen-back" onClick={() => setScreen("menu")}>← Back to menu</button>

          <div className="admin-section admin-section-purple">
            <h3>Loan Eligibility — Thresholds</h3>
            <p className="admin-section-note">
              These are estimates using standard lending rules of thumb — not a real bank's actual underwriting
              decision. Every threshold below is real and takes effect immediately across both the public Loan
              Eligibility panel and Agent Intelligence's own eligibility checks.
            </p>
            {!loanEligibilitySettings ? (
              <p>Loading...</p>
            ) : (
              <div className="admin-loan-settings-grid">
                <label>
                  Max debt-to-income (FOIR) %
                  <input
                    type="number" min="1" max="100" defaultValue={loanEligibilitySettings.max_foir_percent}
                    onBlur={(e) => e.target.value && saveLoanEligibilitySetting("max_foir_percent", Number(e.target.value))}
                  />
                </label>
                <label>
                  Max loan-to-value (LTV) %
                  <input
                    type="number" min="1" max="100" defaultValue={loanEligibilitySettings.max_ltv_percent}
                    onBlur={(e) => e.target.value && saveLoanEligibilitySetting("max_ltv_percent", Number(e.target.value))}
                  />
                </label>
                <label>
                  Max age at loan maturity
                  <input
                    type="number" min="19" max="100" defaultValue={loanEligibilitySettings.max_age_at_maturity}
                    onBlur={(e) => e.target.value && saveLoanEligibilitySetting("max_age_at_maturity", Number(e.target.value))}
                  />
                </label>
                <label>
                  Minimum credit rating
                  <select
                    defaultValue={loanEligibilitySettings.min_credit_rating}
                    onChange={(e) => saveLoanEligibilitySetting("min_credit_rating", e.target.value)}
                  >
                    <option value="poor">Poor</option>
                    <option value="fair">Fair</option>
                    <option value="good">Good</option>
                    <option value="excellent">Excellent</option>
                  </select>
                </label>
              </div>
            )}
            {loanEligibilitySaveMessage && <div className="studio-status-banner">{loanEligibilitySaveMessage}</div>}
          </div>
        </>
      )}

      {screen === "neighborhood" && (
        <>
          <button type="button" className="admin-subscreen-back" onClick={() => setScreen("menu")}>← Back to menu</button>

          <div className="admin-section">
            <h3>Neighborhood Insights — Page Sections</h3>
            <p className="admin-section-note">
              Show or hide any section of the public Neighborhood Insights page without a code change or
              redeploy — useful for temporarily hiding a section (e.g. Infrastructure) while sorting out an
              issue with it, without taking the whole page down.
            </p>
            {niSectionVisibility ? (
              <>
                {[
                  { key: "map", label: "Neighborhood map (nearby places)" },
                  { key: "flood_risk", label: "Flood & waterlogging risk" },
                  { key: "infrastructure", label: "Upcoming infrastructure" },
                  { key: "resale_signal", label: "Resale demand signal" },
                  { key: "extended_metrics", label: "More about this area (air quality, rankings, etc.)" },
                  { key: "comparison", label: "Compare areas (paid feature)" },
                  { key: "price_trends", label: "Price trends (paid feature)" },
                  { key: "cost_of_living", label: "Cost of living (paid feature)" },
                  { key: "emi_calculator", label: "EMI calculator (paid feature)" },
                  { key: "amortization_projector", label: "Amortization projector (paid feature)" },
                  { key: "checklist", label: "Buyer's due-diligence checklist" },
                  { key: "authority_contacts", label: "Local authority contacts" },
                  { key: "cross_sell", label: "PropertyIQWeb cross-sell card" },
                  { key: "share", label: "Share this report" },
                ].map(({ key, label }) => (
                  <div key={key} className="admin-toggle-row">
                    <label htmlFor={`ni-toggle-${key}`}>{label}</label>
                    <label className="admin-switch" htmlFor={`ni-toggle-${key}`}>
                      <input
                        id={`ni-toggle-${key}`}
                        type="checkbox"
                        checked={!!niSectionVisibility[key]}
                        onChange={() => toggleNiSection(key)}
                      />
                      <span className="admin-slider"></span>
                    </label>
                  </div>
                ))}
                <button className="cs-nav-btn cs-nav-primary" style={{ marginTop: 16 }} onClick={saveNiSectionVisibility} disabled={loading}>
                  {loading ? "Saving..." : "Save"}
                </button>
                {niVisibilitySaveMessage && <div className="studio-status-banner">{niVisibilitySaveMessage}</div>}
              </>
            ) : (
              <p className="admin-empty-note">Loading...</p>
            )}
          </div>
        </>
      )}

      {screen === "homepage" && (
        <>
          <button type="button" className="admin-subscreen-back" onClick={() => setScreen("menu")}>← Back to menu</button>

          <div className="admin-section">
            <h3>Homepage — Feature Panels</h3>
            <p className="admin-section-note">
              Show or hide any of these homepage panels without a code change or redeploy — useful for
              temporarily hiding a panel while sorting out an issue with it, without taking the homepage down.
              The first 5 are free quick-checks; Construction Studio, Agent Intelligence, and Property AI
              Advisor are the 3 feature-strip entry points below them — Property AI Advisor is paid and
              tier-gated. Hiding any of these here only controls whether its homepage entry point (and
              sticker, for the feature strips) is shown, not who's actually entitled to use the feature.
            </p>
            {homepagePanelVisibility ? (
              <>
                {[
                  { key: "instant_property_score", label: "Instant Property Score (Free, No Signup)" },
                  { key: "hidden_deal", label: "Hidden Deal — What Did PropertyIQWeb Find? (Free)" },
                  { key: "red_flag_hunt", label: "Red Flag Hunt — Can You Spot the Red Flags? (Free)" },
                  { key: "challenge_a_friend", label: "Should I Buy This? — Challenge a Friend (Free)" },
                  { key: "price_drop_alert", label: "Price Drop Alert — Let PropertyIQWeb Watch For You (Free)" },
                  { key: "hottest_properties_ticker", label: "Hottest Properties ticker (below the logo)" },
                  { key: "construction_studio", label: "Construction Studio (feature strip)" },
                  { key: "agent_intelligence", label: "Agent Intelligence (feature strip)" },
                  { key: "property_ai_advisor", label: "Property AI Advisor (feature strip — tier-gated, not free)" },
                ].map(({ key, label }) => (
                  <div key={key} className="admin-toggle-row">
                    <label htmlFor={`homepage-toggle-${key}`}>{label}</label>
                    <label className="admin-switch" htmlFor={`homepage-toggle-${key}`}>
                      <input
                        id={`homepage-toggle-${key}`}
                        type="checkbox"
                        checked={!!homepagePanelVisibility[key]}
                        onChange={() => toggleHomepagePanel(key)}
                      />
                      <span className="admin-slider"></span>
                    </label>
                  </div>
                ))}
                <button className="cs-nav-btn cs-nav-primary" style={{ marginTop: 16 }} onClick={saveHomepagePanelVisibility} disabled={loading}>
                  {loading ? "Saving..." : "Save"}
                </button>
                {homepageVisibilitySaveMessage && <div className="studio-status-banner">{homepageVisibilitySaveMessage}</div>}
              </>
            ) : (
              <p className="admin-empty-note">Loading...</p>
            )}
          </div>

          <div className="admin-section">
            <h3>Homepage — Feature Strip Stickers</h3>
            <p className="admin-section-note">
              The small "excitement" badge pinned to the corner of each feature strip above — wording only;
              whether the strip (and its sticker) shows at all is still controlled by the toggles above.
              Leaving a field blank and saving keeps its current text rather than clearing the sticker.
            </p>
            {featureStickerText ? (
              <>
                {[
                  { key: "construction_studio", label: "Construction Studio" },
                  { key: "agent_intelligence", label: "Agent Intelligence" },
                  { key: "property_ai_advisor", label: "Property AI Advisor" },
                ].map(({ key, label }) => (
                  <div key={key} className="admin-toggle-row">
                    <label htmlFor={`sticker-text-${key}`}>{label}</label>
                    <input
                      id={`sticker-text-${key}`}
                      type="text"
                      value={featureStickerText[key] || ""}
                      onChange={(e) => updateStickerText(key, e.target.value)}
                      placeholder="e.g. 🔥 Save Big"
                      style={{ maxWidth: 220 }}
                    />
                  </div>
                ))}
                <button className="cs-nav-btn cs-nav-primary" style={{ marginTop: 16 }} onClick={saveFeatureStickerText} disabled={loading}>
                  {loading ? "Saving..." : "Save"}
                </button>
                {stickerSaveMessage && <div className="studio-status-banner">{stickerSaveMessage}</div>}
              </>
            ) : (
              <p className="admin-empty-note">Loading...</p>
            )}
          </div>
        </>
      )}

      {screen === "subscriptions" && (
        <>
          <button type="button" className="admin-subscreen-back" onClick={() => setScreen("menu")}>← Back to menu</button>

          <div className="admin-section admin-section-blue">
            <h3>Active Subscriptions ({subscriptions.length})</h3>
            {subscriptions.length === 0 ? (
              <p className="admin-empty-note">No subscriptions yet.</p>
            ) : (
              <div className="admin-table-scroll">
                <table className="admin-table">
                  <thead>
                    <tr><th>Email</th><th>Tier</th><th>Status</th><th>Updated</th></tr>
                  </thead>
                  <tbody>
                    {subscriptions.map((s) => (
                      <tr key={s.email}>
                        <td>{s.email}</td>
                        <td>{s.tier_id}</td>
                        <td>
                          <span className={`admin-status-badge ${s.status === "active" ? "admin-status-active" : "admin-status-other"}`}>
                            {s.status}
                          </span>
                        </td>
                        <td>{new Date(s.updated_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {screen === "grants" && (
        <>
          <button type="button" className="admin-subscreen-back" onClick={() => setScreen("menu")}>← Back to menu</button>

          <div className="admin-section admin-section-green">
            <h3>Quick Analysis Grants ({grants.length})</h3>
            {grants.length === 0 ? (
              <p className="admin-empty-note">No Insight purchases yet.</p>
            ) : (
              <div className="admin-table-scroll">
                <table className="admin-table">
                  <thead>
                    <tr><th>Report ID</th><th>Email</th><th>Granted</th></tr>
                  </thead>
                  <tbody>
                    {grants.map((g, i) => (
                      <tr key={i}>
                        <td>{g.report_id}</td>
                        <td>{g.user_email}</td>
                        <td>{new Date(g.granted_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {screen === "refunds" && (
        <>
          <button type="button" className="admin-subscreen-back" onClick={() => setScreen("menu")}>← Back to menu</button>

          {refundMessage && <div className="studio-status-banner">{refundMessage}</div>}

          <div className="admin-section admin-section-blue">
            <h3>Look up payments &amp; issue a refund</h3>
            <p className="admin-section-note">
              Works for subscription payments (Starter/Pro/Unlimited) by email — looked up directly from Dodo.
              For a one-time purchase (Quick Analysis, Standard Report), there's no subscription to look up by;
              paste the payment_id from Dodo's own dashboard into the manual section below instead.
            </p>
            <div className="admin-tier-row" style={{ gridTemplateColumns: "1fr auto" }}>
              <input
                type="email"
                placeholder="customer@example.com"
                value={refundLookupEmail}
                onChange={(e) => setRefundLookupEmail(e.target.value)}
              />
              <button className="cs-nav-btn cs-nav-primary" onClick={lookupPayments} disabled={loading || !refundLookupEmail.trim()}>
                {loading ? "Looking up..." : "Look up payments"}
              </button>
            </div>

            {refundPayments !== null && (
              refundPayments.length === 0 ? (
                <p className="admin-empty-note">{refundLookupNote || "No payments found for this email."}</p>
              ) : (
                <div className="admin-table-scroll" style={{ marginTop: 16 }}>
                  <table className="admin-table">
                    <thead>
                      <tr><th>Payment ID</th><th>Amount</th><th>Status</th><th>Refund status</th><th>Date</th><th></th></tr>
                    </thead>
                    <tbody>
                      {refundPayments.map((p) => (
                        <tr key={p.payment_id}>
                          <td>{p.payment_id}</td>
                          <td>${p.amount_usd} {p.currency?.toUpperCase()}</td>
                          <td>{p.status}</td>
                          <td>{p.refund_status || "—"}</td>
                          <td>{p.created_at ? new Date(p.created_at).toLocaleDateString() : "—"}</td>
                          <td>
                            {p.refund_status === "full" ? (
                              <span className="admin-empty-note">Already fully refunded</span>
                            ) : (
                              <button type="button" className="admin-feature-hide-btn" style={{ background: "#fdecea", borderColor: "#f5c6c1", color: "var(--red-600, #c0392b)" }} onClick={() => issueRefund(p.payment_id)} disabled={loading}>
                                Refund via Dodo
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            )}
          </div>

          <div className="admin-section admin-section-amber">
            <h3>Record a manual refund</h3>
            <p className="admin-section-note">
              For a refund handled OUTSIDE Dodo entirely — something Dodo missed, an expired card refunded by
              direct transfer, a goodwill refund done another way. This does not call Dodo or move any money —
              it's a record-keeping entry only, so refund history here stays complete.
            </p>
            <div className="admin-tier-row" style={{ gridTemplateColumns: "1.4fr 1fr 1fr" }}>
              <input type="email" placeholder="Customer email" value={manualRefundForm.email} onChange={(e) => setManualRefundForm({ ...manualRefundForm, email: e.target.value })} />
              <input type="number" placeholder="Amount" value={manualRefundForm.amount} onChange={(e) => setManualRefundForm({ ...manualRefundForm, amount: e.target.value })} />
              <input type="text" placeholder="Currency (e.g. USD)" value={manualRefundForm.currency} onChange={(e) => setManualRefundForm({ ...manualRefundForm, currency: e.target.value })} />
            </div>
            <div className="admin-tier-row" style={{ gridTemplateColumns: "1fr 1fr auto", marginTop: 8 }}>
              <input type="text" placeholder="Reason (e.g. duplicate charge)" value={manualRefundForm.reason} onChange={(e) => setManualRefundForm({ ...manualRefundForm, reason: e.target.value })} />
              <input type="text" placeholder="Admin note (how it was actually refunded)" value={manualRefundForm.note} onChange={(e) => setManualRefundForm({ ...manualRefundForm, note: e.target.value })} />
              <button className="cs-nav-btn cs-nav-primary" onClick={submitManualRefund} disabled={loading}>
                {loading ? "Recording..." : "Record"}
              </button>
            </div>
          </div>

          <div className="admin-section">
            <h3>Refund history ({refundHistory.length})</h3>
            {refundHistory.length === 0 ? (
              <p className="admin-empty-note">No refunds recorded yet.</p>
            ) : (
              <div className="admin-table-scroll">
                <table className="admin-table">
                  <thead>
                    <tr><th>Email</th><th>Amount</th><th>Reason</th><th>Status</th><th>Source</th><th>Date</th></tr>
                  </thead>
                  <tbody>
                    {refundHistory.map((r) => (
                      <tr key={r.id}>
                        <td>{r.user_email}</td>
                        <td>{r.amount_usd != null ? `$${r.amount_usd} ${(r.currency || "").toUpperCase()}` : "—"}</td>
                        <td>{r.reason || r.admin_note || "—"}</td>
                        <td>
                          <span className={`admin-status-badge ${r.status === "succeeded" ? "admin-status-active" : "admin-status-other"}`}>
                            {r.status}
                          </span>
                        </td>
                        <td>{r.is_manual ? "Manual" : "Dodo"}</td>
                        <td>{new Date(r.created_at).toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {screen === "refund-requests" && (
        <>
          <button type="button" className="admin-subscreen-back" onClick={() => setScreen("menu")}>← Back to menu</button>

          {refundRequestsMessage && <div className="studio-status-banner">{refundRequestsMessage}</div>}

          <div className="admin-section admin-section-amber">
            <h3>Refund Requests ({refundRequests.length})</h3>
            <p className="admin-section-note">
              Requests customers have actually submitted, each tied to a real policy scenario. Approving
              one either issues a real refund via Dodo or records a manual entry — the same fulfillment
              this screen's sibling "Refunds" tile already uses, just started from a real request instead
              of an ad-hoc lookup.
            </p>
            <div className="admin-tier-features-row" style={{ marginBottom: 16 }}>
              <span className="admin-tier-features-label">Filter:</span>
              {["pending", "approved", "denied"].map((s) => (
                <button
                  key={s}
                  type="button"
                  className="admin-feature-hide-btn"
                  style={
                    refundRequestsFilter === s
                      ? { background: "#14283d", borderColor: "#14283d", color: "white" }
                      : { background: "white", borderColor: "var(--grey-200, #d6e4ec)", color: "var(--grey-600, #5b6f7c)" }
                  }
                  onClick={() => setRefundRequestsFilter(s)}
                >
                  {s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              ))}
            </div>

            {refundRequests.length === 0 ? (
              <p className="admin-empty-note">No {refundRequestsFilter} requests.</p>
            ) : (
              refundRequests.map((req) => {
                const isOpen = expandedRequestId === req.id;
                const form = decisionForms[req.id] || {};
                return (
                  <div key={req.id} className="admin-section" style={{ marginBottom: 12, padding: 16 }}>
                    <div
                      style={{ display: "flex", justifyContent: "space-between", alignItems: "center", cursor: "pointer" }}
                      onClick={() => setExpandedRequestId(isOpen ? null : req.id)}
                    >
                      <div>
                        <strong>{req.user_email}</strong>
                        {" — "}
                        {REFUND_REASON_LABELS[req.reason_code] || req.reason_code}
                        <span
                          className={`admin-status-badge ${req.status === "approved" ? "admin-status-active" : "admin-status-other"}`}
                          style={{ marginLeft: 10 }}
                        >
                          {req.status}
                        </span>
                      </div>
                      <span className="admin-empty-note">{new Date(req.created_at).toLocaleString()}</span>
                    </div>

                    {isOpen && (
                      <div style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--grey-100, #ebf5fb)" }}>
                        {req.purchase_reference && <p><strong>Purchase reference:</strong> {req.purchase_reference}</p>}
                        {req.details && <p><strong>Customer's notes:</strong> {req.details}</p>}
                        {req.reason_code === "first_month_guarantee" && (
                          <div className="terms-gate-body" style={{
                            background: req.already_used_guarantee_before ? "#fdecea" : "#f7f9fb",
                            padding: 10, borderRadius: 8, marginBottom: 10,
                          }}>
                            <strong>Usage this month:</strong> {req.designs_generated_this_month} design{req.designs_generated_this_month === 1 ? "" : "s"} generated.
                            {req.already_used_guarantee_before && (
                              <> <strong style={{ color: "#c0392b" }}>This customer has already used the first-month guarantee before — approving here will be blocked.</strong></>
                            )}
                          </div>
                        )}
                        {req.admin_response && <p><strong>Admin response:</strong> {req.admin_response}</p>}

                        {req.status === "pending" && (
                          <>
                            <div className="admin-tier-row" style={{ gridTemplateColumns: "1fr 1fr", marginTop: 10 }}>
                              <input
                                type="text"
                                placeholder="Dodo payment_id (to refund via Dodo)"
                                value={form.paymentId || ""}
                                onChange={(e) => updateDecisionForm(req.id, { paymentId: e.target.value })}
                              />
                              <button className="cs-nav-btn cs-nav-primary" onClick={() => approveViaDodo(req.id)} disabled={loading}>
                                Approve &amp; Refund via Dodo
                              </button>
                            </div>
                            <div className="admin-tier-row" style={{ gridTemplateColumns: "1fr 1fr 1fr", marginTop: 8 }}>
                              <input
                                type="number"
                                placeholder="Amount"
                                value={form.amount || ""}
                                onChange={(e) => updateDecisionForm(req.id, { amount: e.target.value })}
                              />
                              <input
                                type="text"
                                placeholder="How it was actually refunded"
                                value={form.note || ""}
                                onChange={(e) => updateDecisionForm(req.id, { note: e.target.value })}
                              />
                              <button className="cs-nav-btn cs-nav-primary" onClick={() => approveManually(req.id)} disabled={loading}>
                                Approve &amp; Record Manual
                              </button>
                            </div>
                            <div className="admin-tier-row" style={{ gridTemplateColumns: "1fr auto", marginTop: 8 }}>
                              <input
                                type="text"
                                placeholder="Response shown to the customer (required to deny; optional note on approval)"
                                value={form.response || ""}
                                onChange={(e) => updateDecisionForm(req.id, { response: e.target.value })}
                              />
                              <button
                                type="button"
                                className="admin-feature-hide-btn"
                                onClick={() => denyRequest(req.id)}
                                disabled={loading}
                              >
                                Deny
                              </button>
                            </div>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </>
      )}

      {screen === "manual" && (
        <>
          <button type="button" className="admin-subscreen-back" onClick={() => setScreen("menu")}>← Back to menu</button>
          <AdminManual password={password} />
        </>
      )}

      {screen === "reset-quota" && (
        <>
          <button type="button" className="admin-subscreen-back" onClick={() => setScreen("menu")}>← Back to menu</button>

          {quotaMessage && <div className="studio-status-banner">{quotaMessage}</div>}

          <div className="admin-section admin-section-purple">
            <h3>Reset User Quota</h3>
            <p className="admin-section-note">
              Gives a user a fresh monthly design-generate quota immediately, without waiting for the
              calendar month to roll over — for a real support case (a bug consumed their quota, a
              confusing moment in the product). This never deletes or touches their design history — only
              what counts against this month's limit changes, from this moment forward.
            </p>
            <div className="admin-tier-row" style={{ gridTemplateColumns: "1fr auto" }}>
              <input
                type="email"
                placeholder="customer@example.com"
                value={quotaLookupEmail}
                onChange={(e) => setQuotaLookupEmail(e.target.value)}
              />
              <button className="cs-nav-btn cs-nav-primary" onClick={lookupQuota} disabled={loading || !quotaLookupEmail.trim()}>
                {loading ? "Looking up..." : "Look up"}
              </button>
            </div>

            {quotaInfo && (
              <>
                <table className="admin-table" style={{ marginTop: 16 }}>
                  <tbody>
                    <tr><td>Tier</td><td style={{ textAlign: "right" }}>{quotaInfo.tier_id || "No active plan"}</td></tr>
                    <tr><td>Monthly quota</td><td style={{ textAlign: "right" }}>{quotaInfo.design_quota_per_month ?? "Unlimited"}</td></tr>
                    <tr><td>Used this month</td><td style={{ textAlign: "right" }}><strong>{quotaInfo.designs_used_this_month}</strong></td></tr>
                    <tr><td>Last admin reset</td><td style={{ textAlign: "right" }}>{quotaInfo.last_reset_at ? new Date(quotaInfo.last_reset_at).toLocaleString() : "Never"}</td></tr>
                  </tbody>
                </table>

                <div className="admin-tier-row" style={{ gridTemplateColumns: "1fr auto", marginTop: 12 }}>
                  <input
                    type="text"
                    placeholder="Note (e.g. reason for the reset)"
                    value={quotaResetNote}
                    onChange={(e) => setQuotaResetNote(e.target.value)}
                  />
                  <button className="cs-nav-btn cs-nav-primary" onClick={resetQuota} disabled={loading}>
                    Reset Quota
                  </button>
                </div>
              </>
            )}
          </div>
        </>
      )}

      <span className="studio-back-link" onClick={onBack}>← Back to site</span>
    </div>
  );
}

export default AdminPanel;
