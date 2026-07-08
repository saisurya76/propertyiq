import json
from pathlib import Path
from datetime import datetime

from .models import FraudEvidence


def _parse_date(value):

    if not value:
        return None

    return datetime.fromisoformat(value)


def load_evidence(file_path: str):

    path = Path(file_path)

    if not path.exists():
        return []

    with path.open(
        "r",
        encoding="utf-8"
    ) as f:

        raw = json.load(f)

    evidence = []

    for item in raw:

        evidence.append(

            FraudEvidence(

                evidence_id=item["evidence_id"],

                fraud_type_id=item["fraud_type_id"],

                country=item["country"],
                state=item["state"],
                city=item["city"],
                locality=item["locality"],

                source_type=item["source_type"],
                source_name=item["source_name"],

                published_date=_parse_date(
                    item.get("published_date")
                ),

                retrieved_date=_parse_date(
                    item.get("retrieved_date")
                ),

                confidence=float(
                    item["confidence"]
                ),

                citation=item["citation"],

                url=item["url"],

                summary=item["summary"]
            )
        )

    return evidence