from datetime import datetime

from backend.fraud_intelligence.models import (
    FraudStatus,
    FraudReport
)

from backend.fraud_intelligence.taxonomy import (
    FRAUD_TYPES
)


def generate_report_id():

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")

    return f"PIQ-FI-{timestamp}"


def generate_fraud_report(
    country: str,
    state: str,
    city: str,
    locality: str
) -> FraudReport:

    status = FraudStatus(

        report_id=generate_report_id(),

        status="UNAVAILABLE",

        generated_at=datetime.now(),

        evidence_last_synced=None
    )

    return FraudReport(

        status=status,

        fraud_types=FRAUD_TYPES,

        evidence=[],

        locality_heatmap=None,

        country_heatmap=None,

        global_heatmap=None,

        citations=[]
    )