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
    name: str
    description: str


@dataclass
class FraudEvidence:
    evidence_id: str

    fraud_type: str

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
class FraudReport:
    status: FraudStatus

    fraud_types: List[FraudType]

    evidence: List[FraudEvidence]

    locality_heatmap: Optional[bytes]

    country_heatmap: Optional[bytes]

    global_heatmap: Optional[bytes]

    citations: List[str]