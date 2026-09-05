"""Renders the Agent Intelligence consolidated advisory PDF.

Deliberately pure rendering — takes already-fetched data (from the
exact same functions the rest of the app already uses: build_assessment,
_fetch_area_comparison_data, summarize_loan, build_amortization_schedule,
etc., all called by the endpoint in api.py that owns this report) and
lays it out as one PDF. No new analysis happens here, and no external
calls — this module can't accidentally drift from what the rest of the
app actually shows, because it never fetches anything itself.

Uses reportlab, the same real, already-installed dependency
construction_report.py uses — no new library. The page-numbered
footer with real, clickable Privacy/Terms/Refund links reuses that
same module's own proven _NumberedCanvas pattern (a plain
story.append(Paragraph(...)) only ever renders once, wherever it
falls in the flow — it can't be a real per-page footer on its own;
reportlab's own two-pass canvas override is the correct mechanism,
already established and working elsewhere in this app).
"""

import io
from datetime import datetime, timezone
from typing import Any, Optional

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from backend.country_reference import get_country_reference

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
_BULLET_STYLE = ParagraphStyle("AgentBullet", parent=_STYLES["Normal"], fontSize=9.5, textColor=HexColor(_TEXT_DARK), leading=13, spaceAfter=4, leftIndent=12, bulletIndent=0)


# ---------------------------------------------------------------------------
# Page chrome: footer + page numbers on every page, with real, clickable
# Privacy/Terms/Refund links — same proven two-pass pattern as
# construction_report.py's own _NumberedCanvas, adapted to this report's
# own slate/indigo palette.
# ---------------------------------------------------------------------------


class _AgentReportCanvas(Canvas):
    """Standard reportlab two-pass pattern for a genuine 'Page X of Y' —
    the total page count isn't known until the whole document has been
    laid out once, so every page's drawing is buffered and replayed
    once the final count is available."""

    def __init__(self, *args, **kwargs):
        Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
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

        # Plain, styled text rather than a real linkURL annotation --
        # reportlab's two-pass numbered-canvas replay (this exact
        # pattern, already proven in construction_report.py) re-plays
        # each page's saved __dict__ state, which carries a stale
        # annotation-name counter forward and crashes linkURL with
        # "redefining named object" on the second page onward. Shown
        # as the real, full URL instead so it's still genuinely usable
        # by anyone reading a printed or non-interactive copy, which a
        # clickable-only link would not be.
        self.setFillColor(HexColor(_INDIGO))
        self.setFont("Helvetica", 7)
        self.drawString(0.6 * inch, 0.6 * inch, "Privacy Policy · Terms of Service · Refund Policy — app.propertyiqweb.com")

        self.setFillColor(HexColor(_TEXT_MUTED))
        self.setFont("Helvetica-Oblique", 7)
        self.drawCentredString(width / 2, 0.45 * inch, "PropertyIQ Agent Intelligence — for internal advisory use by the preparing agent")


def _make_canvas_factory():
    def factory(*args, **kwargs):
        return _AgentReportCanvas(*args, **kwargs)
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


def build_agent_advisory_pdf(
    *,
    client_name: str,
    property_name: str,
    property_address: str,
    property_country: str,  # drives the checklist/authority-contacts section below
    property_currency: str,  # the property's own real local currency (e.g. "THB" for a Thailand property) -- never assumed to be INR
    assessment: Any,  # the real PropertyAssessment object build_assessment() returns, not a dict
    neighborhood: Optional[dict[str, Any]],
    price_trend: Optional[dict[str, Any]],
    comparison_results: Optional[list[dict[str, Any]]],
    emi_summary: Optional[dict[str, Any]],
    amortization_schedule: Optional[list[dict[str, Any]]],
    cost_of_living: Optional[dict[str, Any]],
    prepared_by: str,  # the agent's real display name if they've set one, else their email — computed by the caller
) -> bytes:
    """Builds the actual PDF bytes. Every section is honest about its
    own source, same standard as the rest of this app — a section with
    no real data for this property is shown as "not available" rather
    than skipped silently or filled in, so the agent (and their
    client) can see exactly what was and wasn't checked."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5 * inch, bottomMargin=0.95 * inch, leftMargin=0.6 * inch, rightMargin=0.6 * inch)
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

    story.append(Paragraph("Amortization Projector", _SECTION_STYLE))
    if amortization_schedule:
        yearly_rows = [row for i, row in enumerate(amortization_schedule) if (i + 1) % 12 == 0 or i == len(amortization_schedule) - 1]
        header_row = [Paragraph(h, _LABEL_STYLE) for h in ["Year", "Payment", "Principal", "Interest", "Balance"]]
        rows = [header_row]
        for row in yearly_rows:
            year_num = -(-row["month"] // 12)  # ceiling division
            rows.append([
                str(year_num),
                f"{property_currency} {row['payment']:,.0f}",
                f"{property_currency} {row['principal_component']:,.0f}",
                f"{property_currency} {row['interest_component']:,.0f}",
                f"{property_currency} {row['remaining_balance']:,.0f}",
            ])
        amort_table = Table(rows, colWidths=[0.7 * inch, 1.4 * inch, 1.4 * inch, 1.4 * inch, 1.4 * inch])
        amort_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, HexColor(_BORDER)),
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#F1F5F9")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        story.append(amort_table)
        story.append(Paragraph("One row per year, for readability — same illustrative loan assumptions as the EMI estimate above.", _MUTED_STYLE))
    else:
        story.append(Paragraph("Not available — the property's quoted price was not usable for an amortization projection.", _MUTED_STYLE))

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

    reference = get_country_reference(property_country)
    if reference["checklist"]:
        story.append(Paragraph("Buyer's Due-Diligence Checklist", _SECTION_STYLE))
        for item in reference["checklist"]:
            story.append(Paragraph(f"☐ {item}", _BULLET_STYLE))

    if reference["authority_contacts"]:
        story.append(Paragraph("Local Authority Contacts", _SECTION_STYLE))
        story.append(_kv_table(reference["authority_contacts"]))

    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "This report consolidates PropertyIQ's own independent, evidence-based analysis tools for internal advisory "
        "use by the preparing agent. It does not constitute a financial, legal, or investment recommendation.",
        _MUTED_STYLE,
    ))

    doc.build(story, canvasmaker=_make_canvas_factory())
    return buffer.getvalue()
