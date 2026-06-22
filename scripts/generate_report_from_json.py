import json
import os

from backend.assessment_pipeline import PropertyInput, run_assessment
from backend.executive_summary import generate_executive_summary
from backend.risk_engine import identify_risks
from backend.negotiation import negotiation_guidance
from backend.renderers.html_renderer import render_html
from backend.renderers.pdf_renderer import generate_pdf


def load_property(path):
    with open(path, "r") as f:
        data = json.load(f)

    return PropertyInput(**data)


def generate_reports(json_file):

    property_data = load_property(json_file)

    assessment = run_assessment(property_data)

    summary = generate_executive_summary(
        property_name=assessment.property_name,
        quoted_price=assessment.quoted_price,
        fair_value=assessment.fair_value,
        buyer_protection_score=assessment.buyer_protection_score,
        buyer_protection_rating=assessment.buyer_protection_rating,
        recommendation=assessment.recommendation,
        inventory_risk=assessment.inventory_risk,
        developer_rating=assessment.developer_rating
    )

    risks = identify_risks(
        assessment.overpricing_percent,
        assessment.inventory_risk,
        assessment.developer_rating
    )

    guidance = negotiation_guidance(
        assessment.quoted_price,
        assessment.fair_value
    )

    report_name = os.path.splitext(
        os.path.basename(json_file)
    )[0]

    html_output = f"outputs/reports/{report_name}.html"
    pdf_output = f"outputs/pdfs/{report_name}.pdf"

    html = render_html(
        assessment,
        risks,
        guidance
    )

    with open(html_output, "w", encoding="utf-8") as f:
        f.write(html)

    generate_pdf(
        assessment=assessment,
        risks=risks,
        negotiation_text=guidance,
        executive_summary=summary,
        output_file=pdf_output
    )

    print(f"Generated: {html_output}")
    print(f"Generated: {pdf_output}")


def main():

    os.makedirs(
        "outputs/reports",
        exist_ok=True
    )

    os.makedirs(
        "outputs/pdfs",
        exist_ok=True
    )

    files = [
        "sample_inputs/india_aparna.json",
        "sample_inputs/thailand_condo.json",
        "sample_inputs/usa_austin.json"
    ]

    for file in files:
        generate_reports(file)


if __name__ == "__main__":
    main()