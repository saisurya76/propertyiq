function PropertyForm({
  formData,
  handleChange,
  generateAssessment,
  loading
}) {
  return (
    <div className="card">

      <h2>Property Assessment</h2>

      <p className="required-note">
        Fields marked <strong>*</strong> are required.
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
              placeholder="Aparna Sarovar Zenith"
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
              placeholder="18000000"
            />
          </div>

          <div className="form-field">
            <label>Built-up Area *</label>

            <input
              type="number"
              name="areaValue"
              value={formData.areaValue}
              onChange={handleChange}
              placeholder="1800"
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
              placeholder="45000"
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
              placeholder="Aparna Constructions"
            />
          </div>

          <div className="form-field">
            <label>Projects Completed</label>

            <input
              type="number"
              name="projectsCompleted"
              value={formData.projectsCompleted}
              onChange={handleChange}
              placeholder="20"
            />
          </div>

          <div className="form-field">
            <label>Projects Delayed</label>

            <input
              type="number"
              name="projectsDelayed"
              value={formData.projectsDelayed}
              onChange={handleChange}
              placeholder="1"
            />
          </div>

          <div className="form-field">
            <label>Years in Business</label>

            <input
              type="number"
              name="yearsInBusiness"
              value={formData.yearsInBusiness}
              onChange={handleChange}
              placeholder="25"
            />
          </div>

          <div className="form-field">
            <label>Regulatory Violations</label>

            <input
              type="number"
              name="regulatoryViolations"
              value={formData.regulatoryViolations}
              onChange={handleChange}
              placeholder="0"
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
              placeholder="500"
            />
          </div>

          <div className="form-field">
            <label>Unsold Units</label>

            <input
              type="number"
              name="unsoldUnits"
              value={formData.unsoldUnits}
              onChange={handleChange}
              placeholder="120"
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
            placeholder="Provide any additional information that may help evaluate this property."
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
          : "Generate Assessment"}
      </button>

    </div>
  );
}

export default PropertyForm;