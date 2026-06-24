from dataclasses import dataclass


@dataclass
class ComparableProject:
    project_name: str
    developer: str
    city: str
    price_per_sqft: float


HYDERABAD_COMPARABLES = [

    ComparableProject(
        "Aparna Zenon",
        "Aparna",
        "Hyderabad",
        9800
    ),

    ComparableProject(
        "Prestige High Fields",
        "Prestige",
        "Hyderabad",
        10200
    ),

    ComparableProject(
        "My Home Bhooja",
        "My Home",
        "Hyderabad",
        11000
    ),

    ComparableProject(
        "Lansum Elena",
        "Lansum",
        "Hyderabad",
        9500
    )
]


def get_comparables(
    city: str
):

    city = city.lower().strip()

    if city == "hyderabad":
        return HYDERABAD_COMPARABLES

    return []


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