from typing import List

from .models import FraudEvidence


def _match(value: str, expected: str) -> bool:

    if expected is None:
        return True

    if expected.strip() == "":
        return True

    return value.strip().lower() == expected.strip().lower()


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