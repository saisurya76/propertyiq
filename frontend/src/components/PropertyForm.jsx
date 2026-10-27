import { useEffect, useRef, useState } from "react";
import { getGovernmentValueLabel } from "../utils/governmentValueLabels";
import { getCitiesForCountry } from "../utils/citiesByCountry";
import { studioApi, getSession } from "../studio/studioApi";

const property_label = (t) => (t ? t.toLowerCase() : "this property type");

function PropertyForm({
  formData,
  handleChange,
  generateAssessment,
  loading,
  onBulkFillFromExtraction,
  onLaunchStudio
}) {
  const availableCities = getCitiesForCountry(formData.country, formData.city);
  const governmentValueLabel = getGovernmentValueLabel(formData.country);

  // Suggestions for the Government Guidance Value and Market Average boxes,
  // looked up from the chosen country, state, city, property type, area unit
  // and (when typed) locality. City-level data only: the server says so, and
  // never invents a number where it has none.
  const [hints, setHints] = useState(null);
  const { country, stateProvince, city, propertyType, areaUnit, location } = formData;
  useEffect(() => {
    let alive = true;
    const timer = setTimeout(() => {
      if (!country || !city) { setHints(null); return; }
      studioApi
        .priceHints({ country, state_province: stateProvince || "", city, property_type: propertyType || "Apartment", area_unit: areaUnit || "sqft", locality: location || "" })
        .then((h) => { if (alive) setHints(h); })
        .catch(() => { if (alive) setHints(null); });
    }, 500);
    return () => { alive = false; clearTimeout(timer); };
  }, [country, stateProvince, city, propertyType, areaUnit, location]);

  // Fill the two boxes with the real figures we hold, instead of making the
  // visitor click. A box is only overwritten while it is empty or still holds
  // the value we filled in ourselves, so anything the visitor typed is kept.
  const autoFilled = useRef({ governmentGuidance: "", marketAverage: "" });
  useEffect(() => {
    if (!hints) return;
    const fill = (name, avail, value) => {
      const current = String(formData[name] ?? "");
      const mine = autoFilled.current[name];
      if (avail && (current === "" || current === mine)) {
        autoFilled.current[name] = String(value);
        if (current !== String(value)) handleChange({ target: { name, value: String(value) } });
      } else if (!avail && mine && current === mine) {
        autoFilled.current[name] = "";
        handleChange({ target: { name, value: "" } });
      }
    };
    fill("governmentGuidance", hints.government?.available, hints.government?.value);
    fill("marketAverage", hints.market?.available, hints.market?.value);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hints]);

  const fmt = (n) => Number(n).toLocaleString(hints?.currency === "INR" ? "en-IN" : "en-US", { maximumFractionDigits: 0 });

  // Backs the property_url_import tier feature — paste a listing URL
  // from any real-estate site, and whichever fields the extraction
  // genuinely finds get filled in automatically. Deliberately does
  // NOT attempt the fraud-verification fields (government value,
  // market average, developer track record) — those are essentially
  // never published on a listing page, and this feature would rather
  // leave them blank for the user to independently research than
  // guess at something a real fraud-check tool needs to verify, not
  // trust from the same source it's meant to be checking.
  const [urlImportInput, setUrlImportInput] = useState("");
  const [urlImportState, setUrlImportState] = useState("idle"); // "idle" | "loading" | "done" | "error"
  const [urlImportMessage, setUrlImportMessage] = useState("");
  // Real, explicit admin control: if the admin has removed
  // property_url_import from every tier (the "hide from main page"
  // action in the admin panel — a bulk uncheck of the same per-tier
  // checkboxes, not a separate hidden flag), this feature should be
  // completely absent from the report page, not just non-functional
  // when tried.
  const [urlImportFeatureAvailable, setUrlImportFeatureAvailable] = useState(false);

  useEffect(() => {
    studioApi.getTiers()
      .then((tiers) => {
        const anyTierHasIt = Object.values(tiers).some((tier) => (tier.features || []).includes("property_url_import"));
        setUrlImportFeatureAvailable(anyTierHasIt);
      })
      .catch(() => {}); // fails closed (stays hidden) — a nice-to-have display check, not critical path
  }, []);

  const handleUrlImport = async () => {
    if (!urlImportInput.trim()) return;
    if (!getSession()) {
      onLaunchStudio?.();
      return;
    }
    setUrlImportState("loading");
    setUrlImportMessage("");
    try {
      const res = await studioApi.extractFromUrl(urlImportInput.trim());
      const found = Object.entries(res.extracted).filter(([, v]) => v !== null && v !== undefined && v !== "");
      onBulkFillFromExtraction(res.extracted);
      setUrlImportState("done");
      setUrlImportMessage(
        found.length > 0
          ? `Filled in ${found.length} field${found.length === 1 ? "" : "s"} from the listing. Please review, and fill in the remaining fields yourself — the government value, market average, and developer track-record fields need independent research and are never auto-filled from a listing page.`
          : "Couldn't find any usable property details on that page — please fill in the form manually."
      );
    } catch (err) {
      setUrlImportState("error");
      setUrlImportMessage(err.status === 403
        ? "Importing from a URL requires an active Studio subscription that includes this feature."
        : (err.message || "Couldn't import from that URL — please fill in the form manually."));
    }
  };

  return (
    <div className="card">

      {urlImportFeatureAvailable && (
        <div className="property-url-import">
          <label htmlFor="property-url-input">Import from a property listing URL (optional)</label>
          <div className="property-url-import-row">
            <input
              id="property-url-input"
              type="url"
              placeholder="Paste a listing URL from any property site"
              value={urlImportInput}
              onChange={(e) => setUrlImportInput(e.target.value)}
              disabled={urlImportState === "loading"}
            />
            <button
              type="button"
              className="property-url-import-btn"
              onClick={handleUrlImport}
              disabled={urlImportState === "loading" || !urlImportInput.trim()}
            >
              {urlImportState === "loading" ? "Importing..." : "Import"}
            </button>
          </div>
          <p className="property-url-import-expectation-note">
            Note: some listing sites block automated access — if that happens, it's an expected limitation
            of that specific site, not a sign anything is wrong. Just fill in the form manually instead.
          </p>
          {urlImportMessage && (
            <p className={`property-url-import-message property-url-import-${urlImportState}`}>
              {urlImportMessage}
            </p>
          )}
        </div>
      )}

      <p className="required-note">
       Only fields marked <strong>*</strong> are required. All other fields improve assessment accuracy.
      </p>

      {/* Property Information */}

      <div className="form-section">
        <h3 className="form-section-title">
          Property Information
        </h3>

        <div className="form-grid">

          <div className="form-field">
            <label>Country *</label>

            <select
              name="country"
              value={formData.country}
              onChange={handleChange}
              disabled
            >
              <option value="India">India</option>
              <option value="USA">USA</option>
              <option value="UAE">UAE</option>
              <option value="Thailand">Thailand</option>
              <option value="Philippines">Philippines</option>
              <option value="Vietnam">Vietnam</option>
              <option value="Indonesia">Indonesia</option>
              <option value="Other">Other</option>
            </select>
          </div>

          <div className="form-field">
            <label>City *</label>

            <select
              name="city"
              value={formData.city}
              onChange={handleChange}
            >
              {availableCities.map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>

          <div className="form-field">
            <label>Location *</label>

            <input
              name="location"
              value={formData.location}
              onChange={handleChange}
              placeholder="Locality / Layout / Sector / Village"
            />
          </div>

          <div className="form-field">
            <label>Property Type *</label>

            <select
              name="propertyType"
              value={formData.propertyType}
              onChange={handleChange}
            >
              <option value="Apartment">Apartment</option>
              <option value="Villa">Villa</option>
              <option value="Plot / Land">Plot / Land</option>
              <option value="Commercial Office">Commercial Office</option>
              <option value="Retail Shop">Retail Shop</option>
              <option value="Warehouse">Warehouse</option>
              <option value="Other">Other</option>
            </select>
          </div>

          <div className="form-field">
            <label>Property Name *</label>

            <input
              name="propertyName"
              value={formData.propertyName}
              onChange={handleChange}
              placeholder="Enter property name"
            />
          </div>

        </div>
      </div>

      {/* Pricing Information */}

      <div className="form-section">
        <h3 className="form-section-title">
          Pricing Information
        </h3>

        <div className="form-grid">

          <div className="form-field">
            <label>Quoted Price *</label>

            <input
              type="number"
              name="quotedPrice"
              value={formData.quotedPrice}
              onChange={handleChange}
              placeholder="Enter quoted price"
            />
          </div>

          <div className="form-field">
            <label>
             {governmentValueLabel.label} *
            </label>

            <input
              type="number"
              name="governmentGuidance"
              placeholder={`${governmentValueLabel.shortLabel} per selected area unit`}
              title={governmentValueLabel.helpText}
              value={formData.governmentGuidance}
              onChange={handleChange}
            />

            {hints?.government?.available && (
              <div className="price-hint">
                <span>
                  Filled in: <strong>{hints.currency} {fmt(hints.government.value)}</strong> per {hints.area_unit}. You can change it.
                  <em>{hints.government.source}. City-level: your locality can differ.</em>
                </span>
              </div>
            )}
            {hints && !hints.government?.available && hints.government?.how_to && (
              <div className="price-hint">
                <span>
                  No built-in figure for {city}. Official source: <strong>{hints.government.how_to.name}</strong>, from {hints.government.how_to.publisher}.
                </span>
                <a href={hints.government.how_to.search_url} target="_blank" rel="noopener noreferrer">Find it ↗</a>
              </div>
            )}

          </div>

          <div className="form-field">
            <label>Market Average *</label>

            <input
              type="number"
              name="marketAverage"
              value={formData.marketAverage}
              onChange={handleChange}
              placeholder="Current market rate per selected area unit"
            />

            {hints?.market?.available && (
              <div className="price-hint">
                <span>
                  Filled in: <strong>{hints.currency} {fmt(hints.market.value)}</strong> per {hints.area_unit}
                  {hints.market.count > 1 && <> (range {fmt(hints.market.low)} to {fmt(hints.market.high)})</>}. You can change it.
                  <em>{hints.market.source}. City-level: your locality can differ.</em>
                </span>
              </div>
            )}
            {hints && !hints.market?.available && (
              <div className="price-hint">
                <span>No market data for {property_label(propertyType)} in {city || "this city"} yet. Check recent listings and sold prices near the property and enter the average.</span>
              </div>
            )}

            <small className="field-help">
              Current market rate for similar properties in this location.
            </small>
          </div>

          <div className="form-field">
            <label>Built-up Area *</label>

            <input
              type="number"
              name="areaValue"
              value={formData.areaValue}
              onChange={handleChange}
              placeholder="Enter built-up area"
            />
          </div>

          <div className="form-field">
            <label>Area Unit *</label>

            <select
              name="areaUnit"
              value={formData.areaUnit}
              onChange={handleChange}
            >
              <option value="sqft">sqft</option>
              <option value="sq yard">sq yard</option>
              <option value="sq meter">sq meter</option>
              <option value="acre">acre</option>
              <option value="hectare">hectare</option>
            </select>
          </div>

          <div className="form-field">
            <label>Expected Monthly Rent</label>

            <input
              type="number"
              name="monthlyRent"
              value={formData.monthlyRent}
              onChange={handleChange}
              placeholder="Expected monthly rent"
            />
          </div>

        </div>
      </div>

      {/* Seller / Builder Information */}

      <div className="form-section">
        <h3 className="form-section-title">
          Seller / Builder Information
        </h3>

        <div className="form-grid">

          <div className="form-field">
            <label>Seller / Builder Name *</label>

            <input
              name="developerName"
              value={formData.developerName}
              onChange={handleChange}
              placeholder="Enter builder or developer name"
            />
          </div>

          <div className="form-field">
            <label>Projects Completed</label>

            <input
              type="number"
              name="projectsCompleted"
              value={formData.projectsCompleted}
              onChange={handleChange}
              placeholder="Number of completed projects"
            />
          </div>

          <div className="form-field">
            <label>Projects Delayed</label>

            <input
              type="number"
              name="projectsDelayed"
              value={formData.projectsDelayed}
              onChange={handleChange}
              placeholder="Projects delivered late"
            />
          </div>

          <div className="form-field">
            <label>Years in Business</label>

            <input
              type="number"
              name="yearsInBusiness"
              value={formData.yearsInBusiness}
              onChange={handleChange}
              placeholder="Years in business"
            />
          </div>

          <div className="form-field">
            <label>Regulatory Violations</label>

            <input
              type="number"
              name="regulatoryViolations"
              value={formData.regulatoryViolations}
              onChange={handleChange}
              placeholder="Known regulatory violations"
            />
          </div>

        </div>
      </div>

      {/* Project Information */}

      <div className="form-section">
        <h3 className="form-section-title">
          Project Information
        </h3>

        <div className="form-grid">

          <div className="form-field">
            <label>Total Units</label>

            <input
              type="number"
              name="totalUnits"
              value={formData.totalUnits}
              onChange={handleChange}
              placeholder="Total project units"
            />
          </div>

          <div className="form-field">
            <label>Unsold Units</label>

            <input
              type="number"
              name="unsoldUnits"
              value={formData.unsoldUnits}
              onChange={handleChange}
              placeholder="Current unsold units"
            />
          </div>

        </div>
      </div>

      {/* Additional Intelligence */}

      <div className="form-section">

        <h3 className="form-section-title">
          Additional Information
        </h3>

        <div className="form-field">

          <label>Anything else we should consider?</label>

          <textarea
            name="additionalInformation"
            value={formData.additionalInformation}
            onChange={handleChange}
            placeholder="Share any additional details that may influence the assessment (optional)."
            rows="6"
          />

        </div>

      </div>

      {/* translate="no" plus a stable, never-changing set of child nodes
          (spinner always mounted, just display:none'd; text lives in one
          persistent span) — Google Translate wraps/rewrites this button's
          DOM on translated pages, and toggling child nodes in/out on click
          (the old {loading && <span>} + text-swap pattern) collided with
          that, throwing a real "insertBefore ... not a child of this node"
          crash on Thai/Vietnamese/Indonesian pages. Never mutate this
          subtree's shape again — only the span's content/style. */}
      <button
        className="primary-btn"
        onClick={generateAssessment}
        disabled={loading}
        translate="no"
      >
        <span
          className="spinner"
          style={{ display: loading ? "inline-block" : "none" }}
        ></span>

        <span>
          {loading
            ? "Analyzing..."
            : "Generate PropertyIQWeb Report"}
        </span>
      </button>

    </div>
  );
}

export default PropertyForm;