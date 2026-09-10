"""Renders every Agent Intelligence report — the original consolidated
advisory PDF ("Generate Quick Report") plus the 9 named report types
in the agent workspace's Reports panel.

Deliberately built as small, reusable section-builder functions rather
than one monolithic function or 9 separate copy-pasted PDF generators.
Each named report type in REPORT_TYPES is just a different ordered
combination of the same section builders — the report catalog adds no
new data-fetching or business logic of its own, and there is exactly
one place that knows how to render, say, the Price Trends section,
used by every report type that includes it. No new analysis happens
here, and no external calls beyond the agent's own optional logo image
— this module can't drift from what the rest of the app actually shows,
because it never fetches anything else itself.

Uses reportlab, the same real, already-installed dependency
construction_report.py uses — no new library.
"""

import io
import os
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import requests
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

from backend.country_reference import get_country_reference
from backend.report_translations import translate_label

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

# Real Unicode fonts, embedded so Thai/Vietnamese/Indonesian reports
# actually render — confirmed directly (not assumed) that reportlab's
# default base-14 fonts have NO Thai glyph coverage at all: an early
# version of this feature generated a real Thai report and every
# Thai character came out as a solid black box. Fixed by embedding
# Google's own Noto Sans fonts (Thai script coverage for Thai; broad
# Latin+diacritics coverage for Vietnamese/Indonesian). Neither has a
# separate static bold file available upstream, so bold styles reuse
# the same regular-weight file for non-English reports — real,
# readable text without bold emphasis, a deliberate trade-off against
# the alternative (unreadable boxes).
_FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")
_FONT_REGISTERED: dict[str, bool] = {}


def _register_font_once(name: str, filename: str) -> None:
    if _FONT_REGISTERED.get(name):
        return
    pdfmetrics.registerFont(TTFont(name, f"{_FONTS_DIR}/{filename}"))
    _FONT_REGISTERED[name] = True


# language -> (regular font name, bold font name) -- both real,
# registered fonts; English keeps reportlab's own built-in Helvetica.
_FONTS_BY_LANGUAGE: dict[str, tuple[str, str]] = {
    "th": ("NotoSansThai", "NotoSansThai"),
    "vi": ("NotoSans", "NotoSans"),
    "id": ("NotoSans", "NotoSans"),
}


def _get_styles(language: str) -> dict[str, ParagraphStyle]:
    """Builds a fresh, real set of styles for THIS report only --
    never shared module-level mutable state, since a FastAPI sync
    endpoint runs in a threadpool and two agents generating reports in
    different languages at the same time would otherwise be able to
    corrupt each other's fonts mid-request."""
    if language in _FONTS_BY_LANGUAGE:
        regular_name, bold_name = _FONTS_BY_LANGUAGE[language]
        _register_font_once("NotoSansThai", "NotoSansThai-Regular.ttf")
        _register_font_once("NotoSans", "NotoSans-Regular.ttf")
    else:
        regular_name, bold_name = "Helvetica", "Helvetica-Bold"

    return {
        "title": ParagraphStyle("AgentTitle", parent=_STYLES["Title"], fontSize=22, textColor=HexColor("#FFFFFF"), alignment=0, fontName=bold_name),
        "subtitle": ParagraphStyle("AgentSubtitle", parent=_STYLES["Normal"], fontSize=10, textColor=HexColor("#C7D2FE"), fontName=regular_name),
        "section": ParagraphStyle("AgentSection", parent=_STYLES["Heading2"], fontSize=14, textColor=HexColor(_INDIGO), spaceBefore=16, spaceAfter=8, fontName=bold_name),
        "body": ParagraphStyle("AgentBody", parent=_STYLES["Normal"], fontSize=10, textColor=HexColor(_TEXT_DARK), leading=14, fontName=regular_name),
        "muted": ParagraphStyle("AgentMuted", parent=_STYLES["Normal"], fontSize=8.5, textColor=HexColor(_TEXT_MUTED), fontName=regular_name),
        "label": ParagraphStyle("AgentLabel", parent=_STYLES["Normal"], fontSize=9, textColor=HexColor(_TEXT_MUTED), fontName=bold_name),
        "bullet": ParagraphStyle("AgentBullet", parent=_STYLES["Normal"], fontSize=9.5, textColor=HexColor(_TEXT_DARK), leading=13, spaceAfter=4, fontName=regular_name),
    }


# ---------------------------------------------------------------------------
# Page chrome: footer + page numbers on every page, with real, clickable
# Privacy/Terms/Refund links.
# ---------------------------------------------------------------------------

_PRIVACY_URL = "https://app.propertyiqweb.com/privacy-policy.html"
_TERMS_URL = "https://app.propertyiqweb.com/terms-of-service.html"
_REFUND_URL = "https://app.propertyiqweb.com/refund-policy.html"


class _AgentReportCanvas(Canvas):
    """Standard reportlab two-pass pattern for a genuine 'Page X of Y' —
    the total page count isn't known until the whole document has been
    laid out once, so every page's drawing is buffered and replayed
    once the final count is available."""

    def __init__(self, *args, custom_footer_text: Optional[str] = None, **kwargs):
        Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []
        self._custom_footer_text = custom_footer_text

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total_pages = len(self._saved_page_states)
        for page_index, state in enumerate(self._saved_page_states):
            self.__dict__.update(state)
            # _annotationCount is part of the restored __dict__ state
            # above, and every page's saved state shares the same
            # starting value (no footer/links were drawn during the
            # original forward pass) -- replaying page after page would
            # otherwise regenerate the exact same auto-generated
            # annotation name ("NUMBER1", etc.) on every single page,
            # crashing reportlab with "redefining named object" from
            # the second page onward. A real, unique offset per page
            # gives each page's link annotations their own namespace.
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

        # Real, genuinely clickable links -- each page has its own
        # unique annotation-name namespace (see save() above), so
        # linkURL no longer collides across pages during the two-pass
        # replay.
        link_y = 0.6 * inch
        x = 0.6 * inch
        for label, url in [("Privacy Policy", _PRIVACY_URL), ("Terms of Service", _TERMS_URL), ("Refund Policy", _REFUND_URL)]:
            self.setFillColor(HexColor(_INDIGO))
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
        # An agent's own custom footer line, if they've set one,
        # replaces the default -- real, deliberate branding on
        # something handed to their own client, not PropertyIQ's own
        # boilerplate crowding it out.
        default_line = "PropertyIQ Agent Intelligence — for internal advisory use by the preparing agent"
        self.drawCentredString(width / 2, 0.45 * inch, self._custom_footer_text or default_line)


def _make_canvas_factory(custom_footer_text: Optional[str] = None):
    def factory(*args, **kwargs):
        return _AgentReportCanvas(*args, custom_footer_text=custom_footer_text, **kwargs)
    return factory


def _fetch_logo_image(photo_url: Optional[str]) -> Optional[Image]:
    """Real, best-effort fetch of the agent's own logo/photo URL for
    the report header. Deliberately silent on any failure (bad URL,
    unreachable host, not actually an image, oversized file) — a
    logo is a nice-to-have, and a broken external link should never
    take down report generation itself. Capped at a small, fixed
    display size regardless of the source image's real dimensions."""
    if not photo_url:
        return None
    try:
        resp = requests.get(photo_url, timeout=5)
        if resp.status_code != 200 or not resp.headers.get("content-type", "").startswith("image/"):
            return None
        img = Image(io.BytesIO(resp.content))
        img.drawWidth = 0.6 * inch
        img.drawHeight = 0.6 * inch
        return img
    except (requests.RequestException, OSError, ValueError):
        return None


def t(label: str, ctx: dict[str, Any]) -> str:
    """The one place every static section heading/field label in this
    module goes through — real, static dictionary lookup for this
    report's real target language (English if the property's country
    has no translation, e.g. India/Philippines). See
    report_translations.py for the actual translations."""
    return translate_label(label, ctx.get("language", "en"))


def _dt(key: str, fallback: str, ctx: dict[str, Any]) -> str:
    """Same idea as t(), but for the handful of real, dynamically-
    generated narrative strings (the assessment engine's own
    recommendation text, decision narrative, etc.) that a static
    dictionary can't cover — these were translated once, per report,
    via a real Gemini call in _build_agent_report_context (api.py).
    Falls back to the real original English value whenever no
    translation exists for this key (English reports, or a translation
    call that failed) rather than ever showing a blank."""
    return ctx.get("translated_text", {}).get(key) or fallback


def _kv_table(rows: list[tuple[str, str]], styles: dict[str, ParagraphStyle]) -> Table:
    data = [[Paragraph(k, styles["label"]), Paragraph(str(v), styles["body"])] for k, v in rows]
    table = Table(data, colWidths=[2.0 * inch, 4.3 * inch])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, HexColor(_BORDER)),
    ]))
    return table


# ---------------------------------------------------------------------------
# Section builders. Each takes the same shared `ctx` dict (built once by
# the caller in api.py from the real fetched data) and appends its own
# flowables to `story`. Every section is independently honest about its
# own data availability -- a section with no real data for this
# property says so, rather than being silently omitted or invented.
# ---------------------------------------------------------------------------

def _section_header_block(story: list, ctx: dict[str, Any], title: str, subtitle: str) -> None:
    header_table = Table(
        [[Paragraph(title, ctx["styles"]["title"])],
         [Paragraph(subtitle, ctx["styles"]["subtitle"])]],
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

    branding = ctx["branding"]
    logo_image = _fetch_logo_image(branding.get("photo_url"))
    brokerage_suffix = f" ({branding['brokerage_name']})" if branding.get("brokerage_name") else ""
    prepared_by_line = f"{ctx['prepared_by']}{brokerage_suffix}"
    contact_bits = [b for b in [branding.get("contact_phone"), branding.get("contact_email")] if b]
    if contact_bits:
        prepared_by_line += " — " + " · ".join(contact_bits)
    if branding.get("share_slug"):
        prepared_by_line += f"  |  app.propertyiqweb.com/a/{branding['share_slug']}"

    info_rows = [
        (t("Client", ctx), ctx["client_name"]),
        (t("Property", ctx), f"{ctx['property_name']} — {ctx['property_address']}"),
        (t("Prepared by", ctx), prepared_by_line),
        (t("Generated", ctx), datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")),
    ]
    if logo_image:
        info_table = _kv_table(info_rows, ctx["styles"])
        combined = Table([[logo_image, info_table]], colWidths=[0.8 * inch, 5.5 * inch])
        combined.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story.append(combined)
    else:
        story.append(_kv_table(info_rows, ctx["styles"]))


def _section_assessment(story: list, ctx: dict[str, Any]) -> None:
    assessment = ctx["assessment"]
    currency = ctx["property_currency"]
    story.append(Paragraph(t("Property Assessment", ctx), ctx["styles"]["section"]))
    story.append(_kv_table([
        (t("Buyer Protection Score", ctx), f"{assessment.buyer_protection_score:.1f} / 100 ({assessment.buyer_protection_rating})"),
        (t("Recommendation", ctx), _dt("recommendation", assessment.recommendation, ctx)),
        (t("Deal Quality", ctx), t(assessment.deal_quality, ctx)),
        (t("Negotiation Position", ctx), t(assessment.negotiation_position, ctx)),
        (t("Target Price", ctx), f"{currency} {assessment.target_price:,.0f}"),
        (t("Potential Savings", ctx), f"{currency} {assessment.potential_savings:,.0f}"),
    ], ctx["styles"]))


def _section_recommendation(story: list, ctx: dict[str, Any]) -> None:
    """A leaner, focused version of the assessment section — just the
    recommendation and the real reasoning behind it, for a client who
    wants the bottom line without the full data dump."""
    assessment = ctx["assessment"]
    story.append(Paragraph(t("Recommendation", ctx), ctx["styles"]["section"]))
    story.append(_kv_table([
        (t("Recommendation", ctx), _dt("recommendation", assessment.recommendation, ctx)),
        (t("Decision", ctx), f"{assessment.decision.category} — {assessment.decision.action}"),
    ], ctx["styles"]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(_dt("decision_narrative", assessment.decision.narrative, ctx), ctx["styles"]["body"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph(t("Why This Recommendation", ctx), ctx["styles"]["section"]))
    for reason in ctx.get("recommendation_reasons") or []:
        story.append(Paragraph(f"• {reason}", ctx["styles"]["bullet"]))


def _section_neighborhood(story: list, ctx: dict[str, Any]) -> None:
    neighborhood = ctx["neighborhood"]
    story.append(Paragraph(t("Neighborhood Insights", ctx), ctx["styles"]["section"]))
    if not neighborhood:
        story.append(Paragraph(t("Not available for this property — no coordinates were captured for it.", ctx), ctx["styles"]["muted"]))
        return

    resale = neighborhood.get("resale_signal", {})
    infra = neighborhood.get("infrastructure", {})
    overall = neighborhood.get("overall_ranking", {})
    flood = neighborhood.get("flood_risk", {})
    air = neighborhood.get("air_quality", {})
    wb = neighborhood.get("world_bank", {})
    muni = neighborhood.get("municipality_ranking", {})

    story.append(_kv_table([
        (t("Overall Ranking", ctx), f"{overall.get('score')} / 100" if overall.get("has_data") else "Not enough data"),
        (t("Avg. Price/Sqft (resale signal)", ctx), f"{resale.get('currency', '')} {resale.get('average_price_per_sqft', 0):,.0f}" if resale.get("has_data") else "No data"),
        (t("Comparable Listings", ctx), str(resale.get("comparable_count", "—")) if resale.get("has_data") else "—"),
        (t("Infrastructure News", ctx), _dt("infrastructure_summary", infra.get("summary", "No recent news found"), ctx) if infra.get("has_data") else "No recent news found"),
        (t("Flood-Risk Proximity", ctx), f"{flood.get('nearby_water_count')} nearby water body(ies) within 2km" if flood.get("has_data") else "Not available"),
        (t("Air Pollution Index", ctx), f"{air.get('aqi_label')} ({air.get('aqi')}/5) — PM2.5: {air.get('pm2_5')}" if air.get("has_data") else "Not available"),
    ], ctx["styles"]))

    wb_rows = []
    if wb.get("has_data"):
        if wb.get("unemployment_rate"):
            wb_rows.append((t("Job Prospects (unemployment rate)", ctx), f"{wb['unemployment_rate']['value']:.1f}% ({wb['unemployment_rate']['year']})"))
        if wb.get("gdp_growth"):
            wb_rows.append((t("Business Environment (GDP growth)", ctx), f"{wb['gdp_growth']['value']:.1f}% ({wb['gdp_growth']['year']})"))
        if wb.get("tourist_arrivals"):
            wb_rows.append((t("Tourism Index (annual arrivals)", ctx), f"{wb['tourist_arrivals']['value'] / 1_000_000:.1f}M/yr ({wb['tourist_arrivals']['year']})"))
        if wb.get("life_expectancy"):
            wb_rows.append((t("Diseases (life expectancy proxy)", ctx), f"{wb['life_expectancy']['value']:.1f} yrs ({wb['life_expectancy']['year']})"))
    if muni.get("has_data"):
        wb_rows.append((t("Municipality Ranking (Swachh Survekshan)", ctx), f"Rank {muni.get('rank')} of {muni.get('total_cities_ranked')}"))
    if wb_rows:
        story.append(Spacer(1, 4))
        story.append(_kv_table(wb_rows, ctx["styles"]))
    else:
        story.append(Paragraph(t("Country-level indicators (job market, tourism, municipality ranking) not available for this country.", ctx), ctx["styles"]["muted"]))


def _section_price_trends(story: list, ctx: dict[str, Any]) -> None:
    price_trend = ctx["price_trend"]
    story.append(Paragraph(t("Price Trends", ctx), ctx["styles"]["section"]))
    if price_trend and price_trend.get("has_data"):
        first_point = price_trend["points"][0]
        last_point = price_trend["points"][-1]
        change_pct = ((last_point["value"] - first_point["value"]) / first_point["value"]) * 100 if first_point["value"] else 0
        story.append(_kv_table([
            (t("Index (real, country-level)", ctx), price_trend.get("unit", "")),
            (t("Earliest on Record", ctx), f"{first_point['date']}: {first_point['value']:.1f}"),
            (t("Latest on Record", ctx), f"{last_point['date']}: {last_point['value']:.1f}"),
            (t("Change Over Period", ctx), f"{change_pct:+.1f}%"),
        ], ctx["styles"]))
        story.append(Paragraph(f"Source: {price_trend.get('source', 'Bank for International Settlements, via FRED')}. Country-level, not neighborhood-specific.", ctx["styles"]["muted"]))
    else:
        reason = price_trend.get("reason") if price_trend else "no_coordinates"
        message = "No real historical price index exists for this country." if reason == "country_not_covered" else "Not available for this property right now."
        story.append(Paragraph(message, ctx["styles"]["muted"]))


def _comparison_table(comparison_results: list[dict[str, Any]], ctx: dict[str, Any]) -> Table:
    header_row = ["Metric"] + [Paragraph(r["property_name"], ctx["styles"]["label"]) for r in comparison_results]
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

    rows.append([t("Avg. Price/Sqft (resale signal)", ctx)] + [_resale_cell(r) for r in comparison_results])
    rows.append([t("Overall Ranking", ctx)] + [_ranking_cell(r) for r in comparison_results])
    rows.append([t("Flood-Risk Proximity", ctx)] + [_flood_cell(r) for r in comparison_results])

    col_width = min(1.5 * inch, 6.3 * inch / len(header_row))
    comp_table = Table(rows, colWidths=[1.5 * inch] + [col_width] * len(comparison_results))
    comp_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, HexColor(_BORDER)),
        ("BACKGROUND", (0, 0), (-1, 0), HexColor("#F1F5F9")),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
    ]))
    return comp_table


def _section_area_comparison(story: list, ctx: dict[str, Any]) -> None:
    """Neighborhood/location metrics only, across this client's other
    properties -- the "which area is better" view, not full pricing."""
    comparison_results = ctx.get("comparison_results")
    story.append(Paragraph(t("Area Comparison", ctx), ctx["styles"]["section"]))
    if not comparison_results:
        story.append(Paragraph(t("This client has no other properties with captured coordinates to compare against.", ctx), ctx["styles"]["muted"]))
        return
    story.append(_comparison_table(comparison_results, ctx))


def _section_client_property_comparison(story: list, ctx: dict[str, Any]) -> None:
    """The fuller side-by-side: this property's own assessment plus
    the same area-comparison table, for a client weighing multiple of
    their own saved options against each other."""
    _section_assessment(story, ctx)
    story.append(Spacer(1, 8))
    comparison_results = ctx.get("comparison_results")
    story.append(Paragraph(t("Comparison Against This Client's Other Properties", ctx), ctx["styles"]["section"]))
    if not comparison_results:
        story.append(Paragraph(t("This client has no other properties with captured coordinates to compare against.", ctx), ctx["styles"]["muted"]))
        return
    story.append(_comparison_table(comparison_results, ctx))


def _section_financing(story: list, ctx: dict[str, Any]) -> None:
    emi_summary = ctx["emi_summary"]
    currency = ctx["property_currency"]
    story.append(Paragraph(t("Financing Snapshot (EMI Estimate)", ctx), ctx["styles"]["section"]))
    if emi_summary:
        story.append(_kv_table([
            (t("Estimated Monthly EMI", ctx), f"{currency} {emi_summary.get('emi', 0):,.2f}"),
            (t("Total Interest (full tenure)", ctx), f"{currency} {emi_summary.get('total_interest', 0):,.2f}"),
            (t("Total Amount Payable", ctx), f"{currency} {emi_summary.get('total_paid', 0):,.2f}"),
        ], ctx["styles"]))
        story.append(Paragraph(t("Illustrative only, based on the property's quoted price at a default rate/tenure — not a loan offer.", ctx), ctx["styles"]["muted"]))
    else:
        story.append(Paragraph(t("Not available — the property's quoted price was not usable for an EMI estimate.", ctx), ctx["styles"]["muted"]))


def _section_amortization(story: list, ctx: dict[str, Any]) -> None:
    amortization_schedule = ctx["amortization_schedule"]
    currency = ctx["property_currency"]
    story.append(Paragraph(t("Amortization Projector", ctx), ctx["styles"]["section"]))
    if amortization_schedule:
        yearly_rows = [row for i, row in enumerate(amortization_schedule) if (i + 1) % 12 == 0 or i == len(amortization_schedule) - 1]
        header_row = [Paragraph(h, ctx["styles"]["label"]) for h in ["Year", "Payment", "Principal", "Interest", "Balance"]]
        rows = [header_row]
        for row in yearly_rows:
            year_num = -(-row["month"] // 12)  # ceiling division
            rows.append([
                str(year_num),
                f"{currency} {row['payment']:,.0f}",
                f"{currency} {row['principal_component']:,.0f}",
                f"{currency} {row['interest_component']:,.0f}",
                f"{currency} {row['remaining_balance']:,.0f}",
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
        story.append(Paragraph(t("One row per year, for readability — same illustrative loan assumptions as the EMI estimate above.", ctx), ctx["styles"]["muted"]))
    else:
        story.append(Paragraph(t("Not available — the property's quoted price was not usable for an amortization projection.", ctx), ctx["styles"]["muted"]))


def _section_investment_analysis(story: list, ctx: dict[str, Any]) -> None:
    """Price Trends + Financing + Amortization together — the
    investment/financial lens, deliberately without the neighborhood
    or checklist sections that don't bear on the numbers."""
    _section_price_trends(story, ctx)
    story.append(Spacer(1, 8))
    _section_financing(story, ctx)
    story.append(Spacer(1, 8))
    _section_amortization(story, ctx)


def _section_cost_of_living(story: list, ctx: dict[str, Any]) -> None:
    cost_of_living = ctx["cost_of_living"]
    story.append(Paragraph(t("Cost of Living Factors", ctx), ctx["styles"]["section"]))
    if cost_of_living:
        school = cost_of_living.get("school_access", {})
        hospital = cost_of_living.get("hospital_access", {})
        story.append(_kv_table([
            (t("School Access (within 2km)", ctx), f"{school.get('count_within_2km')} school(s) nearby" if school.get("has_data") else "Not available"),
            (t("Hospital Access (within 2km)", ctx), f"{hospital.get('count_within_2km')} hospital(s) nearby" if hospital.get("has_data") else "Not available"),
        ], ctx["styles"]))
        story.append(Paragraph(t("Remaining cost-of-living factors (fuel, tolls, utilities, etc.) have no verified per-area data source and are omitted rather than estimated.", ctx), ctx["styles"]["muted"]))
    else:
        story.append(Paragraph(t("Not available for this property — no coordinates were captured for it.", ctx), ctx["styles"]["muted"]))


def _section_location(story: list, ctx: dict[str, Any]) -> None:
    """Neighborhood + cost of living only — the pure "what's around
    this property" view, without price/assessment content."""
    _section_neighborhood(story, ctx)
    story.append(Spacer(1, 8))
    _section_cost_of_living(story, ctx)


def _section_due_diligence(story: list, ctx: dict[str, Any]) -> None:
    reference = get_country_reference(ctx["property_country"])
    translated = ctx.get("translated_text", {})
    checklist = translated.get("checklist") or reference["checklist"]
    authority_contacts = translated.get("authority_contacts") or reference["authority_contacts"]
    if checklist:
        story.append(Paragraph(t("Buyer's Due-Diligence Checklist", ctx), ctx["styles"]["section"]))
        for item in checklist:
            story.append(Paragraph(f"☐ {item}", ctx["styles"]["bullet"]))
    if authority_contacts:
        story.append(Paragraph(t("Local Authority Contacts", ctx), ctx["styles"]["section"]))
        story.append(_kv_table(authority_contacts, ctx["styles"]))


def _section_handover(story: list, ctx: dict[str, Any]) -> None:
    """A genuinely new section — no equivalent existed anywhere in this
    app before. Real, country-specific post-deal handover items
    (documents, keys, clearances) from country_reference.py's own
    handover_checklist, same honest, static-reference-data reasoning
    as the due-diligence checklist above."""
    reference = get_country_reference(ctx["property_country"])
    story.append(Paragraph(t("Handover Checklist", ctx), ctx["styles"]["section"]))
    items = ctx.get("translated_text", {}).get("handover_checklist") or reference.get("handover_checklist") or []
    if not items:
        story.append(Paragraph(t("No handover checklist is available for this country yet.", ctx), ctx["styles"]["muted"]))
        return
    for item in items:
        story.append(Paragraph(f"☐ {item}", ctx["styles"]["bullet"]))
    story.append(Paragraph(t("Confirm all items above are received and verified before releasing final payment or possession.", ctx), ctx["styles"]["muted"]))


def _section_construction(story: list, ctx: dict[str, Any]) -> None:
    """Honestly gated: this app's Construction Studio designs are not
    yet linked to an agent's own client properties (a genuinely
    separate system today) -- rather than fabricate a design summary
    or silently produce an empty report, this says so plainly."""
    story.append(Paragraph(t("Construction Report", ctx), ctx["styles"]["section"]))
    story.append(Paragraph(
        "This property has no linked Construction Studio design yet. Create one in Construction Studio and link it "
        "to this property to include a construction report here.",
        ctx["styles"]["muted"],
    ))


def _section_disclaimer(story: list, ctx: dict[str, Any]) -> None:
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "This report consolidates PropertyIQ's own independent, evidence-based analysis tools for internal advisory "
        "use by the preparing agent. It does not constitute a financial, legal, or investment recommendation.",
        ctx["styles"]["muted"],
    ))


# ---------------------------------------------------------------------------
# The report catalog: each named report type is a title/subtitle plus an
# ordered list of the section builders above. Adding a new report type
# in the future means adding one entry here, not a new PDF generator.
# ---------------------------------------------------------------------------

_SectionFn = Callable[[list, dict[str, Any]], None]

REPORT_TYPES: dict[str, dict[str, Any]] = {
    "quick": {
        "label": "Quick Report",
        "title": "PROPERTY ADVISORY REPORT",
        "subtitle": "Independent, evidence-based analysis — prepared using PropertyIQ Agent Intelligence",
        "sections": [_section_assessment, _section_neighborhood, _section_price_trends, _section_area_comparison, _section_financing, _section_amortization, _section_cost_of_living, _section_due_diligence],
    },
    "property_intelligence": {
        "label": "Property Intelligence Report",
        "title": "PROPERTY INTELLIGENCE REPORT",
        "subtitle": "A complete, evidence-based view of this property and its surroundings",
        "sections": [_section_assessment, _section_neighborhood, _section_cost_of_living],
    },
    "location": {
        "label": "Location Report",
        "title": "LOCATION REPORT",
        "subtitle": "What's around this property — infrastructure, risk, and livability",
        "sections": [_section_location],
    },
    "area_comparison": {
        "label": "Area Comparison",
        "title": "AREA COMPARISON REPORT",
        "subtitle": "How this property's location compares to this client's other saved properties",
        "sections": [_section_area_comparison],
    },
    "investment_analysis": {
        "label": "Investment Analysis",
        "title": "INVESTMENT ANALYSIS REPORT",
        "subtitle": "Price history, financing, and the full amortization picture",
        "sections": [_section_investment_analysis],
    },
    "buyer_due_diligence": {
        "label": "Buyer Due-Diligence Report",
        "title": "BUYER DUE-DILIGENCE REPORT",
        "subtitle": "What to verify before you buy, and who to contact",
        "sections": [_section_due_diligence],
    },
    "construction": {
        "label": "Construction Report",
        "title": "CONSTRUCTION REPORT",
        "subtitle": "Construction Studio design summary for this property",
        "sections": [_section_construction],
    },
    "client_property_comparison": {
        "label": "Client Property Comparison",
        "title": "CLIENT PROPERTY COMPARISON",
        "subtitle": "This property's own numbers, side by side with this client's other options",
        "sections": [_section_client_property_comparison],
    },
    "recommendation": {
        "label": "Recommendation Report",
        "title": "RECOMMENDATION REPORT",
        "subtitle": "The bottom line, and the real reasoning behind it",
        "sections": [_section_recommendation],
    },
    "handover": {
        "label": "Handover Report",
        "title": "HANDOVER REPORT",
        "subtitle": "What to confirm and collect at final handover",
        "sections": [_section_handover],
    },
}


def build_agent_report_pdf(report_type: str, ctx: dict[str, Any]) -> bytes:
    """ctx carries every piece of real, already-fetched data any
    section might need (assessment, neighborhood, price_trend,
    comparison_results, emi_summary, amortization_schedule,
    cost_of_living, recommendation_reasons, property_country,
    property_currency, client_name, property_name, property_address,
    prepared_by, branding) — built once by the caller in api.py,
    regardless of which report_type was actually requested, so a
    report type that doesn't need a given piece of data simply doesn't
    read that key."""
    report_def = REPORT_TYPES.get(report_type, REPORT_TYPES["quick"])
    ctx = {**ctx, "branding": ctx.get("branding") or {}}
    ctx["styles"] = _get_styles(ctx.get("language", "en"))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5 * inch, bottomMargin=0.95 * inch, leftMargin=0.6 * inch, rightMargin=0.6 * inch)
    story: list = []

    _section_header_block(story, ctx, report_def["title"], report_def["subtitle"])
    for section_fn in report_def["sections"]:
        section_fn(story, ctx)
    _section_disclaimer(story, ctx)

    doc.build(story, canvasmaker=_make_canvas_factory(ctx["branding"].get("custom_footer_text")))
    return buffer.getvalue()


def build_agent_advisory_pdf(**kwargs) -> bytes:
    """Backwards-compatible wrapper for the original "Generate Quick
    Report" call site — same real keyword arguments as before, routed
    through the new build_agent_report_pdf("quick", ctx) path so the
    quick report and the 9 named report types share one real
    implementation, not two."""
    ctx = {
        "client_name": kwargs["client_name"],
        "property_name": kwargs["property_name"],
        "property_address": kwargs["property_address"],
        "property_country": kwargs["property_country"],
        "property_currency": kwargs["property_currency"],
        "assessment": kwargs["assessment"],
        "neighborhood": kwargs["neighborhood"],
        "price_trend": kwargs["price_trend"],
        "comparison_results": kwargs["comparison_results"],
        "emi_summary": kwargs["emi_summary"],
        "amortization_schedule": kwargs["amortization_schedule"],
        "cost_of_living": kwargs["cost_of_living"],
        "prepared_by": kwargs["prepared_by"],
        "branding": kwargs.get("branding"),
        "recommendation_reasons": kwargs.get("recommendation_reasons"),
        "language": kwargs.get("language", "en"),
        "translated_text": kwargs.get("translated_text", {}),
    }
    return build_agent_report_pdf("quick", ctx)
