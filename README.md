# propertyiq
Global Property Due Diligence, Valuation and Buyer Protection Assessment Platform



# 🛡️ PropertyIQ

<div align="center">

## Independent Property Intelligence for Home Buyers

### **Know Before You Negotiate.**

**An independent buyer-first platform that evaluates property quality, pricing, developer credibility, market conditions, and negotiation opportunities through transparent intelligence models.**

---

![Version](https://img.shields.io/badge/version-v1.0.0-blue)
![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)
![License](https://img.shields.io/badge/license-MIT-green)

</div>

---

# What is PropertyIQ?

PropertyIQ is an **Independent Property Intelligence Platform** designed to help home buyers make informed purchasing decisions before committing to one of the largest financial investments of their lives.

Unlike traditional property valuation tools, PropertyIQ evaluates a property using multiple independent intelligence engines to generate a comprehensive **Buyer Protection Score**.

Rather than answering only:

> **"What is this property worth?"**

PropertyIQ answers much more important questions:

- Is the quoted price fair?
- Is the developer trustworthy?
- Does inventory create buyer leverage?
- How much should I negotiate?
- What does the government guidance value indicate?
- How confident is this recommendation?
- What are the biggest risks before purchasing?

The objective is simple:

> **Help buyers purchase with confidence rather than emotion.**

---

# Why PropertyIQ?

Buying property is often an information imbalance.

Most information available to buyers comes from organizations whose objective is to sell property.

- Builders market projects.
- Brokers close transactions.
- Property portals list inventory.
- Advertisements highlight positives.

Very few platforms evaluate a property solely from the buyer's perspective.

PropertyIQ was created to become an **independent buyer-first intelligence platform**, providing transparent analysis that helps buyers understand pricing, risk, negotiation opportunities, and overall purchase quality.

---

# Core Principles

PropertyIQ is built around four principles:

- Independent analysis
- Transparent methodology
- Buyer-first decision support
- Explainable recommendations

Every recommendation presented by PropertyIQ is supported by measurable assessment models rather than opaque scoring.

---

# Key Capabilities

## 🛡 Buyer Protection Intelligence

- Buyer Protection Score (0–100)
- Deal Quality Assessment
- Recommendation Confidence
- Buyer Advantage Meter

---

## 💰 Pricing Intelligence

- Fair Value Estimation
- Comparable Sales Analysis
- Rental Yield Analysis
- Replacement Cost Valuation
- Price Premium / Discount Analysis

---

## 🏗 Developer Intelligence

Evaluate developer quality using:

- Project delivery history
- Years in business
- Project delays
- Regulatory compliance

---

## 📦 Inventory Intelligence

Understand current market conditions through:

- Unsold inventory analysis
- Inventory risk
- Buyer leverage estimation

---

## 🤝 Negotiation Intelligence

Generate practical negotiation guidance including:

- Target purchase price
- Negotiation range
- Estimated buyer savings
- Negotiation position

---

## 🏛 Government Intelligence

Compare market pricing against government guidance values.

Includes:

- Government guidance rate
- Estimated government property value
- Buyer observations
- Confidence level

---

## 📊 Market Intelligence

Understand how the property compares against nearby developments.

Includes:

- Comparable projects
- Market asking prices
- Average market pricing
- Fair value comparison

---

## 📄 Professional Reports

Generate buyer-ready reports in multiple formats.

- Interactive Dashboard
- HTML Buyer Protection Report
- PDF Buyer Protection Report

Designed for buyers, investors, consultants, and advisors.

---

# Dashboard Preview

> **📷 Screenshot Placeholder**

```
docs/images/dashboard-overview.png
```

Recommended screenshots:

- Assessment Dashboard
- Buyer Protection Score
- Pricing Intelligence
- Government Intelligence
- Negotiation Advisor
- Market Context

---

# Sample Buyer Protection Report

> **📷 Screenshot Placeholder**

```
docs/images/pdf-cover.png
```

The generated report includes:

- Executive Summary
- Buyer Protection Score
- Pricing Analysis
- Government Intelligence
- Market Context
- Negotiation Strategy
- Key Findings
- Final Recommendation




# 🏗️ Architecture

PropertyIQ follows a modular architecture that separates assessment engines, intelligence modules, report generation, and the user interface.

```text
                    +----------------------+
                    |    React Dashboard   |
                    +----------+-----------+
                               |
                               |
                     REST API (FastAPI)
                               |
                 +-------------+-------------+
                 |                           |
        Assessment Pipeline          Report Generation
                 |                           |
                 |                           |
   +-------------+-------------+             |
   |             |             |             |
 Valuation   Developer    Inventory      HTML Report
 Engine       Engine        Engine
   |             |             |             |
   +-------------+-------------+             |
                 |                           |
         Buyer Protection Engine             |
                 |                           |
   +-------------+-------------+             |
   |             |             |             |
Government   Market      Negotiation     PDF Report
Intelligence Intelligence Intelligence
                 |
                 |
        Final Buyer Assessment
```

---

# Technology Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18 |
| Backend | FastAPI |
| Language | Python 3.9+ |
| Reports | HTML, PDF |
| API | REST |
| Styling | CSS |
| Testing | Pytest |
| Deployment | Render |

---

# Project Structure

```text
propertyiq/

├── backend/
│   ├── assessment_pipeline.py
│   ├── valuation_models.py
│   ├── buyer_protection.py
│   ├── negotiation.py
│   ├── government_intelligence.py
│   ├── comparables.py
│   ├── findings.py
│   ├── recommendation.py
│   ├── renderers/
│   │      ├── html_renderer.py
│   │      └── pdf_renderer.py
│   └── api.py
│
├── frontend/
│
├── configs/
│
├── scripts/
│
├── tests/
│
├── outputs/
│   ├── reports/
│   └── pdfs/
│
└── README.md
```

---

# Installation

Clone the repository

```bash
git clone https://github.com/saisurya76/propertyiq.git

cd propertyiq
```

Create a virtual environment

```bash
python3 -m venv .venv
```

Activate

macOS / Linux

```bash
source .venv/bin/activate
```

Windows

```bash
.venv\Scripts\activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

---

# Running PropertyIQ

Start the backend

```bash
python3 -m uvicorn backend.api:app --reload
```

Backend

```
http://localhost:8000
```

Swagger

```
http://localhost:8000/docs
```

Start the frontend

```bash
cd frontend

npm install

npm run dev
```

Frontend

```
http://localhost:5173
```

---

# Quick Start

1. Open the dashboard.

2. Enter property details.

3. Click **Assess Property**.

4. Review the Buyer Protection Score.

5. Analyze pricing, developer quality, inventory risk, and market intelligence.

6. Download the professional Buyer Protection Report.


# 🔍 How PropertyIQ Works

PropertyIQ evaluates every property through multiple independent intelligence engines. Each engine analyzes a different aspect of the purchase before producing a final buyer recommendation.

```text
Property Details
        │
        ▼
Valuation Intelligence
        │
        ▼
Developer Intelligence
        │
        ▼
Inventory Intelligence
        │
        ▼
Government Intelligence
        │
        ▼
Market Intelligence
        │
        ▼
Negotiation Intelligence
        │
        ▼
Buyer Protection Score
        │
        ▼
Final Recommendation
```

The result is a transparent assessment that explains **why** a recommendation was generated rather than presenting only a final score.

---

# Buyer Protection Score

The **Buyer Protection Score (BPS)** is PropertyIQ's primary decision metric.

Unlike traditional valuation tools that estimate only property value, the Buyer Protection Score evaluates the overall quality of a purchase from a buyer's perspective.

Current assessment weights:

| Intelligence Engine | Weight |
|----------------------|-------:|
| Valuation Analysis | 50% |
| Inventory Risk | 30% |
| Developer Quality | 20% |

Score interpretation:

| Score | Rating |
|-------:|---------|
| 90–100 | Excellent |
| 80–89 | Strong |
| 70–79 | Fair |
| 60–69 | Caution |
| Below 60 | High Risk |

---

# Intelligence Engines

## Pricing Intelligence

Evaluates whether the asking price is justified.

Includes:

- Comparable Sales
- Rental Yield
- Replacement Cost
- Weighted Fair Value

---

## Developer Intelligence

Measures execution capability using:

- Completed projects
- Delayed projects
- Years in business
- Regulatory history

---

## Inventory Intelligence

Measures market supply conditions.

Includes:

- Unsold inventory
- Inventory risk
- Buyer leverage

---

## Government Intelligence

Compares the property with official government guidance values.

Provides:

- Government guidance rate
- Estimated government value
- Buyer observations
- Confidence assessment

---

## Market Intelligence

Compares the property with nearby developments.

Includes:

- Comparable projects
- Market asking prices
- Average price per square foot

---

## Negotiation Intelligence

Provides practical buyer guidance.

Includes:

- Target purchase price
- Recommended negotiation range
- Estimated buyer savings
- Buyer negotiation position

---

# Report Generation

PropertyIQ generates professional buyer reports in multiple formats.

## Interactive Dashboard

Designed for real-time exploration of assessment results.

Provides:

- Buyer Protection Score
- Pricing Intelligence
- Government Intelligence
- Market Context
- Buyer Advisory
- Recommendation Confidence

---

## HTML Report

Optimized for browser viewing and sharing.

Includes:

- Executive Summary
- Pricing Analysis
- Government Intelligence
- Market Context
- Buyer Advisory
- Final Recommendation

---

## PDF Report

Designed for printing and professional sharing.

Includes:

- Premium cover page
- Buyer Protection Score
- Property Overview
- Market Context
- Negotiation Strategy
- Executive Summary
- Disclaimer

---

# Testing

PropertyIQ includes automated unit tests covering the core assessment engines.

Run the complete suite:

```bash
python3 -m pytest
```

Current status:

```
31 Passed
0 Failed
```

---

# Example Workflow

```text
Enter Property Details
          │
          ▼
Run Assessment
          │
          ▼
Review Buyer Protection Score
          │
          ▼
Analyze Pricing Intelligence
          │
          ▼
Review Government Intelligence
          │
          ▼
Evaluate Negotiation Guidance
          │
          ▼
Download Buyer Protection Report
```

# 🗺️ Roadmap

## ✅ Version 1.0

PropertyIQ v1.0 delivers a complete buyer-first property assessment platform with:

- Buyer Protection Score
- Fair Value Estimation
- Pricing Intelligence
- Developer Assessment
- Inventory Risk Analysis
- Government Intelligence
- Market Intelligence
- Negotiation Intelligence
- Buyer Advantage Meter
- Recommendation Confidence
- Interactive Dashboard
- HTML Report
- PDF Buyer Protection Report
- REST API
- Automated Test Suite

---

## 🚀 Future Roadmap

The following capabilities are planned for future releases.

### Location Intelligence

Interactive map showing:

- Property location
- Metro stations
- Highways
- Airports
- Railway stations
- Schools
- Hospitals
- Shopping centres
- Employment hubs
- Parks
- Future infrastructure projects

---

### Environmental Intelligence

- Flood zones
- High tension power lines
- Industrial zones
- Quarry and mining areas
- Airport noise zones
- Lake buffer zones

---

### Additional Intelligence Engines

- Infrastructure Score
- Connectivity Score
- Lifestyle Score
- Future Growth Score
- Environmental Risk Score
- Location Intelligence Score

---

# Contributing

Contributions are welcome.

If you would like to contribute:

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes.
4. Open a Pull Request.

For significant feature additions, please open an issue first to discuss the proposed enhancement.

---

# Design Principles

PropertyIQ is built around a few core principles.

- Buyer First
- Independent Assessment
- Transparent Methodology
- Explainable Recommendations
- Practical Decision Support

The platform is designed to help buyers make informed decisions rather than simply estimate market prices.

---

# Project Status

Current Release

```
Version: 1.0.0
Status : Beta
```

The assessment engines, reporting system, REST API, and user interface are stable and ready for evaluation.

Future releases will continue to expand PropertyIQ with additional intelligence engines while maintaining backward compatibility wherever practical.

---

# License

This project is licensed under the MIT License.

See the LICENSE file for details.

---

# Acknowledgements

PropertyIQ brings together ideas from multiple disciplines including:

- Property valuation
- Market analysis
- Risk assessment
- Software engineering
- User experience design
- Decision support systems

The project was developed with the goal of providing transparent, buyer-first intelligence for one of life's most important financial decisions.

---

# Support

If you encounter an issue or have suggestions for improvement:

- Open a GitHub Issue
- Submit a Pull Request
- Share feedback through the repository discussions

---

# Author

**Suryanarayana Bollapragada**

Senior Full Stack AI Engineer

Independent Software Architect

---

<div align="center">

## PropertyIQ

### Independent Property Intelligence for Home Buyers

**Know Before You Negotiate.**

Built with a buyer-first philosophy.

⭐ If you find this project useful, consider giving it a star.

</div>

