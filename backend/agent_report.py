"""Renders the Agent Intelligence consolidated advisory PDF.

Deliberately pure rendering — takes already-fetched data (from the
exact same functions the rest of the app already uses: build_assessment,
_fetch_area_comparison_data, summarize_loan, etc., all called by the
endpoint in api.py that owns this report) and lays it out as one PDF.
No new analysis happens here, and no external calls — this module
can't accidentally drift from what the rest of the app actually shows,
because it never fetches anything itself.

Uses reportlab, the same real, already-installed dependency
construction_report.py uses — no new library.
"""

import io
from datetime import datetime, timezone
from typing import Any, Optional

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

# A distinct palette from Construction Studio's own amber/navy report —
# slate + indigo + emerald, meant to read as "professional business
# tool," matching the Analyze -> Advise -> Monetize framing this
# feature was built around, not a re-skin of an existing report.
_SLATE = "#1E293B"
_INDIGO = "#4F46E5"
_EMERALD = "#059669"
_BORDER = "#E2E8F0"
_TEXT_MUTED = "#64748B"
_TEXT_DARK = "#0F172A"

_STYLES = getSampleStyleSheet()
_TITLE_STYLE = ParagraphStyle("AgentTitle", parent=_STYLES["Title"], fontSize=22, textColor=HexColor("#FFFFFF"), alignment=0, fontName="Helvetica-Bold")
_SUBTITLE_STYLE = ParagraphStyle("AgentSubtitle", parent=_STYLES["Normal"], fontSize=10, textColor=HexColor("#C7D2FE"))
_SECTION_STYLE = ParagraphStyle("AgentSection", parent=_STYLES["Heading2"], fontSize=14, textColor=HexColor(_INDIGO), spaceBefore=16, spaceAfter=8, fontName="Helvetica-Bold")
_BODY_STYLE = ParagraphStyle("AgentBody", parent=_STYLES["Normal"], fontSize=10, textColor=HexColor(_TEXT_DARK), leading=14)
_MUTED_STYLE = ParagraphStyle("AgentMuted", parent=_STYLES["Normal"], fontSize=8.5, textColor=HexColor(_TEXT_MUTED))
_LABEL_STYLE = ParagraphStyle("AgentLabel", parent=_STYLES["Normal"], fontSize=9, textColor=HexColor(_TEXT_MUTED), fontName="Helvetica-Bold")


def _kv_table(rows: list[tuple[str, str]]) -> Table:
    data = [[Paragraph(k, _LABEL_STYLE), Paragraph(str(v), _BODY_STYLE)] for k, v in rows]
    table = Table(data, colWidths=[2.0 * inch, 4.3 * inch])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, HexColor(_BORDER)),
    ]))
    return table


def build_agent_advisory_pdf(
    *,
    client_name: str,
    property_name: str,
    property_address: str,
    assessment: Any,  # the real PropertyAssessment object build_assessment() returns, not a dict
    neighborhood: Optional[dict[str, Any]],
    emi_summary: Optional[dict[str, Any]],
    cost_of_living: Optional[dict[str, Any]],
    agent_email: str,
) -> bytes:
    """Builds the actual PDF bytes. Every section is honest about its
    own source, same standard as the rest of this app — a section with
    no real data for this property is shown as "not available" rather
    than skipped silently or filled in, so the agent (and their
    client) can see exactly what was and wasn't checked."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5 * inch, bottomMargin=0.6 * inch, leftMargin=0.6 * inch, rightMargin=0.6 * inch)
    story = []

    header_table = Table(
        [[Paragraph("PROPERTYIQ AGENT INTELLIGENCE", _TITLE_STYLE)],
         [Paragraph("Consolidated Advisory Report — Analyze · Advise · Monetize", _SUBTITLE_STYLE)]],
        colWidths=[6.3 * inch],
    )
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor(_SLATE)),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 14),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 16))

    story.append(_kv_table([
        ("Client", client_name),
        ("Property", f"{property_name} — {property_address}"),
        ("Prepared by", agent_email),
        ("Generated", datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")),
    ]))

    story.append(Paragraph("Property Assessment", _SECTION_STYLE))
    story.append(_kv_table([
        ("Buyer Protection Score", f"{assessment.buyer_protection_score:.1f} / 100 ({assessment.buyer_protection_rating})"),
        ("Recommendation", assessment.recommendation),
        ("Deal Quality", assessment.deal_quality),
        ("Negotiation Position", assessment.negotiation_position),
        ("Target Price", f"{assessment.target_price:,.0f}"),
        ("Potential Savings", f"{assessment.potential_savings:,.0f}"),
    ]))

    story.append(Paragraph("Neighborhood Insights", _SECTION_STYLE))
    if neighborhood:
        resale = neighborhood.get("resale_signal", {})
        infra = neighborhood.get("infrastructure", {})
        overall = neighborhood.get("overall_ranking", {})
        story.append(_kv_table([
            ("Overall Ranking", f"{overall.get('score')} / 100" if overall.get("has_data") else "Not enough data"),
            ("Avg. Price/Sqft (resale signal)", f"{resale.get('currency', '')} {resale.get('average_price_per_sqft', 0):,.0f}" if resale.get("has_data") else "No data"),
            ("Comparable Listings", str(resale.get("comparable_count", "—")) if resale.get("has_data") else "—"),
            ("Infrastructure News", infra.get("summary", "No recent news found") if infra.get("has_data") else "No recent news found"),
        ]))
    else:
        story.append(Paragraph("Not available for this property — no coordinates were captured for it.", _MUTED_STYLE))

    story.append(Paragraph("Financing Snapshot (EMI Estimate)", _SECTION_STYLE))
    if emi_summary:
        story.append(_kv_table([
            ("Estimated Monthly EMI", f"{emi_summary.get('emi', 0):,.2f}"),
            ("Total Interest (full tenure)", f"{emi_summary.get('total_interest', 0):,.2f}"),
            ("Total Amount Payable", f"{emi_summary.get('total_paid', 0):,.2f}"),
        ]))
        story.append(Paragraph("Illustrative only, based on the property's quoted price at a default rate/tenure — not a loan offer.", _MUTED_STYLE))
    else:
        story.append(Paragraph("Not available — the property's quoted price was not usable for an EMI estimate.", _MUTED_STYLE))

    story.append(Paragraph("Cost of Living Factors", _SECTION_STYLE))
    if cost_of_living:
        school = cost_of_living.get("school_access", {})
        hospital = cost_of_living.get("hospital_access", {})
        story.append(_kv_table([
            ("School Access (within 2km)", f"{school.get('count_within_2km')} school(s) nearby" if school.get("has_data") else "Not available"),
            ("Hospital Access (within 2km)", f"{hospital.get('count_within_2km')} hospital(s) nearby" if hospital.get("has_data") else "Not available"),
        ]))
        story.append(Paragraph("Remaining cost-of-living factors (fuel, tolls, utilities, etc.) have no verified per-area data source and are omitted rather than estimated.", _MUTED_STYLE))
    else:
        story.append(Paragraph("Not available for this property — no coordinates were captured for it.", _MUTED_STYLE))

    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "This report consolidates PropertyIQ's own independent, evidence-based analysis tools for internal advisory "
        "use by the preparing agent. It does not constitute a financial, legal, or investment recommendation.",
        _MUTED_STYLE,
    ))

    doc.build(story)
    return buffer.getvalue()
