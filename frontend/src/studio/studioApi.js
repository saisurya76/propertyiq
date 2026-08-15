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
};
