from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer
)

from reportlab.lib.styles import (
    getSampleStyleSheet
)


def generate_pdf(
    assessment,
    risks,
    negotiation_text,
    executive_summary,
    output_file
):

    doc = SimpleDocTemplate(output_file)

    styles = getSampleStyleSheet()

    story = []

    story.append(
        Paragraph(
            "PropertyIQ Assessment Report",
            styles["Title"]
        )
    )

    story.append(Spacer(1, 12))

    story.append(
        Paragraph(
            "Executive Summary",
            styles["Heading2"]
        )
    )

    story.append(
        Paragraph(
            executive_summary.replace("\n", "<br/>"),
            styles["BodyText"]
        )
    )

    story.append(Spacer(1, 12))

    story.append(
        Paragraph(
            "Buyer Protection Score",
            styles["Heading2"]
        )
    )

    story.append(
        Paragraph(
            f"{assessment.buyer_protection_score} "
            f"({assessment.buyer_protection_rating})",
            styles["BodyText"]
        )
    )

    story.append(Spacer(1, 12))

    story.append(
        Paragraph(
            "Key Risks",
            styles["Heading2"]
        )
    )

    for risk in risks:
        story.append(
            Paragraph(
                f"• {risk}",
                styles["BodyText"]
            )
        )

    story.append(Spacer(1, 12))

    story.append(
        Paragraph(
            "Negotiation Guidance",
            styles["Heading2"]
        )
    )

    story.append(
        Paragraph(
            negotiation_text,
            styles["BodyText"]
        )
    )

    story.append(Spacer(1, 12))

    story.append(
        Paragraph(
            "Final Recommendation",
            styles["Heading2"]
        )
    )

    story.append(
        Paragraph(
            assessment.recommendation,
            styles["BodyText"]
        )
    )

    doc.build(story)