def render_html(
    assessment,
    risks,
    negotiation_text
):

    html = f"""
<!DOCTYPE html>
<html>
<head>
  
    <style>

    body {{
       font-family: Inter, Arial, sans-serif;
        max-width: 1100px;
        margin: auto;
        padding: 40px;
        line-height: 1.6;
        color: #222;
        background: #fafafa;
    }}

    .report-header {{
        text-align: center;
        margin-bottom: 40px;
    }}

    .product-name {{
        font-size: 40px;
        font-weight: bold;
        color: #1f4e79;
        letter-spacing: 2px;
    }}

    .product-tagline {{
        font-size: 18px;
        color: #666;
        margin-top: 8px;
        margin-bottom: 20px;
    }}

    h1 {{
        color: #1f4e79;
        font-size: 34px;
        margin-top: 10px;
        margin-bottom: 8px;
    }}

    h2 {{
        color: #1f4e79;
        font-size: 24px;
        margin-top: 45px;
        margin-bottom: 18px;
        border-bottom: 2px solid #1f4e79;
        padding-bottom: 8px;
    }}

    table {{
        width: 100%;
        border-collapse: collapse;
        margin: 20px 0 35px 0;
        background: white;
        border-radius: 10px;
        overflow: hidden;
    }}

    td, th {{
        border: 1px solid #e5e7eb;
        padding: 12px 14px;
    }}

    td:first-child {{
        width: 35%;
        font-weight: 600;
        background: #f8fafc;
        color: #374151;
    }}

    .score {{
        font-size: 28px;
        font-weight: bold;
    }}

    .score-card {{
        text-align: center;
        border: 2px solid #1f4e79;
        border-radius: 12px;
        padding: 25px;
        margin: 35px 0;
        background: white;
    }}

    .score-value {{
        font-size: 56px;
        font-weight: bold;
        color: #1f4e79;
        margin-top: 10px;
    }}

    .score-rating {{
        font-size: 22px;
        font-weight: bold;
        letter-spacing: 2px;
        color: #2e7d32;
        margin-top: 8px;
    }}

    </style>

</head>

<body>

  <div class="report-header">

        <div class="product-name">
            PropertyIQ
        </div>

        <div class="product-tagline">
            Independent Property Intelligence
        </div>

        <h1>
            Buyer Protection Report
        </h1>

    </div>

<h2>Executive Summary</h2>

<table>

    <tr>
        <td>Property</td>
        <td>{assessment.property_name}</td>
    </tr>

    <tr>
        <td>Seller / Builder</td>
        <td>{assessment.developer_name}</td>
    </tr>

     <tr>
        <td>Country</td>
        <td>{assessment.country}</td>
    </tr>

    <tr>
        <td>State / Province</td>
        <td>{assessment.state_province}</td>
    </tr>

    <tr>
        <td>City</td>
        <td>{assessment.city}</td>
    </tr>

    <tr>
        <td>Recommended Action</td>
        <td>{assessment.recommendation}</td>
    </tr>

</table>

<div class="score-card">

    <h2>Buyer Protection Score</h2>

    <div class="score-value">
        {assessment.buyer_protection_score}
    </div>

    <div class="score-rating">
        {assessment.buyer_protection_rating}
    </div>

</div>

<h2>Fair Value Analysis</h2>

<table>

    <tr>
        <td>Quoted Price</td>
        <td>{assessment.quoted_price}</td>
    </tr>

    <tr>
        <td>Fair Value</td>
        <td>{assessment.fair_value}</td>
    </tr>

    <tr>
        <td>Overpricing %</td>
        <td>{assessment.overpricing_percent}</td>
    </tr>

</table>

<h2>Inventory Risk</h2>

<p>
    {assessment.inventory_risk}
</p>

<h2>Seller / Builder Assessment</h2>

<p>
    {assessment.developer_rating}
</p>

<h2>Key Buyer Risks</h2>

<ul>
    {''.join(f'<li>{risk}</li>' for risk in risks)}
</ul>

<h2>Negotiation Strategy</h2>

<p>
    {negotiation_text}
</p>

<h2>Detailed Findings</h2>

<p>
    <strong>Pricing:</strong><br>
    {assessment.findings.pricing_finding}
</p>

<p>
    <strong>Inventory:</strong><br>
    {assessment.findings.inventory_finding}
</p>

<p>
    <strong>Developer:</strong><br>
    {assessment.findings.developer_finding}
</p>

<p>
    <strong>Overall:</strong><br>
    {assessment.findings.overall_finding}
</p>

<h2>Final Recommendation</h2>

<p>
    <strong>
        {assessment.recommendation}
    </strong>
</p>

</body>
</html>
"""

    return html