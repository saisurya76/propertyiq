from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


@dataclass
class FraudStatus:
    report_id: str
    status: str
    generated_at: datetime
    evidence_last_synced: Optional[datetime]


@dataclass
class FraudType:
    id: str
    display_name: str
    description: str


@dataclass
class FraudEvidence:
    evidence_id: str

    fraud_type_id: str

    country: str
    state: str
    city: str
    locality: str

    source_type: str
    source_name: str

    published_date: Optional[datetime]
    retrieved_date: Optional[datetime]

    confidence: float

    citation: str
    url: str

    summary: str


@dataclass
class FraudAssessment:

    fraud_type: FraudType

    risk_level: str

    color: str

    evidence_count: int

    applicable: bool

@dataclass
class FraudReport:

    status: FraudStatus

    #
    # City Intelligence
    #

    city: List[FraudAssessment]

    city_heatmap: Optional[dict]

    #
    # Country Intelligence
    #

    country: List[FraudAssessment]

    country_heatmap: Optional[dict]

    #
    # Global Intelligence
    #

    global_taxonomy: List[FraudAssessment]

    global_heatmap: Optional[dict]

    #
    # Supporting Evidence
    #

    evidence: List[FraudEvidence]

    citations: List[str]