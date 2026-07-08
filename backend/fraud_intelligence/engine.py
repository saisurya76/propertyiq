from datetime import datetime

from backend.fraud_intelligence.models import (
    FraudStatus,
    FraudAssessment,
    FraudReport
)

from backend.fraud_intelligence.taxonomy import (
    FRAUD_TYPES
)

from backend.fraud_intelligence.evidence_loader import (
    load_evidence
)

from backend.fraud_intelligence.evidence_search import (
    search_evidence
)

from backend.fraud_intelligence.evidence_ranker import (
    rank_evidence
)

from backend.fraud_intelligence.citation_builder import (
    build_citations
)


def generate_report_id():

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    return f"PIQ-FI-{timestamp}"


def build_assessments(evidence):

    assessments = []

    for fraud_type in FRAUD_TYPES:

        matching = [
            e for e in evidence
            if e.fraud_type_id == fraud_type.id
        ]

        assessments.append(

            FraudAssessment(

                fraud_type=fraud_type,

                risk_level=(
                    "VERY_HIGH"
                    if matching
                    else "VERY_LOW"
                ),

                color=(
                    "RED"
                    if matching
                    else "GREEN"
                ),

                evidence_count=len(matching),

                applicable=True
            )
        )

    return assessments


def generate_fraud_report(
    country: str,
    state: str,
    city: str,
    locality: str
) -> FraudReport:

    evidence = load_evidence(
        "backend/data/fraud/evidence.json"
    )

    evidence = search_evidence(
        evidence,
        country=country,
        state=state,
        city=city,
        locality=locality
    )

    evidence = rank_evidence(
        evidence
    )

    citations = build_citations(
        evidence
    )

    assessments = build_assessments(
        evidence
    )

    status = FraudStatus(

        report_id=generate_report_id(),

        status=(
            "AVAILABLE"
            if evidence
            else "UNAVAILABLE"
        ),

        generated_at=datetime.now(),

        evidence_last_synced=None
    )

    return FraudReport(

        status=status,

        city=assessments,

        city_heatmap=None,

        country=assessments,

        country_heatmap=None,

        global_taxonomy=assessments,

        global_heatmap=None,

        evidence=evidence,

        citations=citations
    )