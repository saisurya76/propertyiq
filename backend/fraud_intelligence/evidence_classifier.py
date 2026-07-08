from typing import Dict, List

from .models import FraudEvidence


def classify_by_fraud_type(
    evidence: List[FraudEvidence]
) -> Dict[str, List[FraudEvidence]]:

    grouped = {}

    for item in evidence:

        fraud_id = item.fraud_type_id

        if fraud_id not in grouped:
            grouped[fraud_id] = []

        grouped[fraud_id].append(item)

    return grouped