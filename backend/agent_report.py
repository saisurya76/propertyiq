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
    property_currency: str,  # the property's own real local currency (e.g. "THB" for a Thailand property) -- never assumed to be INR
    assessment: Any,  # the real PropertyAssessment object build_assessment() returns, not a dict
    neighborhood: Optional[dict[str, Any]],
    price_trend: Optional[dict[str, Any]],
    comparison_results: Optional[list[dict[str, Any]]],
    emi_summary: Optional[dict[str, Any]],
    cost_of_living: Optional[dict[str, Any]],
    prepared_by: str,  # the agent's real display name if they've set one, else their email — computed by the caller
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
        ("Prepared by", prepared_by),
        ("Generated", datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")),
    ]))

    story.append(Paragraph("Property Assessment", _SECTION_STYLE))
    story.append(_kv_table([
        ("Buyer Protection Score", f"{assessment.buyer_protection_score:.1f} / 100 ({assessment.buyer_protection_rating})"),
        ("Recommendation", assessment.recommendation),
        ("Deal Quality", assessment.deal_quality),
        ("Negotiation Position", assessment.negotiation_position),
        ("Target Price", f"{property_currency} {assessment.target_price:,.0f}"),
        ("Potential Savings", f"{property_currency} {assessment.potential_savings:,.0f}"),
    ]))

    story.append(Paragraph("Neighborhood Insights", _SECTION_STYLE))
    if neighborhood:
        resale = neighborhood.get("resale_signal", {})
        infra = neighborhood.get("infrastructure", {})
        overall = neighborhood.get("overall_ranking", {})
        flood = neighborhood.get("flood_risk", {})
        air = neighborhood.get("air_quality", {})
        wb = neighborhood.get("world_bank", {})
        muni = neighborhood.get("municipality_ranking", {})

        story.append(_kv_table([
            ("Overall Ranking", f"{overall.get('score')} / 100" if overall.get("has_data") else "Not enough data"),
            ("Avg. Price/Sqft (resale signal)", f"{resale.get('currency', '')} {resale.get('average_price_per_sqft', 0):,.0f}" if resale.get("has_data") else "No data"),
            ("Comparable Listings", str(resale.get("comparable_count", "—")) if resale.get("has_data") else "—"),
            ("Infrastructure News", infra.get("summary", "No recent news found") if infra.get("has_data") else "No recent news found"),
            ("Flood-Risk Proximity", f"{flood.get('nearby_water_count')} nearby water body(ies) within 2km" if flood.get("has_data") else "Not available"),
            ("Air Pollution Index", f"{air.get('aqi_label')} ({air.get('aqi')}/5) — PM2.5: {air.get('pm2_5')}" if air.get("has_data") else "Not available"),
        ]))

        wb_rows = []
        if wb.get("has_data"):
            if wb.get("unemployment_rate"):
                wb_rows.append(("Job Prospects (unemployment rate)", f"{wb['unemployment_rate']['value']:.1f}% ({wb['unemployment_rate']['year']})"))
            if wb.get("gdp_growth"):
                wb_rows.append(("Business Environment (GDP growth)", f"{wb['gdp_growth']['value']:.1f}% ({wb['gdp_growth']['year']})"))
            if wb.get("tourist_arrivals"):
                wb_rows.append(("Tourism Index (annual arrivals)", f"{wb['tourist_arrivals']['value'] / 1_000_000:.1f}M/yr ({wb['tourist_arrivals']['year']})"))
            if wb.get("life_expectancy"):
                wb_rows.append(("Diseases (life expectancy proxy)", f"{wb['life_expectancy']['value']:.1f} yrs ({wb['life_expectancy']['year']})"))
        if muni.get("has_data"):
            wb_rows.append(("Municipality Ranking (Swachh Survekshan)", f"Rank {muni.get('rank')} of {muni.get('total_cities_ranked')}"))
        if wb_rows:
            story.append(Spacer(1, 4))
            story.append(_kv_table(wb_rows))
        else:
            story.append(Paragraph("Country-level indicators (job market, tourism, municipality ranking) not available for this country.", _MUTED_STYLE))
    else:
        story.append(Paragraph("Not available for this property — no coordinates were captured for it.", _MUTED_STYLE))

    story.append(Paragraph("Price Trends", _SECTION_STYLE))
    if price_trend and price_trend.get("has_data"):
        first_point = price_trend["points"][0]
        last_point = price_trend["points"][-1]
        change_pct = ((last_point["value"] - first_point["value"]) / first_point["value"]) * 100 if first_point["value"] else 0
        story.append(_kv_table([
            ("Index (real, country-level)", price_trend.get("unit", "")),
            ("Earliest on Record", f"{first_point['date']}: {first_point['value']:.1f}"),
            ("Latest on Record", f"{last_point['date']}: {last_point['value']:.1f}"),
            ("Change Over Period", f"{change_pct:+.1f}%"),
        ]))
        story.append(Paragraph(f"Source: {price_trend.get('source', 'Bank for International Settlements, via FRED')}. Country-level, not neighborhood-specific.", _MUTED_STYLE))
    else:
        reason = price_trend.get("reason") if price_trend else "no_coordinates"
        message = "No real historical price index exists for this country." if reason == "country_not_covered" else "Not available for this property right now."
        story.append(Paragraph(message, _MUTED_STYLE))

    if comparison_results:
        story.append(Paragraph("Comparison Against This Client's Other Properties", _SECTION_STYLE))
        header_row = ["Metric"] + [Paragraph(r["property_name"], _LABEL_STYLE) for r in comparison_results]
        rows = [header_row]

        def _resale_cell(r):
            resale = r.get("resale_signal", {})
            return f"{resale.get('currency', '')} {resale.get('average_price_per_sqft', 0):,.0f}/sqft" if resale.get("has_data") else "No data"

        def _ranking_cell(r):
            ranking = r.get("overall_ranking", {})
            return f"{ranking.get('score')} / 100" if ranking.get("has_data") else "Not enough data"

        def _flood_cell(r):
            flood = r.get("flood_risk", {})
            return f"{flood.get('nearby_water_count')} nearby" if flood.get("has_data") else "Not available"

        rows.append(["Avg. Price/Sqft"] + [_resale_cell(r) for r in comparison_results])
        rows.append(["Overall Ranking"] + [_ranking_cell(r) for r in comparison_results])
        rows.append(["Flood-Risk Proximity"] + [_flood_cell(r) for r in comparison_results])

        col_width = min(1.5 * inch, 6.3 * inch / len(header_row))
        comp_table = Table(rows, colWidths=[1.5 * inch] + [col_width] * len(comparison_results))
        comp_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, HexColor(_BORDER)),
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#F1F5F9")),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ]))
        story.append(comp_table)
        story.append(Spacer(1, 8))

    story.append(Paragraph("Financing Snapshot (EMI Estimate)", _SECTION_STYLE))
    if emi_summary:
        story.append(_kv_table([
            ("Estimated Monthly EMI", f"{property_currency} {emi_summary.get('emi', 0):,.2f}"),
            ("Total Interest (full tenure)", f"{property_currency} {emi_summary.get('total_interest', 0):,.2f}"),
            ("Total Amount Payable", f"{property_currency} {emi_summary.get('total_paid', 0):,.2f}"),
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
