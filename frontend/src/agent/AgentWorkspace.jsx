import { useEffect, useRef, useState } from "react";
import { studioApi, getSession } from "../studio/studioApi";

const API_BASE = "https://propertyiq-api-q21y.onrender.com";

function emptyPropertyForm() {
  return {
    country: "India", stateProvince: "Telangana", city: "", location: "",
    propertyType: "Apartment", propertyName: "", developerName: "",
    quotedPrice: "", governmentGuidance: "", marketAverage: "", unitArea: "",
    monthlyRent: "0", areaUnit: "sqft", lat: null, lon: null,
    addressQuery: "",
  };
}

function propertyPayloadToForm(payload, lat, lon) {
  return {
    ...emptyPropertyForm(),
    ...payload,
    quotedPrice: String(payload.quotedPrice ?? ""),
    governmentGuidance: String(payload.governmentGuidance ?? ""),
    marketAverage: String(payload.marketAverage ?? ""),
    unitArea: String(payload.unitArea ?? ""),
    monthlyRent: String(payload.monthlyRent ?? "0"),
    lat, lon,
    addressQuery: `${payload.location || ""}, ${payload.city || ""}`.trim(),
  };
}

function formatPrice(usdAmount, currency, fxRates) {
  const rate = fxRates?.[currency] || 1;
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 0 }).format(usdAmount * rate);
  } catch {
    return `$${usdAmount}`;
  }
}

function AgentWorkspace({ onBack, currency }) {
  const [view, setView] = useState("dashboard"); // "dashboard" | "workspace"
  const [clients, setClients] = useState(null);
  const [propertiesByClient, setPropertiesByClient] = useState({});
  const [expandedClientId, setExpandedClientId] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const [authStep, setAuthStep] = useState(null); // null | "paywall"
  const [paywallTiers, setPaywallTiers] = useState(null);

  const [showAddClient, setShowAddClient] = useState(false);
  const [editingClientId, setEditingClientId] = useState(null); // client_id being edited, or null for "add new"
  const [clientNameInput, setClientNameInput] = useState("");
  const [clientContactInput, setClientContactInput] = useState("");

  const [propertyFormFor, setPropertyFormFor] = useState(null); // { clientId, propertyId | null } — propertyId set means "editing", null means "adding new"
  const [propertyForm, setPropertyForm] = useState(emptyPropertyForm());
  const [addressSuggestions, setAddressSuggestions] = useState([]);
  const debounceRef = useRef(null);

  const [generatingReportFor, setGeneratingReportFor] = useState(null);

  const loadPaywallTiers = () => {
    if (paywallTiers !== null) return;
    Promise.all([
      fetch(`${API_BASE}/api/tiers`).then((r) => r.json()),
      fetch(`${API_BASE}/api/fx-rates`).then((r) => r.json()),
    ])
      .then(([tiers, fxRates]) => {
        const qualifying = Object.entries(tiers)
          .filter(([, tier]) => (tier.features || []).includes("agent_intelligence"))
          .map(([tierId, tier]) => ({ tierId, ...tier }));
        setPaywallTiers({ tiers: qualifying, fxRates });
      })
      .catch(() => setPaywallTiers({ tiers: [], fxRates: {} }));
  };

  // The initial load stays a plain, direct fetch call (no synchronous
  // setState calls inside the effect body itself) — same established
  // pattern as StudioDesigns.jsx's fetchProperties/handleRefreshClick
  // split.
  const fetchClients = () =>
    studioApi.agentListClients()
      .then((res) => setClients(res.clients))
      .catch((err) => {
        if (err.status === 403) {
          loadPaywallTiers();
          setAuthStep("paywall");
        } else {
          setError(err.message || "Couldn't load your clients.");
        }
      });

  const loadClients = () => {
    setError("");
    setLoading(true);
    return fetchClients().finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchClients();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openAddClient = () => {
    setEditingClientId(null);
    setClientNameInput("");
    setClientContactInput("");
    setShowAddClient(true);
  };

  const openEditClient = (client) => {
    setEditingClientId(client.client_id);
    setClientNameInput(client.client_name);
    setClientContactInput(client.client_contact || "");
    setShowAddClient(true);
  };

  const handleSaveClient = async (e) => {
    e.preventDefault();
    if (!clientNameInput.trim()) return;
    setError("");
    try {
      if (editingClientId) {
        await studioApi.agentUpdateClient(editingClientId, clientNameInput.trim(), clientContactInput.trim() || null);
      } else {
        await studioApi.agentCreateClient(clientNameInput.trim(), clientContactInput.trim() || null);
      }
      setShowAddClient(false);
      setEditingClientId(null);
      await loadClients();
    } catch (err) {
      setError(err.message || "Couldn't save this client.");
    }
  };

  const handleDeleteClient = async (clientId) => {
    if (!window.confirm("Delete this client and all their properties? This can't be undone.")) return;
    setError("");
    try {
      await studioApi.agentDeleteClient(clientId);
      await loadClients();
    } catch (err) {
      setError(err.message || "Couldn't delete this client.");
    }
  };

  const toggleExpandClient = async (clientId) => {
    if (expandedClientId === clientId) {
      setExpandedClientId(null);
      return;
    }
    setExpandedClientId(clientId);
    if (!propertiesByClient[clientId]) {
      try {
        const res = await studioApi.agentListClientProperties(clientId);
        setPropertiesByClient((prev) => ({ ...prev, [clientId]: res.properties }));
      } catch (err) {
        setError(err.message || "Couldn't load properties for this client.");
      }
    }
  };

  // Same real autocomplete this app's Neighborhood Insights page
  // already uses (LocationIQ, via the same backend proxy endpoint) —
  // needed so a client property actually gets real coordinates, which
  // its neighborhood/cost-of-living/report sections all depend on.
  const handleAddressInput = (value) => {
    setPropertyForm((prev) => ({ ...prev, addressQuery: value, lat: null, lon: null }));
    clearTimeout(debounceRef.current);
    if (value.trim().length < 3) {
      setAddressSuggestions([]);
      return;
    }
    debounceRef.current = setTimeout(() => {
      const isoCode = { India: "in", Thailand: "th", Philippines: "ph", Vietnam: "vn", Indonesia: "id" }[propertyForm.country] || "in";
      fetch(`${API_BASE}/api/neighborhood-insights/autocomplete?q=${encodeURIComponent(value)}&country=${isoCode}`)
        .then((res) => res.json())
        .then((data) => setAddressSuggestions(Array.isArray(data) ? data : []))
        .catch(() => setAddressSuggestions([]));
    }, 300);
  };

  const selectAddressSuggestion = (item) => {
    const label = item.display_name || item.display_place || propertyForm.addressQuery;
    setPropertyForm((prev) => ({
      ...prev,
      addressQuery: label,
      location: label,
      city: item.address?.city || item.address?.town || item.address?.village || prev.city,
      lat: parseFloat(item.lat),
      lon: parseFloat(item.lon),
    }));
    setAddressSuggestions([]);
  };

  const openAddProperty = (clientId) => {
    setPropertyFormFor({ clientId, propertyId: null });
    setPropertyForm(emptyPropertyForm());
    setAddressSuggestions([]);
  };

  const openEditProperty = (clientId, prop) => {
    setPropertyFormFor({ clientId, propertyId: prop.property_id });
    setPropertyForm(propertyPayloadToForm(prop.property_payload, prop.lat, prop.lon));
    setAddressSuggestions([]);
  };

  const handleSaveProperty = async (e) => {
    e.preventDefault();
    setError("");
    const { addressQuery, ...rest } = propertyForm;
    void addressQuery;
    const payload = {
      ...rest,
      quotedPrice: parseFloat(propertyForm.quotedPrice) || 0,
      governmentGuidance: parseFloat(propertyForm.governmentGuidance) || 0,
      marketAverage: parseFloat(propertyForm.marketAverage) || 0,
      unitArea: parseFloat(propertyForm.unitArea) || 0,
      monthlyRent: parseFloat(propertyForm.monthlyRent) || 0,
      lat: propertyForm.lat,
      lon: propertyForm.lon,
    };
    try {
      if (propertyFormFor.propertyId) {
        await studioApi.agentUpdateClientProperty(propertyFormFor.propertyId, payload);
      } else {
        await studioApi.agentCreateClientProperty(propertyFormFor.clientId, payload);
      }
      const clientId = propertyFormFor.clientId;
      setPropertyFormFor(null);
      const res = await studioApi.agentListClientProperties(clientId);
      setPropertiesByClient((prev) => ({ ...prev, [clientId]: res.properties }));
    } catch (err) {
      setError(err.message || "Couldn't save this property.");
    }
  };

  const handleDeleteProperty = async (clientId, propertyId) => {
    if (!window.confirm("Delete this property?")) return;
    setError("");
    try {
      await studioApi.agentDeleteClientProperty(propertyId);
      const res = await studioApi.agentListClientProperties(clientId);
      setPropertiesByClient((prev) => ({ ...prev, [clientId]: res.properties }));
    } catch (err) {
      setError(err.message || "Couldn't delete this property.");
    }
  };

  const handleGenerateReport = async (propertyId) => {
    setGeneratingReportFor(propertyId);
    setError("");
    try {
      const session = getSession();
      const res = await fetch(`${API_BASE}/api/agent/properties/${propertyId}/generate-report`, {
        method: "POST",
        headers: session?.token ? { Authorization: `Bearer ${session.token}` } : {},
      });
      if (!res.ok) throw new Error("Couldn't generate the report.");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `advisory_report_${propertyId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message || "Couldn't generate the report right now.");
    } finally {
      setGeneratingReportFor(null);
    }
  };

  const totalProperties = Object.values(propertiesByClient).reduce((sum, list) => sum + list.length, 0);

  return (
    <div className="agent-workspace">
      <div className="agent-hero">
        <div className="agent-hero-inner">
          <button type="button" className="agent-back-link" onClick={onBack}>← Back to PropertyIQ</button>
          <h1>Agent Intelligence</h1>
          <p className="agent-hero-tagline">Analyze <span className="agent-arrow">→</span> Advise <span className="agent-arrow">→</span> Monetize</p>
        </div>
      </div>

      <div className="agent-content">
        {error && <div className="agent-error-banner">{error}</div>}

        {authStep === "paywall" && (
          <div className="agent-paywall">
            <h3>Unlock Agent Intelligence</h3>
            <p>This is a Studio subscriber feature. Here's what you'd get with each plan that includes it:</p>
            {!paywallTiers && <p>Loading plans...</p>}
            {paywallTiers && paywallTiers.tiers.length === 0 && (
              <p>No current plan includes this yet — check back soon, or contact support.</p>
            )}
            {paywallTiers && paywallTiers.tiers.length > 0 && (
              <div className="agent-tier-cards">
                {paywallTiers.tiers.map((tier) => (
                  <div key={tier.tierId} className="agent-tier-card">
                    <h4>{tier.label}</h4>
                    <div className="agent-tier-price">{formatPrice(tier.price_usd, currency, paywallTiers.fxRates)}<span>/mo</span></div>
                    <div className="agent-tier-quota">
                      {tier.max_agent_clients == null ? "Unlimited" : tier.max_agent_clients} clients ·{" "}
                      {tier.max_properties_per_client == null ? "unlimited" : tier.max_properties_per_client} properties each
                    </div>
                  </div>
                ))}
              </div>
            )}
            <a href="https://app.propertyiqweb.com/?view=pricing" target="_blank" rel="noopener noreferrer" className="agent-primary-btn">
              View Studio plans →
            </a>
          </div>
        )}

        {authStep !== "paywall" && (
          <>
            {view === "dashboard" && (
              <div className="agent-dashboard">
                <div className="agent-stat-cards">
                  <div className="agent-stat-card">
                    <div className="agent-stat-number">{clients ? clients.length : "—"}</div>
                    <div className="agent-stat-label">Clients</div>
                  </div>
                  <div className="agent-stat-card">
                    <div className="agent-stat-number">{totalProperties}</div>
                    <div className="agent-stat-label">Properties tracked</div>
                  </div>
                  <div className="agent-stat-card agent-stat-card-accent">
                    <div className="agent-stat-number">📊</div>
                    <div className="agent-stat-label">Consolidated advisory reports, ready to generate</div>
                  </div>
                </div>
                <button type="button" className="agent-primary-btn agent-enter-workspace-btn" onClick={() => setView("workspace")}>
                  Go to Workspace →
                </button>
              </div>
            )}

            {view === "workspace" && (
              <div className="agent-workspace-body">
                <div className="agent-workspace-header">
                  <button type="button" className="agent-back-link" onClick={() => setView("dashboard")}>← Dashboard</button>
                  <button type="button" className="agent-primary-btn" onClick={openAddClient}>
                    + Add Client
                  </button>
                </div>

                {showAddClient && (
                  <form className="agent-add-client-form" onSubmit={handleSaveClient}>
                    <input type="text" placeholder="Client name" value={clientNameInput} onChange={(e) => setClientNameInput(e.target.value)} required autoFocus />
                    <input type="text" placeholder="Contact (email or phone, optional)" value={clientContactInput} onChange={(e) => setClientContactInput(e.target.value)} />
                    <button type="submit" className="agent-primary-btn">{editingClientId ? "Save Changes" : "Save Client"}</button>
                    <button type="button" className="agent-text-btn" onClick={() => { setShowAddClient(false); setEditingClientId(null); }}>Cancel</button>
                  </form>
                )}

                {loading && <p>Loading...</p>}

                {clients && clients.length === 0 && !loading && (
                  <p className="agent-empty-note">No clients yet — add your first one above.</p>
                )}

                <div className="agent-client-list">
                  {clients && clients.map((c) => (
                    <div key={c.client_id} className="agent-client-card">
                      <div className="agent-client-card-header" onClick={() => toggleExpandClient(c.client_id)}>
                        <div>
                          <strong>{c.client_name}</strong>
                          {c.client_contact && <span className="agent-client-contact"> · {c.client_contact}</span>}
                        </div>
                        <div className="agent-client-card-actions">
                          <button type="button" className="agent-text-btn" onClick={(e) => { e.stopPropagation(); openEditClient(c); }}>
                            Edit
                          </button>
                          <button type="button" className="agent-text-btn agent-delete-btn" onClick={(e) => { e.stopPropagation(); handleDeleteClient(c.client_id); }}>
                            Delete
                          </button>
                          <span className="agent-expand-caret">{expandedClientId === c.client_id ? "▲" : "▼"}</span>
                        </div>
                      </div>

                      {expandedClientId === c.client_id && (
                        <div className="agent-client-properties">
                          {(propertiesByClient[c.client_id] || []).map((p) => (
                            <div key={p.property_id} className="agent-property-row">
                              <div>
                                <strong>{p.property_payload.propertyName}</strong>
                                <div className="agent-property-meta">{p.property_payload.location}, {p.property_payload.city}{p.lat == null && <span className="agent-no-coords-note"> · no coordinates yet</span>}</div>
                              </div>
                              <div className="agent-property-actions">
                                <button
                                  type="button"
                                  className="agent-primary-btn agent-small-btn"
                                  onClick={() => handleGenerateReport(p.property_id)}
                                  disabled={generatingReportFor === p.property_id}
                                >
                                  {generatingReportFor === p.property_id ? "Generating..." : "📄 Generate Report"}
                                </button>
                                <button type="button" className="agent-text-btn" onClick={() => openEditProperty(c.client_id, p)}>Edit</button>
                                <button type="button" className="agent-text-btn agent-delete-btn" onClick={() => handleDeleteProperty(c.client_id, p.property_id)}>
                                  Delete
                                </button>
                              </div>
                            </div>
                          ))}

                          {propertyFormFor && propertyFormFor.clientId === c.client_id ? (
                            <form className="agent-add-property-form" onSubmit={handleSaveProperty}>
                              <div className="agent-address-autocomplete">
                                <input
                                  type="text"
                                  placeholder="Search address — locality, city (enables neighborhood data automatically)"
                                  value={propertyForm.addressQuery}
                                  onChange={(e) => handleAddressInput(e.target.value)}
                                />
                                {addressSuggestions.length > 0 && (
                                  <div className="agent-address-suggestions">
                                    {addressSuggestions.map((item, i) => (
                                      <div key={i} className="agent-address-suggestion-item" onClick={() => selectAddressSuggestion(item)}>
                                        {item.display_name || item.display_place}
                                      </div>
                                    ))}
                                  </div>
                                )}
                                {propertyForm.lat != null && (
                                  <p className="agent-coords-confirm">✓ Location captured — neighborhood data will be included in the report.</p>
                                )}
                              </div>
                              <div className="agent-form-grid">
                                <input type="text" placeholder="Property name" value={propertyForm.propertyName} onChange={(e) => setPropertyForm({ ...propertyForm, propertyName: e.target.value })} required />
                                <input type="text" placeholder="Developer" value={propertyForm.developerName} onChange={(e) => setPropertyForm({ ...propertyForm, developerName: e.target.value })} required />
                                <input type="text" placeholder="City" value={propertyForm.city} onChange={(e) => setPropertyForm({ ...propertyForm, city: e.target.value })} required />
                                <input type="number" placeholder="Quoted price" value={propertyForm.quotedPrice} onChange={(e) => setPropertyForm({ ...propertyForm, quotedPrice: e.target.value })} required />
                                <input type="number" placeholder="Government guidance value/sqft" value={propertyForm.governmentGuidance} onChange={(e) => setPropertyForm({ ...propertyForm, governmentGuidance: e.target.value })} required />
                                <input type="number" placeholder="Market average/sqft" value={propertyForm.marketAverage} onChange={(e) => setPropertyForm({ ...propertyForm, marketAverage: e.target.value })} required />
                                <input type="number" placeholder="Unit area (sqft)" value={propertyForm.unitArea} onChange={(e) => setPropertyForm({ ...propertyForm, unitArea: e.target.value })} required />
                              </div>
                              <div className="agent-form-actions">
                                <button type="submit" className="agent-primary-btn">{propertyFormFor.propertyId ? "Save Changes" : "Save Property"}</button>
                                <button type="button" className="agent-text-btn" onClick={() => setPropertyFormFor(null)}>Cancel</button>
                              </div>
                            </form>
                          ) : (
                            <button type="button" className="agent-text-btn agent-add-property-link" onClick={() => openAddProperty(c.client_id)}>
                              + Add a property for {c.client_name}
                            </button>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default AgentWorkspace;
