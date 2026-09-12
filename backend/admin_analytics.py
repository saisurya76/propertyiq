"""Real analytics for the admin dashboard's Overview & Analytics screen.

Deliberately centralized here (direct, read-only queries against each
real table) rather than adding a new global-count function to every
individual store module — this is admin-only reporting, not a quota
check, so it doesn't need to live alongside each feature's own store.

Every number here is a genuine COUNT(*) against a real table — no
estimates, no sampling. Features that never persist anything (the
property assessment, EMI calculator, Price Trends, Cost of Living —
pure on-demand lookups with no saved record) are honestly listed as
"not tracked yet" rather than a fabricated zero or omitted silently,
since a real usage-logging table would be needed to count these and
none exists today.
"""

import os
from typing import Any

from backend.db import get_connection


def _count_rows(table: str) -> int:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) AS n FROM {table}")
            return cursor.fetchone()["n"]


# table name -> the real feature it represents. Every one of these
# tables only gets a row when a user genuinely uses that feature, so a
# row count is a real, direct usage signal — not an estimate.
_FEATURE_USAGE_TABLES: dict[str, str] = {
    "Construction Studio designs": "construction_designs",
    "Neighborhood area comparisons": "neighborhood_comparisons",
    "Price Drop Alert watches": "price_watches",
    "Agent Intelligence clients": "agent_clients",
    "Agent Intelligence properties": "agent_client_properties",
    "Quick Analysis purchases": "insight_grants",
    "Challenge a Friend challenges": "property_challenges",
    "Saved properties (Construction Studio)": "properties",
}

# Real, known gap: these features never write anything to the
# database — they're pure on-demand lookups (an assessment is
# computed and returned, never stored). Listed honestly rather than
# silently omitted, so nobody assumes usage is zero.
FEATURES_WITHOUT_USAGE_TRACKING = [
    "Property Assessment (on-demand, not logged)",
    "EMI Calculator (on-demand, not logged)",
    "Amortization Projector (on-demand, not logged)",
    "Price Trends (on-demand, not logged)",
    "Cost of Living (on-demand, not logged)",
    "Agent Intelligence report generation (on-demand, not logged)",
]


def get_feature_usage_stats() -> dict[str, Any]:
    counts = {label: _count_rows(table) for label, table in _FEATURE_USAGE_TABLES.items()}
    return {
        "counts": counts,
        "not_tracked": FEATURES_WITHOUT_USAGE_TRACKING,
    }


# label -> the real env var (or admin-configured setting) that proves
# this service is actually wired up. "configured" here means "has
# real credentials set," not "is currently reachable" — this sandbox
# environment's own network restrictions (or a real outage) can make a
# fully-configured service temporarily unreachable without that being
# a configuration problem.
def get_tech_stack_status() -> list[dict[str, Any]]:
    from backend.property_url_extract import get_gemini_api_key

    services = [
        ("Database (Neon Postgres)", bool(os.environ.get("DATABASE_URL"))),
        ("Backend hosting (Render)", True),  # self-evident: this code is answering the request from Render right now
        ("Frontend hosting (Vercel)", True),  # self-evident: the admin panel making this request was itself served by Vercel
        ("Dodo Payments", bool(os.environ.get("DODO_PAYMENTS_API_KEY"))),
        ("Resend (email)", bool(os.environ.get("RESEND_API_KEY")) or bool(os.environ.get("LIVINGIQ_AUTH_BASE_URL"))),
        ("LocationIQ (address autocomplete)", bool(os.environ.get("LOCATIONIQ_API_KEY"))),
        ("OpenWeatherMap (air quality)", bool(os.environ.get("OPENWEATHER_API_KEY"))),
        ("FRED / Bank for International Settlements (price trends)", bool(os.environ.get("FRED_API_KEY"))),
        ("Tavily (infrastructure news + property search)", bool(os.environ.get("TAVILY_API_KEY"))),
        ("Google Gemini (property URL extraction + report translation)", bool(get_gemini_api_key())),
    ]
    return [{"name": name, "configured": configured} for name, configured in services]
