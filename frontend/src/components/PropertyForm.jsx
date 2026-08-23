import { getGovernmentValueLabel } from "../utils/governmentValueLabels";

function PropertyForm({
  formData,
  handleChange,
  generateAssessment,
  loading
}) {
  const governmentValueLabel = getGovernmentValueLabel(formData.country);

  return (
    <div className="card">

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
              <option>Other</option>
            </select>
          </div>

          <div className="form-field">
            <label>City *</label>

            <input
              name="city"
               value={formData.city}
              onChange={handleChange}
              placeholder="Hyderabad"
              disabled
            />
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