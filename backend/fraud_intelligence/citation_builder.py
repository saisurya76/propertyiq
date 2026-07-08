from typing import List

from .models import FraudEvidence


def build_citations(
    evidence: List[FraudEvidence]
) -> List[str]:

    citations = []

    for item in evidence:

        citations.append(

            f"{item.source_name} | "
            f"{item.published_date.date()} | "
            f"{item.url}"
        )

    return citations