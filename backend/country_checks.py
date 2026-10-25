"""Guided developer/title checks for the non-India country sites.

Same honest approach as backend/rera.py: we never say a project, developer or
title is "verified". We point to the official registry, give a checklist of what
to confirm there, and run a few rule-based observations on what the visitor
typed. Rules below come from published summaries of each country's law and
carry a "confirm with a local lawyer" line, because laws change."""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from backend.config_store import get_app_setting, set_app_setting
from backend.rera import DISCLAIMER as _IN_DISCLAIMER  # noqa: F401  (kept for parity)

LINK_OVERRIDES_KEY = "country_link_urls"

LAWYER_LINE = (
    "This is a guide, not legal advice or a verification. PropertyIQ cannot confirm that any "
    "licence, title or registration is genuine, and rules change. Confirm each point with the "
    "official registry and a licensed local lawyer before paying any money."
)

# country code -> config. links: (key, label, default url). Only links whose
# address was confirmed in the sources used; admin can correct any of them.
COUNTRIES: dict[str, dict[str, Any]] = {
    "TH": {
        "name": "Thailand",
        "title": "Developer & Title Check",
        "number_label": "Title deed number (optional)",
        "number_hint": "From the title deed or sales document",
        "lead": "Thailand has no RERA. Check the land title at the Department of Lands, the developer company at the DBD, and the contract before you pay.",
        "links": [
            ("land_dept", "Department of Lands (title and registration)", "https://www.dol.go.th/"),
            ("dbd", "DBD company records (developer check)", "https://ebiz.dbd.go.th/eservice-web/"),
        ],
        "checklist": [
            "Get a current Land Department search on the specific plot or unit: registered owner, title type, mortgages, court orders, access.",
            "Check the developer company on the DBD e-service: registered name, directors, filed financial statements and shareholders.",
            "For a condo, get written confirmation that foreign ownership is within the 49% quota of the building.",
            "Check the condominium registration, the juristic person, fee arrears and the building rules.",
            "Ask for the EIA approval and building permits where they apply, and confirm they match the project and plot.",
            "Move every brochure or chat promise into the signed contract or its annexes: specifications, completion date, delay and refund terms.",
            "Avoid large non-refundable payments before a lawyer has reviewed the title and the draft agreement.",
            "For foreign buyers of a freehold condo, funds must come from abroad in foreign currency, and the bank's Foreign Exchange Transaction Form is needed at the Land Office.",
            "Inspect the unit one to two weeks before handover and get defects fixed before paying the balance.",
        ],
    },
    "PH": {
        "name": "Philippines",
        "title": "Developer & Title Check",
        "number_label": "License to Sell (LTS) number",
        "number_hint": "Ask the seller for it; no number is a red flag",
        "lead": "In the Philippines the key check is the developer's License to Sell from DHSUD. Do not pay a reservation for a project that has no LTS.",
        "links": [
            ("lts", "DHSUD list of projects with a License to Sell", "https://dhsud.gov.ph/list-of-license-to-sell/"),
            ("lra", "Land Registration Authority (title records)", "https://lra.gov.ph"),
        ],
        "checklist": [
            "Search the project on the DHSUD list of projects with a License to Sell, and check it is for this project, phase or tower.",
            "A Certificate of Registration alone does not allow sales. Both the Certificate of Registration and the License to Sell are needed.",
            "Check DHSUD's list of cease and desist orders for the project or developer.",
            "Get a certified true copy of the land or condominium title from the Registry of Deeds. Check for mortgages, liens and adverse claims.",
            "Ask for the approved plans and permits, the contract to sell and, for a condominium, the master deed and declaration of restrictions.",
            "If an agent is involved, ask for the developer's written authority plus the broker's or salesperson's credentials.",
            "Pay only the developer's formally named payee and account. Avoid cash, personal accounts, and cheques payable to agents.",
            "Do not pay a reservation on a promise that the licence will follow. Keep every receipt.",
            "Check that promised facilities are written into the contract; advertised facilities can count as warranties.",
        ],
    },
    "VN": {
        "name": "Vietnam",
        "title": "Developer & Title Check",
        "number_label": "Project or legal document number (optional)",
        "number_hint": "For example the number on the sales eligibility notice",
        "lead": "In Vietnam, check that the project is legally allowed to sell before you hand over a deposit, and keep deposits and stage payments within the legal caps.",
        "links": [
            ("moc", "Ministry of Construction (find your provincial Department of Construction)", "https://moc.gov.vn"),
        ],
        "checklist": [
            "Ask for the investor's legal documents and check the project is eligible to be sold off-plan; confirm with the provincial Department of Construction.",
            "Check the land-use right and project legal status for this exact plot, and whether the land is mortgaged.",
            "Ask whether the investor provides a bank guarantee for its obligations if the property is not delivered. Under the 2023 law the buyer may choose whether to require one.",
            "Make sure payments go to the investor's bank account only, and keep the transfer records.",
            "Check the deposit and stage payments against the legal caps (see the observations below).",
            "Read the sale contract for handover date, delay penalties, area, finishing standards and the date the ownership certificate (pink book) is issued.",
            "Check the investor's track record on other projects, and any disputes or delays reported publicly.",
            "Foreign buyers: check the quota rules for apartments and landed housing in the building, and the ownership term.",
        ],
    },
    "ID": {
        "name": "Indonesia",
        "title": "Developer & Title Check",
        "number_label": "Certificate number (NIB / certificate) (optional)",
        "number_hint": "From the land certificate",
        "lead": "In Indonesia the land certificate type decides what you can own. Check it with the land agency (ATR/BPN) and have a PPAT notary review everything.",
        "links": [
            ("bhumi", "BHUMI (ATR/BPN land locations and plot details)", "https://bhumi.atrbpn.go.id"),
            ("gistaru", "GISTARU (ATR/BPN zoning maps)", "https://gistaru.atrbpn.go.id"),
        ],
        "checklist": [
            "Have a PPAT notary check the certificate: the true owner, that it is not in dispute, and that it matches the plot.",
            "Check the plot and certificate on ATR/BPN's BHUMI site or its Sentuh Tanahku app (both are in Bahasa Indonesia).",
            "Check the zoning on GISTARU to confirm your intended use is allowed.",
            "Check the building permit (PBG, formerly IMB) and that it matches the building you are buying.",
            "Check for unpaid property tax or other debts attached to the land.",
            "Pending court cases are not shown online; ask at ATR/BPN or the district court.",
            "Pay by traceable bank transfer or escrow, declare incoming funds, and keep records.",
            "Read the sale and purchase agreement: payment schedule, penalties for backing out, and what happens at the final deed.",
        ],
    },
}

CERT_TYPES = {
    "hak_milik": "Hak Milik (freehold)",
    "hgb": "Hak Guna Bangunan (HGB)",
    "hak_pakai": "Hak Pakai (right to use)",
    "other": "Other / not sure",
}


def _valid_url(u: Any) -> bool:
    return isinstance(u, str) and re.match(r"^https://[^\s]+\.[^\s]+$", u.strip()) is not None


def _defaults() -> dict[str, str]:
    return {f"{cc}.{k}": url for cc, c in COUNTRIES.items() for k, _l, url in c["links"]}


def get_link_urls() -> dict[str, str]:
    urls = _defaults()
    raw = get_app_setting(LINK_OVERRIDES_KEY)
    if raw:
        try:
            stored = json.loads(raw)
            if isinstance(stored, dict):
                for k, u in stored.items():
                    if k in urls and _valid_url(u):
                        urls[k] = u.strip()
        except (ValueError, TypeError):
            pass
    return urls


def set_link_urls(updates: dict[str, str]) -> dict[str, str]:
    raw = get_app_setting(LINK_OVERRIDES_KEY)
    try:
        current = json.loads(raw) if raw else {}
    except (ValueError, TypeError):
        current = {}
    if not isinstance(current, dict):
        current = {}
    known = _defaults()
    for k, u in updates.items():
        if k not in known:
            continue
        if not u or not str(u).strip():
            current.pop(k, None)
        elif _valid_url(u):
            current[k] = str(u).strip()
    set_app_setting(LINK_OVERRIDES_KEY, json.dumps(current))
    return get_link_urls()


def list_countries() -> list[dict[str, Any]]:
    urls = get_link_urls()
    return [
        {
            "code": cc,
            "name": c["name"],
            "title": c["title"],
            "lead": c["lead"],
            "number_label": c["number_label"],
            "number_hint": c["number_hint"],
            "links": [{"label": l, "url": urls[f"{cc}.{k}"]} for k, l, _u in c["links"]],
            "certificate_types": [{"value": v, "label": t} for v, t in CERT_TYPES.items()] if cc == "ID" else [],
        }
        for cc, c in COUNTRIES.items()
    ]


def analysis(
    country: str,
    *,
    number_provided: bool,
    deposit_percent: Optional[float] = None,
    first_payment_percent: Optional[float] = None,
    buyer_is_foreign: Optional[bool] = None,
    certificate_type: Optional[str] = None,
    quoted_price_per_sqft: Optional[float] = None,
    market_price_per_sqft: Optional[float] = None,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if country == "PH":
        if not number_provided:
            out.append({"level": "warn", "text": "No License to Sell number given. A project must have a License to Sell before units are offered or sold. Do not pay a reservation until you have it and have checked it on the DHSUD list."})
        else:
            out.append({"level": "note", "text": "Search that License to Sell number on the DHSUD list. A number we can't check is not proof."})
    if country == "VN":
        if deposit_percent is not None:
            if deposit_percent > 5:
                out.append({"level": "warn", "text": "A deposit above 5% of the price is higher than the cap in the 2023 Law on Real Estate Business for housing projects. A deposit taken in breach of the cap can make the contract invalid. Ask for a legal explanation before paying."})
            else:
                out.append({"level": "ok", "text": "A deposit of 5% or less is within the cap for housing projects under the 2023 law."})
        if first_payment_percent is not None:
            if first_payment_percent > 30:
                out.append({"level": "warn", "text": "A first payment above 30% of the contract value (deposit included) is above the cap in the 2023 law. Ask for a legal explanation before paying."})
            else:
                out.append({"level": "ok", "text": "A first payment of 30% or less is within the cap in the 2023 law."})
    if country == "TH":
        if deposit_percent is not None:
            if deposit_percent > 30:
                out.append({"level": "warn", "text": "A deposit above 30% is higher than the typical 10% to 30%. Avoid large non-refundable payments until a lawyer has reviewed the title and contract."})
            else:
                out.append({"level": "ok", "text": "The deposit is within the typical 10% to 30% range. Check what is refundable and when."})
        if buyer_is_foreign:
            out.append({"level": "note", "text": "Foreigners cannot own land in Thailand. A condo is possible only within the building's 49% foreign quota, usually with funds sent from abroad in foreign currency."})
    if country == "ID":
        if buyer_is_foreign and certificate_type == "hak_milik":
            out.append({"level": "warn", "text": "Hak Milik (freehold) is limited to Indonesian citizens. A foreign buyer normally holds Hak Pakai or a lease instead. Get a notary's advice on the structure."})
        elif certificate_type == "hgb" and buyer_is_foreign:
            out.append({"level": "warn", "text": "HGB is open to Indonesian individuals and Indonesian-established companies, not to foreign individuals directly. Ask a notary how the purchase would be held."})
        elif certificate_type == "hak_pakai":
            out.append({"level": "ok", "text": "Hak Pakai is the right foreigners can hold. It has a fixed term (30 years, extendable). Check the remaining term and the extension conditions."})
        elif certificate_type in (None, "", "other"):
            out.append({"level": "note", "text": "Know which certificate the property has: it decides who can own it and for how long."})
    if quoted_price_per_sqft and market_price_per_sqft and quoted_price_per_sqft > 0 and market_price_per_sqft > 0:
        diff = (quoted_price_per_sqft - market_price_per_sqft) / market_price_per_sqft * 100
        if diff <= -20:
            out.append({"level": "warn", "text": f"The quoted price is about {abs(diff):.0f}% below the market average you gave. A big discount can signal a title, approval or seller problem."})
        elif diff >= 20:
            out.append({"level": "warn", "text": f"The quoted price is about {diff:.0f}% above the market average you gave. Ask what justifies the premium."})
        else:
            out.append({"level": "ok", "text": f"The quoted price is within about {abs(diff):.0f}% of the market average you gave."})
    out.append({"level": "note", "text": "These points use only what you typed. They cannot see the real registry records."})
    return out


def run_check(country: str, number: str, project_name: Optional[str] = None, builder_name: Optional[str] = None, **details: Any) -> dict[str, Any]:
    if country not in COUNTRIES:
        raise ValueError("Unknown country")
    c = COUNTRIES[country]
    urls = get_link_urls()
    n = (number or "").strip()
    return {
        "country": country,
        "state": {"code": country, "name": c["name"]},
        "number": n,
        "provided": {"project_name": (project_name or "").strip(), "builder_name": (builder_name or "").strip()},
        "number_label": c["number_label"],
        "format_check": None,
        "links": [{"label": l, "url": urls[f"{country}.{k}"]} for k, l, _u in c["links"]],
        "analysis": analysis(country, number_provided=bool(n), **details),
        "checklist": c["checklist"],
        "disclaimer": LAWYER_LINE,
        "verified": False,
    }
