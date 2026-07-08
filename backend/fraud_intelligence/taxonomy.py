"""
PropertyIQ Global Fraud Taxonomy

This taxonomy is intentionally country-independent.

Countries, states, cities and localities simply activate
the fraud categories that are applicable to them.
"""

from backend.fraud_intelligence.models import FraudType


FRAUD_TYPES = [

    FraudType(
        id="TITLE_CHAIN_RISK",
        display_name="Title Chain Risk",
        description="Historical ownership chain inconsistencies or uncertainty."
    ),

    FraudType(
        id="REVENUE_RECORD_MANIPULATION",
        display_name="Revenue Record Manipulation",
        description="Manipulation or inconsistency in government land or revenue records."
    ),

    FraudType(
        id="GOVERNMENT_LAND_DISPUTES",
        display_name="Government Land Disputes",
        description="Claims involving government-owned or assigned land."
    ),

    FraudType(
        id="MULTIPLE_SALE_FRAUD",
        display_name="Multiple Sale Fraud",
        description="Same property allegedly sold or promised to multiple buyers."
    ),

    FraudType(
        id="FORGED_DOCUMENTS",
        display_name="Forged Documents",
        description="Forgery involving sale deeds, title deeds, GPA, POA or supporting documents."
    ),

    FraudType(
        id="MORTGAGE_FRAUD",
        display_name="Mortgage Fraud",
        description="Property sold despite existing mortgage or financial encumbrance."
    ),

    FraudType(
        id="ILLEGAL_LAYOUTS",
        display_name="Illegal Layouts",
        description="Unauthorized layouts or plotting without statutory approvals."
    ),

    FraudType(
        id="BUILDER_FRAUD",
        display_name="Builder Fraud",
        description="Developer misconduct identified through regulatory or judicial records."
    ),

    FraudType(
        id="APPROVAL_MISREPRESENTATION",
        display_name="Approval Misrepresentation",
        description="Misrepresentation or absence of mandatory statutory approvals."
    ),

    FraudType(
        id="SURVEY_MANIPULATION",
        display_name="Survey Manipulation",
        description="Survey number, boundary or cadastral manipulation."
    )

]