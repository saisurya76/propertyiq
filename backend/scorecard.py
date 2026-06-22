from dataclasses import dataclass


@dataclass
class Scorecard:

    buyer_protection_score: float

    valuation_score: float

    inventory_score: float

    developer_score: float

    recommendation: str