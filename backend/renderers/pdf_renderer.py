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

    price_position = abs(
        assessment.overpricing_percent
    )

    if assessment.overpricing_percent >= 0:
        position_text = (
            f"{price_position:.2f}% Above Fair Value"
        )
    else:
        position_text = (
            f"{price_position:.2f}% Below Fair Value"
        )

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
            f"<b>Area:</b> {assessment.unit_area:,.0f} {assessment.area_unit}",
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
            f"<b>Price Position:</b> {position_text}",
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
        "SCORE BREAKDOWN",
        section_style
    )
    )

    story.append(
        Paragraph(
            f"Valuation Analysis: {assessment.valuation_score:.2f}",
            styles["BodyText"]
        )
    )

    story.append(
        Paragraph(
            f"Inventory Risk: {assessment.inventory_score:.2f}",
            styles["BodyText"]
        )
    )

    story.append(
        Paragraph(
            f"Developer Quality: {assessment.developer_score:.2f}",
            styles["BodyText"]
        )
    )

    story.append(
        Spacer(1, 8)
    )

    story.append(
        Paragraph(
            "Scores range from 0–100. Higher scores indicate lower buyer risk.",
            styles["BodyText"]
        )
    )

    story.append(
        Paragraph(
            "90–100 Excellent | 80–89 Strong | 70–79 Fair | 60–69 Caution | Below 60 High Risk",
            styles["BodyText"]
        )
    )

    story.append(
        Spacer(1, 20)
    )

    # MARKET INTELLIGENCE

        # MARKET INTELLIGENCE

    if assessment.comparables:

        story.append(
            Paragraph(
                "MARKET INTELLIGENCE",
                section_style
            )
        )

        story.append(
            Paragraph(
                f"Market Average Price: ₹{assessment.market_average_price_per_sqft:,.0f} / sqft",
                styles["BodyText"]
            )
        )

        story.append(
            Spacer(1, 8)
        )

        for project in assessment.comparables:

            story.append(
                Paragraph(
                    f"<b>{project.project_name}</b>",
                    styles["BodyText"]
                )
            )

            story.append(
                Paragraph(
                    f"{project.developer} | ₹{project.price_per_sqft:,.0f} / sqft",
                    styles["BodyText"]
                )
            )

        story.append(
            Spacer(1, 20)
        )

    story.append(
        Spacer(1, 20)
    )

    story.append(
    Paragraph(
        "HOW PROPERTYIQ WORKS",
        section_style
    )
    )

    story.append(
        Paragraph(
            "Buyer Protection Score",
            styles["BodyText"]
        )
    )

    story.append(
        Paragraph(
            "Valuation Analysis — 50%",
            styles["BodyText"]
        )
    )

    story.append(
        Paragraph(
            "Inventory Risk — 30%",
            styles["BodyText"]
        )
    )

    story.append(
        Paragraph(
            "Developer Quality — 20%",
            styles["BodyText"]
        )
    )

    story.append(
        Spacer(1, 8)
    )

    story.append(
        Paragraph(
            "Valuation receives the highest weight because purchase price has the largest direct impact on buyer outcomes.",
            styles["BodyText"]
        )
    )

    story.append(
        Paragraph(
            "Inventory risk influences future appreciation potential and resale liquidity.",
            styles["BodyText"]
        )
    )

    story.append(
        Paragraph(
            "Developer quality evaluates delivery history, execution capability, and regulatory compliance.",
            styles["BodyText"]
        )
    )

    story.append(
        Spacer(1, 8)
    )

    story.append(
        Paragraph(
            "These weights represent the current PropertyIQ assessment methodology and may evolve as additional market intelligence and performance data become available.",
            styles["BodyText"]
        )
    )

    story.append(
        Spacer(1, 20)
    )


    # KEY FINDINGS

    story.append(
        Paragraph(
            "KEY FINDINGS",
            section_style
        )
    )

    story.append(
        Paragraph(
            f"• Property is priced {position_text.lower()}.",
            styles["BodyText"]
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