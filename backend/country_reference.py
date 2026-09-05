"""Static, per-country reference data — the buyer's due-diligence
checklist and local authority contacts already shown on the
Neighborhood Insights page (see COUNTRY_CONFIG in
frontend/src/NeighborhoodInsights.jsx). Copied here verbatim rather
than fetched live, since this is genuine static reference material
(legal/regulatory facts), not something with a real API to call —
the same honest reasoning as the rest of this app's static
datasets (comparables.py). Kept manually in sync with the frontend's
own copy when either changes.
"""

from typing import Any

COUNTRY_REFERENCE: dict[str, dict[str, Any]] = {
    "india": {
        "checklist": [
            "Verify the title deed and confirm a clear, marketable title with no encumbrances",
            "Check RERA registration for the project (for under-construction or recently completed properties)",
            "Confirm the occupancy certificate (OC) and completion certificate (CC) have been issued",
            "Get an encumbrance certificate covering at least the last 13-30 years",
            "Review property tax receipts to confirm they're current and in the seller's name",
            "Check for any pending litigation or disputes tied to the property or land",
            "Confirm the approved building plan matches the actual construction",
            "Verify khata/mutation records reflect the current owner correctly",
        ],
        "authority_contacts": [
            ("RERA helpline", "Search online for your state's RERA helpline"),
            ("Sub-Registrar's Office", "Handles registration and encumbrance certificates"),
            ("Municipal Corporation / Panchayat", "Property tax records, building plan approvals"),
            ("State Consumer Helpline", "1915"),
        ],
    },
    "thailand": {
        "checklist": [
            "Verify the title is a Chanote (Nor Sor 4 Jor) — the only Thai title conferring full, GPS-surveyed ownership; lower-grade titles do not",
            "For a condo, confirm the building's 49% foreign-ownership quota has not been reached",
            "If buying freehold as a foreigner, ensure funds are remitted from abroad through a Thai bank with a Foreign Exchange Transaction Form (FETF)",
            "Check the title for encumbrances, mortgages, outstanding common-area fees, and any litigation at the Land Office",
            "If the plot is landlocked, verify a registered right-of-way easement exists",
            "Foreigners cannot own land directly — confirm the deal structure before paying a deposit",
        ],
        "authority_contacts": [
            ("Department of Lands (Land Department)", "National title registry and transfer authority — verify Chanote status here"),
            ("Local Land Office", "Handles title checks and registration for the property's specific district"),
        ],
    },
    "philippines": {
        "checklist": [
            "Get a Certified True Copy of the title from the Registry of Deeds (TCT for land, CCT for condo units)",
            "Confirm the title has no liens, encumbrances, adverse claims, or lis pendens annotations",
            "Cross-check the tax declaration at the local Assessor's Office against the title",
            "Confirm the developer holds a valid License to Sell from DHSUD",
            "Foreigners cannot own land — if buying a condo, verify the building's 40% foreign-ownership cap has not been reached",
            "Check the developer's track record with DHSUD for delivery delays or pending complaints",
        ],
        "authority_contacts": [
            ("Registry of Deeds", "Under the Land Registration Authority — title verification and registration"),
            ("DHSUD", "Department of Human Settlements and Urban Development — developer/project licensing"),
            ("Bureau of Internal Revenue (BIR)", "Transfer taxes and the Certificate Authorizing Registration (CAR)"),
        ],
    },
    "vietnam": {
        "checklist": [
            "Verify the seller's Pink Book (Certificate of Land Use Rights and Ownership of Assets) is genuine and matches the seller",
            "Confirm no mortgage, dispute, or restriction annotations on the certificate",
            "If buying as a foreigner, verify the building's foreign-ownership quota (30% of units) has not been reached",
            "Understand foreign ownership is a 50-year term from Pink Book issuance, not freehold land ownership",
            "For off-plan purchases, confirm the project has official approval for foreign sales before paying a deposit",
            "Confirm funds are transferred through a licensed Vietnamese bank, with all payment receipts kept",
        ],
        "authority_contacts": [
            ("Provincial land registration office", "Under the Ministry of Agriculture and Environment — Pink Book issuance and verification"),
            ("Commune-level People's Committee", "Since July 2025, first-time certificates are issued here, not at district level"),
        ],
    },
    "indonesia": {
        "checklist": [
            "Confirm the certificate type — Hak Milik (freehold) is for Indonesian citizens only; foreigners can hold Hak Pakai or access HGB via a PT PMA company",
            "Verify the land certificate directly at the local BPN office — owner, boundaries, and expiry date",
            "Reject any legacy or unregistered certificate such as Girik — invalid for transfer under Government Regulation 18/2021",
            "Check the property's zoning designation against the local spatial plan (RTRW)",
            "Confirm building approval (PBG) and a fitness-for-use certificate (SLF) for completed structures",
            "Avoid nominee arrangements (illegal and unenforceable for a foreign buyer)",
        ],
        "authority_contacts": [
            ("BPN / ATR", "Badan Pertanahan Nasional — land certificate verification and registration"),
            ("Local PPAT", "Land deed notary — required to execute and register any property transfer"),
        ],
    },
}


def get_country_reference(country: str) -> dict[str, Any]:
    """Case-insensitive lookup with an honest default: a country not
    in this map at all (shouldn't happen given this app's own 5
    supported countries, but real code should never assume) falls
    back to an empty checklist/contacts list rather than raising or
    silently reusing India's."""
    return COUNTRY_REFERENCE.get((country or "").strip().lower(), {"checklist": [], "authority_contacts": []})
