import { useState } from "react";
import "./App.css";

import PropertyForm from "./components/PropertyForm";
import AssessmentResult from "./components/AssessmentResult";
import Disclaimer from "./components/Disclaimer";

function App() {
  const [formData, setFormData] = useState({
    country: "India",
    stateProvince: "Telangana",
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
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const generateAssessment = async () => {
    if (loading) return;
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
      setLoading(true);
      const response = await fetch(
        "https://propertyiq-api-q21y.onrender.com/assess",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            country: formData.country,
            stateProvince: formData.stateProvince,
            city: formData.city,

            propertyName:
              formData.propertyName,

            developerName:
              formData.developerName,

            quotedPrice:
              Number(formData.quotedPrice),

            unitArea:
              Number(formData.areaValue),

            areaUnit:
              formData.areaUnit,

            monthlyRent:
              Number(formData.monthlyRent || 0),

            totalUnits:
              Number(formData.totalUnits || 100),

            unsoldUnits:
              Number(formData.unsoldUnits || 20),

            projectsCompleted:
              Number(formData.projectsCompleted || 10),

            projectsDelayed:
              Number(formData.projectsDelayed || 1),

            yearsInBusiness:
              Number(formData.yearsInBusiness || 15),

            regulatoryViolations:
              Number(formData.regulatoryViolations || 0)
          })
        }
      );

      if (!response.ok) {
          throw new Error("Assessment failed.");
      }

      const data = await response.json();

      setResult(data);

    } catch (error) {

      console.error(error);

      alert(
        "Failed to connect to PropertyIQ API"
      );
    }
    finally{
        setLoading(false);
    }
  };

  return (
    <div className="app">

      <div className="hero">

       <div className="hero-brand">
        PROPERTYIQ
      </div>

      <div className="hero-subtitle">
        Independent Property Intelligence
      </div>

      <h1>
        Know Before You Buy.
      </h1>

      <p>
        Make informed property decisions using
        independent, explainable and evidence-based intelligence.
      </p>

      </div>

      <PropertyForm
        formData={formData}
        handleChange={handleChange}
        generateAssessment={generateAssessment}
        loading={loading}
      />

      <AssessmentResult
        result={result}
        formData={formData}
      />

      <Disclaimer />

      <footer className="footer">

      <p>PropertyIQ v1.0.0 Beta</p>

      <p>Independent Property Intelligence</p>

      <p>© 2026 PropertyIQ</p>

    </footer>

    </div>
  );
}

export default App;