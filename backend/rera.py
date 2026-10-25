"""RERA guided verification + basic analysis.

Deliberately NOT a verifier: we never claim a project or agent is
"verified". We do a soft format check on the number the user typed, point
them to the official state RERA portal, give a checklist of what to confirm
there, and run a few honest rule-based observations on details they supply.
Portal URLs are admin-overridable (portals move) via app setting."""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any, Optional

from backend.config_store import get_app_setting, set_app_setting

PORTAL_OVERRIDES_KEY = "rera_portal_urls"

# code -> (name, default official portal, soft number-prefix hint or None)
RERA_STATES: dict[str, tuple[str, str, Optional[str]]] = {
    "AN": ("Andaman & Nicobar", "https://rera.andaman.gov.in", None),
    "AP": ("Andhra Pradesh", "https://rera.ap.gov.in", None),
    "AR": ("Arunachal Pradesh", "https://rera.arunachal.gov.in", None),
    "AS": ("Assam", "https://rera.assam.gov.in", None),
    "BR": ("Bihar", "https://rera.bihar.gov.in", None),
    "CH": ("Chandigarh", "https://rera.chd.gov.in", None),
    "CG": ("Chhattisgarh", "https://rera.cgstate.gov.in", None),
    "DN": ("Dadra & Nagar Haveli / Daman & Diu", "https://rera.daman.nic.in", None),
    "DL": ("Delhi", "https://rera.delhi.gov.in", None),
    "GA": ("Goa", "https://rera.goa.gov.in", None),
    "GJ": ("Gujarat", "https://gujrera.gujarat.gov.in", None),
    "HR": ("Haryana", "https://haryanarera.gov.in", None),
    "HP": ("Himachal Pradesh", "https://hprera.nic.in", None),
    "JH": ("Jharkhand", "https://jharera.jharkhand.gov.in", None),
    "KA": ("Karnataka", "https://rera.karnataka.gov.in", None),
    "KL": ("Kerala", "https://rera.kerala.gov.in", None),
    "LD": ("Lakshadweep", "https://lakshadweep.gov.in", None),
    "MP": ("Madhya Pradesh", "https://www.rera.mp.gov.in", None),
    "MH": ("Maharashtra (MahaRERA)", "https://maharera.maharashtra.gov.in", "P5"),
    "MN": ("Manipur", "https://manipur.gov.in", None),
    "ML": ("Meghalaya", "https://meghalaya.gov.in", None),
    "MZ": ("Mizoram", "https://rera.mizoram.gov.in", None),
    "NL": ("Nagaland", "https://rera.nagaland.gov.in", None),
    "OD": ("Odisha", "https://rera.odisha.gov.in", None),
    "PY": ("Puducherry", "https://prera.py.gov.in", None),
    "PB": ("Punjab", "https://rera.punjab.gov.in", None),
    "RJ": ("Rajasthan", "https://rera.rajasthan.gov.in", None),
    "SK": ("Sikkim", "https://sikkim.gov.in", None),
    "TN": ("Tamil Nadu", "https://rera.tn.gov.in", None),
    "TS": ("Telangana", "https://rera.telangana.gov.in", None),
    "TR": ("Tripura", "https://rera.tripura.gov.in", None),
    "UP": ("Uttar Pradesh", "https://www.up-rera.in", None),
    "UK": ("Uttarakhand", "https://rera.uk.gov.in", None),
    "WB": ("West Bengal", "https://rera.wb.gov.in", None),
}

CHECKLIST = [
    "Project is listed on the state RERA portal and its status is Active (not lapsed, revoked or suspended).",
    "Project name, promoter/developer name and location on the portal match what you were shown.",
    "Registration validity and the proposed completion date; check for any extension granted.",
    "Sanctioned plan, approvals and land title details uploaded by the promoter.",
    "Carpet area and unit count in the registration match the brochure and agreement for sale.",
    "Quarterly progress updates are being filed, and the construction percentage looks credible.",
    "Complaints or orders against the project or promoter on the portal.",
    "If buying through an agent, the agent's own RERA registration number is valid and current.",
    "Escrow (RERA) account details: 70% of buyer money must be held for construction.",
]

DISCLAIMER = (
    "This is a guide, not a verification. PropertyIQ does not confirm that any "
    "registration is genuine. Always confirm the number on the official state RERA "
    "portal and consider legal advice before paying any money."
)


def get_portal_urls() -> dict[str, str]:
    urls = {c: v[1] for c, v in RERA_STATES.items()}
    raw = get_app_setting(PORTAL_OVERRIDES_KEY)
    if raw:
        try:
            stored = json.loads(raw)
            if isinstance(stored, dict):
                for c, u in stored.items():
                    if c in urls and _valid_url(u):
                        urls[c] = u.strip()
        except (ValueError, TypeError):
            pass
    return urls


def _valid_url(u: Any) -> bool:
    return isinstance(u, str) and re.match(r"^https://[^\s]+\.[^\s]+$", u.strip()) is not None


def set_portal_urls(updates: dict[str, str]) -> dict[str, str]:
    """Merge updates over saved overrides. Unknown states / non-https URLs are
    dropped; a blank value resets that state to its shipped default."""
    raw = get_app_setting(PORTAL_OVERRIDES_KEY)
    try:
        current = json.loads(raw) if raw else {}
    except (ValueError, TypeError):
        current = {}
    if not isinstance(current, dict):
        current = {}
    for code, url in updates.items():
        if code not in RERA_STATES:
            continue
        if not url or not str(url).strip():
            current.pop(code, None)
        elif _valid_url(url):
            current[code] = str(url).strip()
    set_app_setting(PORTAL_OVERRIDES_KEY, json.dumps(current))
    return get_portal_urls()


def list_states() -> list[dict[str, Any]]:
    urls = get_portal_urls()
    return [{"code": c, "name": v[0], "portal_url": urls[c]} for c, v in RERA_STATES.items()]


def check_format(state: str, number: str) -> dict[str, Any]:
    n = (number or "").strip()
    compact = re.sub(r"\s+", "", n).upper()
    notes: list[str] = []
    level = "ok"
    if len(compact) < 6:
        level, _ = "warn", notes.append("This looks too short to be a registration number.")
    elif len(compact) > 40:
        level, _ = "warn", notes.append("This looks too long to be a registration number.")
    elif not re.search(r"\d", compact):
        level, _ = "warn", notes.append("Registration numbers normally contain digits.")
    elif not re.fullmatch(r"[A-Z0-9/\-_.()]+", compact):
        level, _ = "warn", notes.append("Contains unusual characters; copy the number exactly as printed.")
    hint = RERA_STATES[state][2]
    if level == "ok" and hint and not compact.startswith(hint):
        level = "note"
        notes.append(
            f"{RERA_STATES[state][0]} numbers usually start with \"{hint}\". "
            "Older registrations may differ, so this is only a hint."
        )
    if level == "ok":
        notes.append("The format looks plausible. That does not mean the registration exists.")
    return {"level": level, "notes": notes}


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def basic_analysis(
    *,
    possession_date: Optional[str] = None,
    quoted_price_per_sqft: Optional[float] = None,
    market_price_per_sqft: Optional[float] = None,
    advance_percent: Optional[float] = None,
    is_under_construction: Optional[bool] = None,
    agent_number_provided: bool = False,
    today: Optional[date] = None,
) -> list[dict[str, str]]:
    today = today or date.today()
    out: list[dict[str, str]] = []
    pd = _parse_date(possession_date)
    if possession_date and not pd:
        out.append({"level": "note", "text": "Possession date not understood; use the YYYY-MM-DD format."})
    elif pd:
        if pd < today and is_under_construction:
            out.append({"level": "warn", "text": "The promised possession date has already passed for a project you describe as under construction. Check for a registered extension and ask why."})
        elif (pd - today).days > 365 * 5:
            out.append({"level": "warn", "text": "Possession is more than 5 years away, which ties up your money for a long time."})
        else:
            out.append({"level": "ok", "text": "The possession date is within a normal range. Confirm it matches the date on the RERA portal."})
    if quoted_price_per_sqft and market_price_per_sqft and quoted_price_per_sqft > 0 and market_price_per_sqft > 0:
        diff = (quoted_price_per_sqft - market_price_per_sqft) / market_price_per_sqft * 100
        if diff <= -20:
            out.append({"level": "warn", "text": f"The quoted price is about {abs(diff):.0f}% below the market average. A big discount can signal an issue with title, approvals or the seller."})
        elif diff >= 20:
            out.append({"level": "warn", "text": f"The quoted price is about {diff:.0f}% above the market average. Ask what justifies the premium."})
        else:
            out.append({"level": "ok", "text": f"The quoted price is within about {abs(diff):.0f}% of the market average you gave."})
    if advance_percent is not None:
        if advance_percent > 10:
            out.append({"level": "warn", "text": "The RERA Act bars a promoter from taking more than 10% as advance before a registered agreement for sale. Do not pay more before the agreement is registered."})
        else:
            out.append({"level": "ok", "text": "An advance of 10% or less is within the RERA limit before a registered agreement for sale."})
    if not agent_number_provided:
        out.append({"level": "note", "text": "No agent registration number given. If an agent is involved, ask for their RERA agent number and check it on the same portal."})
    out.append({"level": "note", "text": "These points use only what you typed. They cannot see the actual registration."})
    return out


def run_check(state: str, number: str, project_name: Optional[str] = None, builder_name: Optional[str] = None, **details: Any) -> dict[str, Any]:
    if state not in RERA_STATES:
        raise ValueError("Unknown state")
    urls = get_portal_urls()
    return {
        "state": {"code": state, "name": RERA_STATES[state][0], "portal_url": urls[state]},
        "number": number.strip(),
        "provided": {
            "project_name": (project_name or "").strip(),
            "builder_name": (builder_name or "").strip(),
        },
        "format_check": check_format(state, number),
        "analysis": basic_analysis(**details),
        "checklist": CHECKLIST,
        "disclaimer": DISCLAIMER,
        "verified": False,
    }
