def render_html(
    assessment,
    risks,
    negotiation_text
):

    html = f"""
<!DOCTYPE html>
<html>
<head>
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

    <style>

    body {{
        font-family: Arial, sans-serif;
        margin: 40px;
        line-height: 1.6;
    }}

    h1 {{
        color: #1f4e79;
    }}

    h2 {{
        border-bottom: 1px solid #ddd;
        padding-bottom: 5px;
    }}

    table {{
        width: 100%;
        border-collapse: collapse;
    }}

    td, th {{
        border: 1px solid #ddd;
        padding: 8px;
    }}

    .score {{
        font-size: 28px;
        font-weight: bold;
    }}

    </style>

</head>

<body>

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
        <td>Recommendation</td>
        <td>{assessment.recommendation}</td>
    </tr>

</table>

<h2>Buyer Protection Score</h2>

<p class="score">
    {assessment.buyer_protection_score}
    ({assessment.buyer_protection_rating})
</p>

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