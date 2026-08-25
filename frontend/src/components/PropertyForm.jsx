import { useEffect, useState } from "react";
import { getGovernmentValueLabel } from "../utils/governmentValueLabels";
import { getCitiesForCountry } from "../utils/citiesByCountry";
import { studioApi, getSession } from "../studio/studioApi";

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
              <option>India</option>
              <option>USA</option>
              <option>UAE</option>
              <option>Thailand</option>
              <option>Philippines</option>
              <option>Vietnam</option>
              <option>Indonesia</option>
              <option>Other</option>
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
              <option>Apartment</option>
              <option>Villa</option>
              <option>Plot / Land</option>
              <option>Commercial Office</option>
              <option>Retail Shop</option>
              <option>Warehouse</option>
              <option>Other</option>
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
              <option>sqft</option>
              <option>sq yard</option>
              <option>sq meter</option>
              <option>acre</option>
              <option>hectare</option>
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

      <button
        className="primary-btn"
        onClick={generateAssessment}
        disabled={loading}
      >
        {loading && <span className="spinner"></span>}

        {loading
          ? "Analyzing..."
          : "Generate PropertyIQ Report"}
      </button>

    </div>
  );
}

export default PropertyForm;