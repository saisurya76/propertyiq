"""
PropertyIQ Global Fraud Taxonomy

This taxonomy is intentionally country-independent.

Countries, states, cities and localities simply activate
the fraud categories that are applicable to them.
"""

from backend.fraud_intelligence.models import FraudType


FRAUD_TYPES = [

    FraudType(
        name="Title Chain Risk",
        description="Historical ownership chain inconsistencies or uncertainty."
    ),

    FraudType(
        name="Revenue Record Manipulation",
        description="Manipulation or inconsistency in government land or revenue records."
    ),

    FraudType(
        name="Government Land Disputes",
        description="Claims involving government-owned or assigned land."
    ),

    FraudType(
        name="Multiple Sale Fraud",
        description="Same property allegedly sold or promised to multiple buyers."
    ),

    FraudType(
        name="Forged Documents",
        description="Forgery involving sale deeds, title deeds, GPA, POA or supporting documents."
    ),

    FraudType(
        name="Mortgage Fraud",
        description="Property sold despite existing mortgage or financial encumbrance."
    ),

    FraudType(
        name="Illegal Layouts",
        description="Unauthorized layouts or plotting without statutory approvals."
    ),

    FraudType(
        name="Builder Fraud",
        description="Developer misconduct identified through regulatory or judicial records."
    ),

    FraudType(
        name="Approval Misrepresentation",
        description="Misrepresentation or absence of mandatory statutory approvals."
    ),

    FraudType(
        name="Survey Manipulation",
        description="Survey number, boundary or cadastral manipulation."
    )
]