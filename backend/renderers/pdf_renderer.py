from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak
)

from reportlab.lib.styles import (
    getSampleStyleSheet,
    ParagraphStyle
)

from reportlab.lib.enums import (
    TA_CENTER
)

from reportlab.lib import colors


def format_currency(value):

    if value >= 10000000:
        return f"₹{value / 10000000:.2f} Cr"

    if value >= 100000:
        return f"₹{value / 100000:.2f} L"

    return f"₹{value:,.0f}"


def generate_pdf(
    assessment,
    risks,
    negotiation_text,
    executive_summary,
    output_file
):

    doc = SimpleDocTemplate(output_file)

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0F172A")
    )

    developer_style = ParagraphStyle(
        "DeveloperStyle",
        parent=styles["Heading3"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#64748B")
    )

    score_heading_style = ParagraphStyle(
        "ScoreHeading",
        parent=styles["Heading2"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#64748B")
    )

    score_style = ParagraphStyle(
        "ScoreStyle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=42,
        leading=48,
        textColor=colors.HexColor("#0F172A")
    )

    rating_style = ParagraphStyle(
        "RatingStyle",
        parent=styles["Heading2"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#15803D")
    )

    section_style = ParagraphStyle(
        "SectionStyle",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#EA580C")
    )

    recommendation_style = ParagraphStyle(
        "RecommendationStyle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        fontSize=26,
        leading=32,
        textColor=colors.HexColor("#0F172A")
    )

    recommendation_text_style = ParagraphStyle(
        "RecommendationText",
        parent=styles["BodyText"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#64748B")
    )

    story = []

    # COVER PAGE

    story.append(
        Paragraph(
            "PROPERTYIQ",
            title_style
        )
    )

    story.append(
        Paragraph(
            "Independent Property Assessment Report",
            ParagraphStyle(
                "SubtitleStyle",
                parent=styles["Heading2"],
                alignment=TA_CENTER
            )
        )
    )

    story.append(
        Spacer(1, 50)
    )

    story.append(
        Paragraph(
            assessment.property_name,
            title_style
        )
    )

    story.append(
        Paragraph(
            f"Developed by {assessment.developer_name}",
            developer_style
        )
    )

    story.append(
        Spacer(1, 60)
    )

    story.append(
        Paragraph(
            "BUYER PROTECTION SCORE",
            score_heading_style
        )
    )

    story.append(
        Spacer(1, 10)
    )

    story.append(
        Paragraph(
            f"{assessment.buyer_protection_score:.2f}",
            score_style
        )
    )

    story.append(
        Paragraph(
            assessment.buyer_protection_rating,
            rating_style
        )
    )

    story.append(
        Spacer(1, 50)
    )

    story.append(
        Paragraph(
            "FINAL RECOMMENDATION",
            section_style
        )
    )

    story.append(
        Spacer(1, 10)
    )

    story.append(
        Paragraph(
            assessment.recommendation,
            recommendation_style
        )
    )

    story.append(
        Spacer(1, 15)
    )

    story.append(
        Paragraph(
            "Independent recommendation generated from valuation analysis, inventory risk assessment, and developer quality review.",
            recommendation_text_style
        )
    )

    story.append(
        PageBreak()
    )

    # PROPERTY OVERVIEW

    story.append(
        Paragraph(
            "PROPERTY OVERVIEW",
            section_style
        )
    )

    story.append(
        Spacer(1, 12)
    )

    story.append(
        Paragraph(
            f"<b>Property:</b> {assessment.property_name}",
            styles["BodyText"]
        )
    )

    story.append(
        Paragraph(
            f"<b>Developer:</b> {assessment.developer_name}",
            styles["BodyText"]
        )
    )

    story.append(
        Paragraph(
            f"<b>Quoted Price:</b> {format_currency(assessment.quoted_price)}",
            styles["BodyText"]
        )
    )

    story.append(
        Paragraph(
            f"<b>Estimated Fair Value:</b> {format_currency(assessment.fair_value)}",
            styles["BodyText"]
        )
    )

    story.append(
        Paragraph(
            f"<b>Inventory Risk:</b> {assessment.inventory_risk}",
            styles["BodyText"]
        )
    )

    story.append(
        Paragraph(
            f"<b>Developer Rating:</b> {assessment.developer_rating}",
            styles["BodyText"]
        )
    )

    story.append(
        Spacer(1, 20)
    )

    story.append(
        Paragraph(
            "KEY FINDINGS",
            section_style
        )
    )

    for risk in risks:
        story.append(
            Paragraph(
                f"• {risk}",
                styles["BodyText"]
            )
        )

    story.append(
        Spacer(1, 20)
    )

    story.append(
        Paragraph(
            "NEGOTIATION GUIDANCE",
            section_style
        )
    )

    story.append(
        Paragraph(
            negotiation_text,
            styles["BodyText"]
        )
    )

    story.append(
        Spacer(1, 20)
    )

    story.append(
        Paragraph(
            "EXECUTIVE SUMMARY",
            section_style
        )
    )

    story.append(
        Paragraph(
            executive_summary.replace(
                "\n",
                "<br/>"
            ),
            styles["BodyText"]
        )
    )

    story.append(
        Spacer(1, 20)
    )

    story.append(
        Paragraph(
            "DISCLAIMER",
            section_style
        )
    )

    story.append(
        Paragraph(
            "PropertyIQ provides informational decision-support analysis only. This report should not be considered legal, financial, tax, engineering, investment, or regulatory advice. Users should independently verify all information before making property decisions.",
            styles["BodyText"]
        )
    )

    doc.build(story)