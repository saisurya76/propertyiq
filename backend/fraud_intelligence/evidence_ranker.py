from typing import List

from .models import FraudEvidence


SOURCE_PRIORITY = {

    "Government": 100,

    "Court": 95,

    "RERA": 90,

    "Audit": 85,

    "Police": 80,

    "ED": 80,

    "CBI": 80,

    "Municipal": 75,

    "Development Authority": 75,

    "Bank": 70,

    "Research": 60,

    "Media": 50,

    "Sample": 0
}


def rank_evidence(
    evidence: List[FraudEvidence]
) -> List[FraudEvidence]:

    return sorted(

        evidence,

        key=lambda item: (

            SOURCE_PRIORITY.get(
                item.source_type,
                0
            ),

            item.confidence,

            item.published_date
        ),

        reverse=True
    )