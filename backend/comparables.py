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


def get_comparables(
    city: str,
    property_type: str
):

    if not city:
        return []

    city = city.strip().lower()

    if city != "hyderabad":
        return []

    return [
        c
        for c in HYDERABAD_COMPARABLES
        if c.property_type.lower()
        == property_type.lower()
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