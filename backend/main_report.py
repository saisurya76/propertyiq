"""Renders the main homepage's "Download PropertyIQ Report" PDF.

This replaces the old backend/renderers/pdf_renderer.py, which was
built against an older, smaller shape of the assessment result and
never updated as the live AssessmentResult.jsx page grew — confirmed
directly by comparing the two field lists, which is why the download
button was disabled (a genuinely stale, incomplete PDF next to a rich,
current live page). This module renders straight from the exact same
PropertyAssessment object the live page's own /assess endpoint already
returns — one real source of truth, so the two can't drift apart again.

Deliberately does NOT attempt to reproduce the live page's visual fraud
heatmap (a static PDF can't show an interactive heatmap meaningfully)
— shown instead as an honest, real count of applicable fraud risk
types, with a pointer back to the live report for the full detail.

Uses reportlab, the same real, already-installed dependency
agent_report.py and construction_report.py already use.
"""

import io
from datetime import datetime, timezone
from typing import Any

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

# Distinct from both Construction Studio's amber/navy report and Agent
# Intelligence's slate/indigo/emerald — this is PropertyIQ's own core,
# public-facing report, using the same navy the homepage hero itself
# already uses, so it reads as "the same product," not a third
# separate visual identity.
_NAVY = "#0B2545"
_GOLD = "#F4A300"
_BORDER = "#E2E8F0"
_TEXT_MUTED = "#64748B"
_TEXT_DARK = "#0F172A"

_STYLES = getSampleStyleSheet()
_TITLE_STYLE = ParagraphStyle("MainTitle", parent=_STYLES["Title"], fontSize=22, textColor=HexColor("#FFFFFF"), alignment=0, fontName="Helvetica-Bold")
_SUBTITLE_STYLE = ParagraphStyle("MainSubtitle", parent=_STYLES["Normal"], fontSize=10, textColor=HexColor("#CBD5E1"))
_SECTION_STYLE = ParagraphStyle("MainSection", parent=_STYLES["Heading2"], fontSize=14, textColor=HexColor(_NAVY), spaceBefore=16, spaceAfter=8, fontName="Helvetica-Bold")
_BODY_STYLE = ParagraphStyle("MainBody", parent=_STYLES["Normal"], fontSize=10, textColor=HexColor(_TEXT_DARK), leading=14)
_MUTED_STYLE = ParagraphStyle("MainMuted", parent=_STYLES["Normal"], fontSize=8.5, textColor=HexColor(_TEXT_MUTED))
_LABEL_STYLE = ParagraphStyle("MainLabel", parent=_STYLES["Normal"], fontSize=9, textColor=HexColor(_TEXT_MUTED), fontName="Helvetica-Bold")
_BULLET_STYLE = ParagraphStyle("MainBullet", parent=_STYLES["Normal"], fontSize=9.5, textColor=HexColor(_TEXT_DARK), leading=13, spaceAfter=4)

_PRIVACY_URL = "https://app.propertyiqweb.com/privacy-policy.html"
_TERMS_URL = "https://app.propertyiqweb.com/terms-of-service.html"
_REFUND_URL = "https://app.propertyiqweb.com/refund-policy.html"


class _MainReportCanvas(Canvas):
    """Same real, proven two-pass numbered-canvas pattern as
    agent_report.py's own _AgentReportCanvas (see that module's own
    comments for the real reportlab annotation-collision bug this
    works around) — genuine "Page X of Y" plus real, clickable
    Privacy/Terms/Refund links on every page."""

    def __init__(self, *args, **kwargs):
        Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self._saved_page_states)
        for page_index, state in enumerate(self._saved_page_states):
            self.__dict__.update(state)
            self._annotationCount = page_index * 1000
            self._draw_footer(total_pages)
            Canvas.showPage(self)
        Canvas.save(self)

    def _draw_footer(self, total_pages: int) -> None:
        width, _ = letter
        self.setStrokeColor(HexColor(_BORDER))
        self.setLineWidth(0.5)
        self.line(0.6 * inch, 0.78 * inch, width - 0.6 * inch, 0.78 * inch)

        self.setFillColor(HexColor(_TEXT_MUTED))
        self.setFont("Helvetica", 7.5)
        self.drawRightString(width - 0.6 * inch, 0.6 * inch, f"Page {self._pageNumber} of {total_pages}")

        link_y = 0.6 * inch
        x = 0.6 * inch
        for label, url in [("Privacy Policy", _PRIVACY_URL), ("Terms of Service", _TERMS_URL), ("Refund Policy", _REFUND_URL)]:
            self.setFillColor(HexColor(_NAVY))
            self.setFont("Helvetica", 7.5)
            text_width = self.stringWidth(label, "Helvetica", 7.5)
            self.drawString(x, link_y, label)
            self.linkURL(url, (x, link_y - 1, x + text_width, link_y + 8), relative=0)
            x += text_width
            if url != _REFUND_URL:
                self.setFillColor(HexColor(_TEXT_MUTED))
                self.drawString(x, link_y, "  ·  ")
                x += self.stringWidth("  ·  ", "Helvetica", 7.5)

        self.setFillColor(HexColor(_TEXT_MUTED))
        self.setFont("Helvetica-Oblique", 7)
        self.drawCentredString(width / 2, 0.45 * inch, "PropertyIQ — Independent Property Intelligence")


def _make_canvas_factory():
    def factory(*args, **kwargs):
        return _MainReportCanvas(*args, **kwargs)
    return factory


def _kv_table(rows: list[tuple[str, str]]) -> Table:
    data = [[Paragraph(k, _LABEL_STYLE), Paragraph(str(v), _BODY_STYLE)] for k, v in rows]
    table = Table(data, colWidths=[2.0 * inch, 4.3 * inch])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, HexColor(_BORDER)),
    ]))
    return table


def build_main_property_report_pdf(assessment: Any, recommendation_reasons: list[str], currency: str = "INR") -> bytes:
    """assessment is the real PropertyAssessment object build_assessment()
    returns — the exact same object the live /assess endpoint already
    builds its JSON response from. Rendering directly from it (rather
    than a second, hand-maintained copy of the same numbers) is what
    keeps this PDF from ever drifting from the live page again."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5 * inch, bottomMargin=0.95 * inch, leftMargin=0.6 * inch, rightMargin=0.6 * inch)
    story = []

    header_table = Table(
        [[Paragraph("PROPERTYIQ REPORT", _TITLE_STYLE)],
         [Paragraph("Independent, Evidence-Based Property Intelligence", _SUBTITLE_STYLE)]],
        colWidths=[6.3 * inch],
    )
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor(_NAVY)),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 14),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 16))

    story.append(_kv_table([
        ("Property", f"{assessment.property_name} — {assessment.city}, {assessment.state_province}, {assessment.country}"),
        ("Developer", assessment.developer_name),
        ("Property Type", assessment.property_type),
        ("Generated", datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")),
    ]))

    story.append(Paragraph("Buyer Protection Score & Recommendation", _SECTION_STYLE))
    story.append(_kv_table([
        ("Buyer Protection Score", f"{assessment.buyer_protection_score:.1f} / 100 ({assessment.buyer_protection_rating})"),
        ("Recommendation", assessment.recommendation),
        ("Decision", f"{assessment.decision.category} — {assessment.decision.action}"),
    ]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(assessment.decision.narrative, _BODY_STYLE))

    story.append(Paragraph("Valuation", _SECTION_STYLE))
    story.append(_kv_table([
        ("Quoted Price", f"{currency} {assessment.quoted_price:,.0f} ({currency} {assessment.quoted_price_per_sqft:,.0f}/sqft)"),
        ("Fair Value", f"{currency} {assessment.fair_value:,.0f} ({currency} {assessment.fair_value_per_sqft:,.0f}/sqft)"),
        ("Overpricing", f"{assessment.overpricing_percent:+.1f}%"),
        ("Market Average", f"{currency} {assessment.market_average_price_per_sqft:,.0f}/sqft"),
        ("Deal Quality", f"{assessment.deal_quality} — {assessment.deal_quality_reason}"),
    ]))

    story.append(Paragraph("Negotiation Guidance", _SECTION_STYLE))
    story.append(_kv_table([
        ("Position", f"{assessment.negotiation_position} — {assessment.negotiation_reason}"),
        ("Target Price", f"{currency} {assessment.target_price:,.0f}"),
        ("Suggested Offer Range", f"{currency} {assessment.low_offer:,.0f} – {currency} {assessment.high_offer:,.0f}"),
        ("Potential Savings", f"{currency} {assessment.potential_savings:,.0f}"),
    ]))

    story.append(Paragraph("Buyer Advantage & Confidence", _SECTION_STYLE))
    story.append(_kv_table([
        ("Buyer Advantage", f"{assessment.buyer_advantage_score:.1f} / 100 ({assessment.buyer_advantage_rating})"),
        ("Reason", assessment.buyer_advantage_reason),
        ("Recommendation Confidence", f"{assessment.recommendation_confidence_score:.1f} / 100 ({assessment.recommendation_confidence_rating})"),
        ("Reason", assessment.recommendation_confidence_reason),
    ]))

    story.append(Paragraph("Why This Recommendation", _SECTION_STYLE))
    for reason in recommendation_reasons:
        story.append(Paragraph(f"• {reason}", _BULLET_STYLE))

    story.append(Paragraph("Findings", _SECTION_STYLE))
    story.append(_kv_table([
        ("Pricing", assessment.findings.pricing_finding),
        ("Inventory", assessment.findings.inventory_finding),
        ("Developer", assessment.findings.developer_finding),
        ("Overall", assessment.findings.overall_finding),
    ]))

    story.append(Paragraph("Developer & Inventory Risk", _SECTION_STYLE))
    story.append(_kv_table([
        ("Developer Rating", assessment.developer_rating),
        ("Inventory Risk", assessment.inventory_risk),
    ]))

    gi = assessment.government_intelligence
    story.append(Paragraph("Government Reference Intelligence", _SECTION_STYLE))
    story.append(_kv_table([
        ("Government Rate", f"{currency} {gi.government_rate_per_unit:,.0f}/sqft"),
        ("Government Property Value", f"{currency} {gi.government_property_value:,.0f}"),
        ("Reference", gi.reference_name),
        ("Confidence", gi.confidence),
        ("Note", gi.buyer_observation),
    ]))
    story.append(Paragraph(gi.disclaimer, _MUTED_STYLE))

    if assessment.comparables:
        story.append(Paragraph("Comparable Projects", _SECTION_STYLE))
        rows = [(c.project_name, f"{c.developer} — {currency} {c.price_per_sqft:,.0f}/sqft") for c in assessment.comparables]
        story.append(_kv_table(rows))

    fraud = assessment.fraud_intelligence
    applicable_city = sum(1 for item in fraud.city if item.applicable)
    applicable_country = sum(1 for item in fraud.country if item.applicable)
    story.append(Paragraph("Fraud Risk Intelligence", _SECTION_STYLE))
    story.append(_kv_table([
        ("Applicable City-Level Risk Types", str(applicable_city)),
        ("Applicable Country-Level Risk Types", str(applicable_country)),
        ("Report ID", fraud.status.report_id),
    ]))
    story.append(Paragraph(
        "The full, interactive fraud risk atlas (heat maps and detailed evidence sources) is available on the live "
        "PropertyIQ report — this PDF summarizes the applicable risk counts only.",
        _MUTED_STYLE,
    ))

    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "This report is generated by PropertyIQ's independent, evidence-based analysis engine. It does not "
        "constitute a financial, legal, or investment recommendation.",
        _MUTED_STYLE,
    ))

    doc.build(story, canvasmaker=_make_canvas_factory())
    return buffer.getvalue()
