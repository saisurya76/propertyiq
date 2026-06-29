function PropertyForm({
  formData,
  handleChange,
  generateAssessment,
  loading
}) {
  return (
    <div className="card">

      <h2>Analyze Property</h2>

      <div className="form-grid">

        <select
          name="country"
          value={formData.country}
          onChange={handleChange}
        >
          <option>India</option>
          <option>USA</option>
          <option>UAE</option>
          <option>Thailand</option>
          <option>Other</option>
        </select>

        <input
          name="city"
          value={formData.city}
          onChange={handleChange}
          placeholder="City *"
        />

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

        <input
          name="propertyName"
          value={formData.propertyName}
          onChange={handleChange}
          placeholder="Property Name *"
        />

        <input
          name="developerName"
          value={formData.developerName}
          onChange={handleChange}
          placeholder="Developer Name *"
        />

        <input
          name="quotedPrice"
          value={formData.quotedPrice}
          onChange={handleChange}
          placeholder="Quoted Price *"
        />

        <input
          name="areaValue"
          value={formData.areaValue}
          onChange={handleChange}
          placeholder="Area Value *"
        />

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

        <input
          name="monthlyRent"
          value={formData.monthlyRent}
          onChange={handleChange}
          placeholder="Monthly Rent"
        />

        <input
          name="totalUnits"
          value={formData.totalUnits}
          onChange={handleChange}
          placeholder="Total Units"
        />

        <input
          name="unsoldUnits"
          value={formData.unsoldUnits}
          onChange={handleChange}
          placeholder="Unsold Units"
        />

        <input
          name="projectsCompleted"
          value={formData.projectsCompleted}
          onChange={handleChange}
          placeholder="Projects Completed"
        />

        <input
          name="projectsDelayed"
          value={formData.projectsDelayed}
          onChange={handleChange}
          placeholder="Projects Delayed"
        />

        <input
          name="yearsInBusiness"
          value={formData.yearsInBusiness}
          onChange={handleChange}
          placeholder="Years In Business"
        />

        <input
          name="regulatoryViolations"
          value={formData.regulatoryViolations}
          onChange={handleChange}
          placeholder="Regulatory Violations"
        />

      </div>

      <textarea
        name="additionalInformation"
        value={formData.additionalInformation}
        onChange={handleChange}
        placeholder="Additional Intelligence (optional)"
        rows="6"
      />

      <button
        className="primary-btn"
        onClick={generateAssessment}
        disabled={loading}
      >
        {loading && <span className="spinner"></span>}

        {loading
            ? "Analyzing..."
            : "Assess Property"}
      </button>

    </div>
  );
}

export default PropertyForm;