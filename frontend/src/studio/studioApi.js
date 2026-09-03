const API_BASE = "https://propertyiq-api-q21y.onrender.com";

const SESSION_KEY = "propertyiq_studio_session";

export function getSession() {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function saveSession(token, email) {
  localStorage.setItem(SESSION_KEY, JSON.stringify({ token, email }));
}

export function clearSession() {
  localStorage.removeItem(SESSION_KEY);
}

function authHeaders() {
  const session = getSession();
  return session?.token ? { Authorization: `Bearer ${session.token}` } : {};
}

async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });

  let data = null;
  try {
    data = await response.json();
  } catch {
    // no body
  }

  if (!response.ok) {
    const message = data?.detail || `Request failed (${response.status})`;
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }

  return data;
}

export const studioApi = {
  requestOtp: (email) =>
    apiFetch("/api/auth/request-otp", { method: "POST", body: JSON.stringify({ email }) }),

  verifyOtp: (email, code) =>
    apiFetch("/api/auth/verify-otp", { method: "POST", body: JSON.stringify({ email, code }) }),

  getTiers: () => apiFetch("/api/tiers"),

  getFxRates: () => apiFetch("/api/fx-rates"),

  getStatus: () => apiFetch("/api/subscribe/status"),

  subscribeCheckout: (tierId) =>
    apiFetch("/api/subscribe/checkout", { method: "POST", body: JSON.stringify({ tier_id: tierId }) }),

  insightCheckout: (reportId) =>
    apiFetch("/api/insight/checkout", { method: "POST", body: JSON.stringify({ report_id: reportId }) }),

  getSimilarProperties: (reportId, { city, propertyType, subjectPricePerSqft }) =>
    apiFetch(
      `/api/similar-properties/${encodeURIComponent(reportId)}?city=${encodeURIComponent(city)}` +
        `&property_type=${encodeURIComponent(propertyType)}&subject_price_per_sqft=${subjectPricePerSqft || 0}`
    ),

  createConstructionDesign: (payload) =>
    apiFetch("/api/construction-studio/design", { method: "POST", body: JSON.stringify(payload) }),

  getMaterials: (region) => apiFetch(`/api/construction-studio/materials?region=${encodeURIComponent(region)}`),

  estimateCost: (payload) =>
    apiFetch("/api/construction-studio/estimate", { method: "POST", body: JSON.stringify(payload) }),

  getBillOfMaterials: (payload) =>
    apiFetch("/api/construction-studio/bill-of-materials", { method: "POST", body: JSON.stringify(payload) }),

  checkVastu: (payload) =>
    apiFetch("/api/construction-studio/vastu-check", { method: "POST", body: JSON.stringify(payload) }),

  checkAdjacency: (payload) =>
    apiFetch("/api/construction-studio/adjacency-check", { method: "POST", body: JSON.stringify(payload) }),

  getBillOfQuantities: (payload) =>
    apiFetch("/api/construction-studio/bill-of-quantities", { method: "POST", body: JSON.stringify(payload) }),

  adminOverview: (password, forceRefreshPrices = false) =>
    apiFetch("/api/admin/overview", { method: "POST", body: JSON.stringify({ password, force_refresh_prices: forceRefreshPrices }) }),

  adminUpdateTiers: (password, tierConfig) =>
    apiFetch("/api/admin/tiers", { method: "POST", body: JSON.stringify({ password, tier_config: tierConfig }) }),

  adminUpdateSettings: (password, geminiApiKey, niSectionVisibility) =>
    apiFetch("/api/admin/settings", { method: "POST", body: JSON.stringify({ password, gemini_api_key: geminiApiKey, ni_section_visibility: niSectionVisibility }) }),

  adminLookupPayments: (password, email) =>
    apiFetch("/api/admin/payments", { method: "POST", body: JSON.stringify({ password, email }) }),

  adminIssueRefund: (password, paymentId, userEmail, reason) =>
    apiFetch("/api/admin/refunds", { method: "POST", body: JSON.stringify({ password, payment_id: paymentId, user_email: userEmail, reason }) }),

  adminRecordManualRefund: (password, userEmail, amountUsd, currency, reason, adminNote) =>
    apiFetch("/api/admin/refunds/manual", { method: "POST", body: JSON.stringify({ password, user_email: userEmail, amount_usd: amountUsd, currency, reason, admin_note: adminNote }) }),

  adminListRefunds: (password) =>
    apiFetch("/api/admin/refunds/list", { method: "POST", body: JSON.stringify({ password }) }),

  submitRefundRequest: (userEmail, reasonCode, details, purchaseReference) =>
    apiFetch("/api/refund-requests", { method: "POST", body: JSON.stringify({ user_email: userEmail, reason_code: reasonCode, details, purchase_reference: purchaseReference }) }),

  checkRefundRequestStatus: (requestId, userEmail) =>
    apiFetch("/api/refund-requests/status", { method: "POST", body: JSON.stringify({ request_id: requestId, user_email: userEmail }) }),

  adminListRefundRequests: (password, status) =>
    apiFetch("/api/admin/refund-requests/list", { method: "POST", body: JSON.stringify({ password, status }) }),

  adminApproveRefundRequestViaDodo: (password, requestId, paymentId, adminResponse) =>
    apiFetch("/api/admin/refund-requests/approve-dodo", { method: "POST", body: JSON.stringify({ password, request_id: requestId, payment_id: paymentId, admin_response: adminResponse }) }),

  adminApproveRefundRequestManually: (password, requestId, amountUsd, currency, adminNote, adminResponse) =>
    apiFetch("/api/admin/refund-requests/approve-manual", { method: "POST", body: JSON.stringify({ password, request_id: requestId, amount_usd: amountUsd, currency, admin_note: adminNote, admin_response: adminResponse }) }),

  adminDenyRefundRequest: (password, requestId, adminResponse) =>
    apiFetch("/api/admin/refund-requests/deny", { method: "POST", body: JSON.stringify({ password, request_id: requestId, admin_response: adminResponse }) }),

  adminLookupQuota: (password, userEmail) =>
    apiFetch("/api/admin/quota-lookup", { method: "POST", body: JSON.stringify({ password, user_email: userEmail }) }),

  adminResetQuota: (password, userEmail, adminNote) =>
    apiFetch("/api/admin/reset-quota", { method: "POST", body: JSON.stringify({ password, user_email: userEmail, admin_note: adminNote }) }),

  listProperties: () => apiFetch("/api/properties"),

  getProperty: (propertyId) => apiFetch(`/api/properties/${encodeURIComponent(propertyId)}`),

  createProperty: (payload) =>
    apiFetch("/api/properties", { method: "POST", body: JSON.stringify(payload) }),

  updateProperty: (propertyId, payload) =>
    apiFetch(`/api/properties/${encodeURIComponent(propertyId)}`, { method: "PUT", body: JSON.stringify(payload) }),

  upsertFloor: (propertyId, payload) =>
    apiFetch(`/api/properties/${encodeURIComponent(propertyId)}/floors`, { method: "PUT", body: JSON.stringify(payload) }),

  syncProperty: (propertyId, payload) =>
    apiFetch(`/api/properties/${encodeURIComponent(propertyId)}/sync`, { method: "PUT", body: JSON.stringify(payload) }),

  deleteFloor: (propertyId, floorId) =>
    apiFetch(`/api/properties/${encodeURIComponent(propertyId)}/floors/${encodeURIComponent(floorId)}`, { method: "DELETE" }),

  lockProperty: (propertyId) =>
    apiFetch(`/api/properties/${encodeURIComponent(propertyId)}/lock`, { method: "POST" }),

  requestUnlock: (propertyId) =>
    apiFetch(`/api/properties/${encodeURIComponent(propertyId)}/request-unlock`, { method: "POST" }),

  confirmUnlock: (propertyId, code) =>
    apiFetch(`/api/properties/${encodeURIComponent(propertyId)}/confirm-unlock`, { method: "POST", body: JSON.stringify({ code }) }),

  deleteProperty: (propertyId) =>
    apiFetch(`/api/properties/${encodeURIComponent(propertyId)}`, { method: "DELETE" }),

  getOrderStatus: (orderId) =>
    apiFetch(`/api/orders/${encodeURIComponent(orderId)}/status`),

  getInsightStatus: (reportId) =>
    apiFetch(`/api/insight/status/${encodeURIComponent(reportId)}`),

  extractFromUrl: (url) =>
    apiFetch("/api/property/extract-from-url", { method: "POST", body: JSON.stringify({ url }) }),

  getInstantScore: (price, city, propertyType, areaValue, areaUnit, location) =>
    apiFetch("/api/instant-score", {
      method: "POST",
      body: JSON.stringify({ price, city, property_type: propertyType, area_value: areaValue, area_unit: areaUnit, location: location || null }),
    }),

  getHiddenDeal: (price, city, propertyType, areaValue, areaUnit, location) =>
    apiFetch("/api/hidden-deal", {
      method: "POST",
      body: JSON.stringify({ price, city, property_type: propertyType, area_value: areaValue, area_unit: areaUnit, location: location || null }),
    }),

  getRedFlagVerdict: (price, city, propertyType, areaValue, areaUnit, guessedCategory, location) =>
    apiFetch("/api/red-flag-hunt", {
      method: "POST",
      body: JSON.stringify({
        price, city, property_type: propertyType, area_value: areaValue, area_unit: areaUnit,
        guessed_category: guessedCategory, location: location || null,
      }),
    }),

  createChallenge: (price, city, propertyType, areaValue, areaUnit, location) =>
    apiFetch("/api/challenges", {
      method: "POST",
      body: JSON.stringify({ price, city, property_type: propertyType, area_value: areaValue, area_unit: areaUnit, location: location || null }),
    }),

  getChallenge: (challengeId) =>
    apiFetch(`/api/challenges/${encodeURIComponent(challengeId)}`),

  guessChallenge: (challengeId, guessedPrice) =>
    apiFetch(`/api/challenges/${encodeURIComponent(challengeId)}/guess`, {
      method: "POST",
      body: JSON.stringify({ guessed_price: guessedPrice }),
    }),

  createPriceWatch: (price, city, propertyType, areaValue, targetPrice, areaUnit, url, location) =>
    apiFetch("/api/price-watches", {
      method: "POST",
      body: JSON.stringify({
        price, city, property_type: propertyType, area_value: areaValue,
        target_price: targetPrice, area_unit: areaUnit, url: url || null, location: location || null,
      }),
    }),

  getPriceWatch: (watchId) =>
    apiFetch(`/api/price-watches/${encodeURIComponent(watchId)}`),

  updateWatchPrice: (watchId, newPrice) =>
    apiFetch(`/api/price-watches/${encodeURIComponent(watchId)}/update-price`, {
      method: "POST",
      body: JSON.stringify({ new_price: newPrice }),
    }),

  getComplianceRules: (tradition) =>
    apiFetch(`/api/construction-studio/compliance-rules?tradition=${encodeURIComponent(tradition)}`),

  getDisciplineOverlay: (discipline, rooms, plotLengthFt, plotWidthFt, totalFloors) =>
    apiFetch(`/api/construction-studio/discipline-overlay?discipline=${encodeURIComponent(discipline)}`, {
      method: "POST",
      body: JSON.stringify({ rooms, plot_length_ft: plotLengthFt, plot_width_ft: plotWidthFt, total_floors: totalFloors }),
    }),

  // Deliberately NOT built on apiFetch: apiFetch always calls
  // response.json(), which would corrupt this endpoint's actual PDF
  // bytes. Fetches the PDF as a blob and triggers a real browser
  // download via a temporary <a> tag + object URL, the standard
  // pattern for a fetch-based (rather than plain-link) file download —
  // needed here because the request has a JSON body (floors) a plain
  // <a href> download can't send.
  downloadConstructionReport: async (designId, floors, propertyName) => {
    const response = await fetch(`${API_BASE}/api/construction-studio/design/${encodeURIComponent(designId)}/report`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ floors, property_name: propertyName || "" }),
    });

    if (!response.ok) {
      let message = `Request failed (${response.status})`;
      try {
        const errorBody = await response.json();
        message = errorBody?.detail || message;
      } catch {
        // error response wasn't JSON either — fall back to the generic message
      }
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `PropertyIQ_ConstructionStudio_Report_${designId}.pdf`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  },
};
