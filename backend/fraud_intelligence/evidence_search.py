from typing import List

from .models import FraudEvidence


def _match(value: str, expected: str) -> bool:

    if expected is None:
        return True

    expected = expected.strip()

    if expected == "":
        return True

    #
    # Unknown locality means
    # city-level search
    #

    if expected.lower() == "unknown":
        return True

    value = value.strip()

    #
    # Country aliases
    #

    aliases = {
        "india": "in",
        "in": "in",
        "usa": "us",
        "united states": "us",
        "us": "us"
    }

    left = aliases.get(
        value.lower(),
        value.lower()
    )

    right = aliases.get(
        expected.lower(),
        expected.lower()
    )

    return left == right


def search_evidence(
    evidence: List[FraudEvidence],

    country: str = None,
    state: str = None,
    city: str = None,
    locality: str = None
) -> List[FraudEvidence]:

    results = []

    for item in evidence:

        if not _match(item.country, country):
            continue

        if not _match(item.state, state):
            continue

        if not _match(item.city, city):
            continue

        if not _match(item.locality, locality):
            continue

        results.append(item)

    return results