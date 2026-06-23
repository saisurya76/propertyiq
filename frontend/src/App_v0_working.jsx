import { useState } from "react";

function App() {
  const [formData, setFormData] = useState({
    country: "India",
    city: "Hyderabad",
    propertyName: "",
    developerName: "",
    quotedPrice: "",
    unitArea: "",
    monthlyRent: ""
  });

  const [result, setResult] = useState(null);

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const generateAssessment = async () => {

  if (
    !formData.propertyName ||
    !formData.developerName ||
    !formData.quotedPrice ||
    !formData.unitArea ||
    !formData.monthlyRent
  ) {
    alert("Please complete all required fields.");
    return;
  }

  try {
    const response = await fetch(
      "http://127.0.0.1:8000/assess",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          country: formData.country,
          city: formData.city,
          propertyName: formData.propertyName,
          developerName: formData.developerName,
          quotedPrice: Number(formData.quotedPrice),
          unitArea: Number(formData.unitArea),
          monthlyRent: Number(formData.monthlyRent)
        })
      }
    );

    const data = await response.json();

    setResult(data);
  } catch (error) {
    console.error(error);
    alert("Failed to connect to PropertyIQ API");
  }
};

  return (
    <div
      style={{
        maxWidth: "900px",
        margin: "40px auto",
        fontFamily: "Arial, sans-serif",
        padding: "20px"
      }}
    >
      <h1>PropertyIQ</h1>

      <p>
        Independent Property Assessment Platform
      </p>

      <hr />

      <h2>Property Details</h2>

      <input
        name="country"
        value={formData.country}
        onChange={handleChange}
        placeholder="Country"
      />

      <br /><br />

      <input
        name="city"
        value={formData.city}
        onChange={handleChange}
        placeholder="City"
      />

      <br /><br />

      <input
        name="propertyName"
        value={formData.propertyName}
        onChange={handleChange}
        placeholder="Property Name"
      />

      <br /><br />

      <input
        name="developerName"
        value={formData.developerName}
        onChange={handleChange}
        placeholder="Developer"
      />

      <br /><br />

      <input
        name="quotedPrice"
        value={formData.quotedPrice}
        onChange={handleChange}
        placeholder="Quoted Price"
      />

      <br /><br />

      <input
        name="unitArea"
        value={formData.unitArea}
        onChange={handleChange}
        placeholder="Area"
      />

      <br /><br />

      <input
        name="monthlyRent"
        value={formData.monthlyRent}
        onChange={handleChange}
        placeholder="Monthly Rent"
      />

      <br /><br />

      <button onClick={generateAssessment}>
        Generate Assessment
      </button>

      {result && (
        <div style={{ marginTop: "40px" }}>
          <h2>Assessment Result</h2>

          <p>
            <strong>Buyer Protection Score:</strong>{" "}
            {result.score}
          </p>

          <p>
            <strong>Rating:</strong>{" "}
            {result.rating}
          </p>

          <p>
            <strong>Fair Value:</strong>{" "}
            {result.fairValue}
          </p>

          <p>
            <strong>Recommendation:</strong>{" "}
            {result.recommendation}
          </p>
        </div>
      )}

      <hr />

      <h3>Important Disclaimer</h3>

      <p style={{ fontSize: "14px", color: "#666" }}>
        PropertyIQ provides AI-assisted property assessment
        and decision-support guidance only. Results are
        informational in nature and should not be considered
        legal, financial, investment, tax, valuation,
        engineering, or regulatory advice. Users should
        independently verify all information and consult
        qualified professionals before making property
        decisions.
      </p>
    </div>
  );
}

export default App;