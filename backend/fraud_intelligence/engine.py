from datetime import datetime
from typing import List

from backend.fraud_intelligence.models import (
    FraudStatus,
    FraudAssessment,
    FraudMatrixCell,
    GlobalFraudMatrix,
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


def build_city_assessments(evidence):

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


def build_country_assessments(evidence):

    return build_city_assessments(
        evidence
    )


def build_global_assessments(evidence):

    return build_city_assessments(
        evidence
    )

def build_global_matrix(
    assessments: List[FraudAssessment],
    countries: List[str]
) -> GlobalFraudMatrix:

    cells = []

    for country in countries:

        for assessment in assessments:

            cells.append(

                FraudMatrixCell(

                    country=country,

                    fraud_type_id=
                        assessment.fraud_type.id,

                    risk_level=
                        assessment.risk_level,

                    color=
                        assessment.color
                )
            )

    return GlobalFraudMatrix(

        countries=countries,

        fraud_types=[
            a.fraud_type
            for a in assessments
        ],

        cells=cells
    )

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

    city_assessments = build_city_assessments(
        evidence
    )

    country_assessments = build_country_assessments(
        evidence
    )

    global_assessments = build_global_assessments(
        evidence
    )

    global_matrix = build_global_matrix(

        assessments=global_assessments,

        countries=[
            country
        ]
    )

    status = FraudStatus(

        report_id=generate_report_id(),

        status=(

            "AVAILABLE"

            if evidence

            else "PARTIAL"
        ),

        generated_at=datetime.now(),

        evidence_last_synced=None
    )

    return FraudReport(

        status=status,

        city=city_assessments,

        city_heatmap=None,

        country=country_assessments,

        country_heatmap=None,

        global_taxonomy=global_assessments,

        global_heatmap=None,

        global_matrix=global_matrix,

        evidence=evidence,

        citations=citations
    )