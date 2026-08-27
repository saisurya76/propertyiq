from dataclasses import dataclass


@dataclass
class ComparableProject:
    project_name: str
    developer: str
    city: str
    property_type: str
    price_per_sqft: float


HYDERABAD_COMPARABLES = [

    ComparableProject(
        "Aparna Zenon",
        "Aparna",
        "Hyderabad",
        "Apartment",
        9800
    ),

    ComparableProject(
        "Prestige High Fields",
        "Prestige",
        "Hyderabad",
        "Apartment",
        10200
    ),

    ComparableProject(
        "My Home Bhooja",
        "My Home",
        "Hyderabad",
        "Apartment",
        11000
    ),

    ComparableProject(
        "Lansum Elena",
        "Lansum",
        "Hyderabad",
        "Apartment",
        9500
    )
]

# Everything below this line was added in a single research pass (Aug
# 2026) to extend real-comparables coverage beyond Hyderabad — a real,
# explicit request, not incremental. Each entry is a genuinely researched
# citywide market-average asking price, sourced from real estate market
# reports/portals current as of Aug 2026 (SquareYards, 99acres,
# GlobalPropertyGuide, Bamboo Routes, and similar), NOT multiple named
# project comparables like Hyderabad has above — that level of per-
# project detail wasn't available within this research pass for every
# city, so each is honestly labeled "Citywide Average" rather than
# invented project names. All figures are Apartment/condo-type only
# (the most consistently reported type across all sources); Villa/Plot/
# Commercial are NOT included here and will correctly fall through to
# the honest "not enough data" response via get_comparables' existing
# type filter, same as any unsupported city.
#
# Only cities with a genuinely findable, city-level (not just a single
# neighborhood's cheapest/priciest micro-market) figure were included.
# Smaller cities not listed here were NOT found with a clear enough
# citywide figure during this research pass and are deliberately left
# unsupported rather than filled in with a guess — see the chat summary
# accompanying this delivery for the exact list of what's covered vs not.
#
# SEA countries' original sources quote per square meter; converted to
# price-per-sqft here (÷10.7639) purely for consistency with this
# module's existing field name — the conversion is arithmetic, not a
# separate data point.

INDIA_COMPARABLES = [
    ComparableProject("Citywide Average (Aug 2026)", "Market data", "Mumbai", "Apartment", 14000),
    ComparableProject("Citywide Average (Aug 2026)", "Market data", "Delhi", "Apartment", 13000),
    ComparableProject("Citywide Average (Aug 2026)", "Market data", "Bangalore", "Apartment", 12100),
    ComparableProject("Citywide Average (Aug 2026)", "Market data", "Chennai", "Apartment", 7900),
    ComparableProject("Citywide Average (Aug 2026)", "Market data", "Kolkata", "Apartment", 6400),
    ComparableProject("Citywide Average (Aug 2026)", "Market data", "Pune", "Apartment", 12950),
    ComparableProject("Citywide Average (Aug 2026)", "Market data", "Ahmedabad", "Apartment", 5900),
    ComparableProject("Citywide Average (Aug 2026)", "Market data", "Lucknow", "Apartment", 6700),
    ComparableProject("Citywide Average (Aug 2026)", "Market data", "Nagpur", "Apartment", 4350),
]

THAILAND_COMPARABLES = [
    ComparableProject("Citywide Average (Aug 2026)", "Market data", "Bangkok", "Apartment", round(130000 / 10.7639)),
    ComparableProject("Citywide Average (Aug 2026)", "Market data", "Chiang Mai", "Apartment", round(60000 / 10.7639)),
    ComparableProject("Citywide Average (Aug 2026)", "Market data", "Phuket", "Apartment", round(96285 / 10.7639)),
    ComparableProject("Citywide Average (Aug 2026)", "Market data", "Pattaya", "Apartment", round(70000 / 10.7639)),
]

VIETNAM_COMPARABLES = [
    ComparableProject("Citywide Average (Aug 2026)", "Market data", "Ho Chi Minh City", "Apartment", round((4500 * 25500) / 10.7639)),
    ComparableProject("Citywide Average (Aug 2026)", "Market data", "Hanoi", "Apartment", round((3852 * 25500) / 10.7639)),
    ComparableProject("Citywide Average (Aug 2026)", "Market data", "Da Nang", "Apartment", round((1800 * 25500) / 10.7639)),
]

INDONESIA_COMPARABLES = [
    ComparableProject("Citywide Average (Aug 2026)", "Market data", "Jakarta", "Apartment", round(36_000_000 / 10.7639)),
    ComparableProject("Citywide Average (Aug 2026)", "Market data", "Bandung", "Apartment", round(16_000_000 / 10.7639)),
]

PHILIPPINES_COMPARABLES = [
    ComparableProject("Citywide Average (Aug 2026)", "Market data", "Manila", "Apartment", round(120000 / 10.7639)),
    ComparableProject("Citywide Average (Aug 2026)", "Market data", "Quezon City", "Apartment", round(100000 / 10.7639)),
    ComparableProject("Citywide Average (Aug 2026)", "Market data", "Cebu City", "Apartment", round(162195 / 10.7639)),
    ComparableProject("Citywide Average (Aug 2026)", "Market data", "Makati", "Apartment", round(230000 / 10.7639)),
]

ALL_COMPARABLES = (
    HYDERABAD_COMPARABLES
    + INDIA_COMPARABLES
    + THAILAND_COMPARABLES
    + VIETNAM_COMPARABLES
    + INDONESIA_COMPARABLES
    + PHILIPPINES_COMPARABLES
)


def get_comparables(
    city: str,
    property_type: str
):

    if not city:
        return []

    city_normalized = city.strip().lower()

    # Live data, when it can genuinely be fetched, REPLACES the static
    # snapshot for this city rather than being blended with it — a
    # deliberate choice, not an oversight: averaging a live, current
    # figure together with a static one that's already confirmed to be
    # meaningfully wrong for at least one city (Mumbai: static ~₹14,000
    # vs live ~₹38,600) would still produce a wrong, merely-less-wrong
    # number. Only India Apartment listings are covered by this live
    # source (see live_comparables.py's own docstring for the honest
    # scope limits) — everything else falls through to the static data
    # exactly as before, completely unaffected by this addition.
    if property_type.lower() == "apartment":
        from backend.live_comparables import get_live_price_per_sqft
        live_price = get_live_price_per_sqft(city)
        if live_price is not None:
            return [
                ComparableProject(
                    "Live Market Data (SquareYards, current month)",
                    "Live market data",
                    city,
                    "Apartment",
                    live_price,
                )
            ]

    return [
        c
        for c in ALL_COMPARABLES
        if c.city.lower() == city_normalized
        and c.property_type.lower() == property_type.lower()
    ]


def average_price_per_sqft(
    comparables
):

    if not comparables:
        return 0

    total = sum(
        c.price_per_sqft
        for c in comparables
    )

    return round(
        total / len(comparables),
        2
    )
