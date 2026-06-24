def get_deal_quality(
    overpricing_percent: float,
    buyer_protection_score: float
):

    if (
        overpricing_percent <= 5
        and buyer_protection_score >= 85
    ):
        return (
            "GOOD DEAL",
            "Property appears attractively priced relative to estimated value and demonstrates strong buyer protection characteristics."
        )

    if (
        overpricing_percent <= 15
        and buyer_protection_score >= 70
    ):
        return (
            "FAIR DEAL",
            "Property fundamentals appear reasonable, but pricing or risk factors warrant negotiation."
        )

    return (
        "POOR DEAL",
        "Current pricing or project risks materially reduce attractiveness for buyers."
    )