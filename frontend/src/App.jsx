import { useState } from "react";
import "./App.css";

import PropertyForm from "./components/PropertyForm";
import AssessmentResult from "./components/AssessmentResult";
import Disclaimer from "./components/Disclaimer";

function App() {
  const [formData, setFormData] = useState({
    country: "India",
    city: "",

    propertyType: "Apartment",

    propertyName: "",
    developerName: "",

    quotedPrice: "",

    areaValue: "",
    areaUnit: "sqft",

    monthlyRent: "",

    totalUnits: "",
    unsoldUnits: "",

    projectsCompleted: "",
    projectsDelayed: "",
    yearsInBusiness: "",
    regulatoryViolations: "",

    additionalInformation: ""
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
      !formData.city ||
      !formData.propertyName ||
      !formData.developerName ||
      !formData.quotedPrice ||
      !formData.areaValue
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
            unitArea: Number(formData.areaValue),
            monthlyRent: Number(formData.monthlyRent || 0)
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
    <div className="app">

      <div className="hero">

        <div className="hero-brand">
          PROPERTYIQ
        </div>

        <h1>
          Know Before You Buy.
        </h1>

        <p>
          Independent property intelligence
          designed to protect buyers,
          not sell property.
        </p>

      </div>

      <PropertyForm
        formData={formData}
        handleChange={handleChange}
        generateAssessment={generateAssessment}
      />

      <AssessmentResult
        result={result}
        formData={formData}
      />

      <Disclaimer />

    </div>
  );
}

export default App;