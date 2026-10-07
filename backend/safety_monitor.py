"""Safety monitor for the Quick Analysis-only launch mode.

While launch mode is ON, two promises must hold no matter what an admin
clicks, saves or forgets:

  1. NO NEW SUBSCRIPTIONS can be bought.
  2. NOTHING that belongs to a current subscriber is taken away: not their
     tier, their features, their quotas, nor the panels that front them.

This module is the single rule set for both. It is pure: it gets the state
it needs as arguments and returns a list of plain-English violations, so it
is easy to test and cannot itself change anything. backend/api.py calls it
in two places:

  * guard — before every admin write that could break a rule, so the write
    is refused (HTTP 409) and nothing is saved;
  * drift check — a background loop that re-checks the live state, repairs
    the few safe things (re-locks Studio tiers, re-opens the free
    assessment) and records anything it cannot repair.

Switching the mode OFF is never blocked: that is the way back to the state
the admin had before switching ON.
"""

from __future__ import annotations

from typing import Any, Optional

# Features each homepage panel / Neighborhood Insights section stands for.
# A panel is "tied" to a subscription when its feature is held by a tier.
# construction_studio has no single feature flag: it is the Studio plans
# themselves, so any active subscriber holds it.
PANEL_FEATURES = {
    "construction_studio": None,
    "agent_intelligence": "agent_intelligence",
    "property_ai_advisor": "property_ai_advisor",
    "price_drop_alert": "price_drop_alert",
}
NI_SECTION_FEATURES = {
    "comparison": "area_comparison",
    "price_trends": "price_trends",
    "cost_of_living": "cost_of_living",
    "emi_calculator": "emi_calculator",
    "amortization_projector": "amortization_projector",
    "loan_eligibility": "loan_eligibility",
}

SELLABLE_TIER = "insight_addon"
REQUIRED_FREE_FEATURES = ["property_assessment"]


def _is_quota_key(key: str) -> bool:
    return key.endswith("_per_month") or key.endswith("_limit") or key.startswith("max_")


def _quota_reduced(old: Any, new: Any) -> bool:
    """None means unlimited, so None -> number is a reduction."""
    if old is None:
        return new is not None
    if new is None:
        return False
    try:
        return new < old
    except TypeError:
        return False


def _holders_of(feature: Optional[str], tiers: dict, subscribers_by_tier: dict) -> list[str]:
    """Tier ids that have at least one active subscriber and include `feature`
    (any active subscriber when feature is None)."""
    out = []
    for tier_id, count in subscribers_by_tier.items():
        if count <= 0:
            continue
        if feature is None or feature in (tiers.get(tier_id, {}).get("features") or []):
            out.append(tier_id)
    return out


def check_tier_config(
    current: dict, proposed: dict, subscribers_by_tier: dict, subscription_tier_ids: list[str],
    require_sellable: bool = True,
) -> list[str]:
    """Rules for an admin tier save. `current` and `proposed` are fully merged
    tier configs (defaults under persisted)."""
    problems: list[str] = []

    # 1. no new subscriptions: every subscription tier stays "coming soon"
    for tier_id in subscription_tier_ids:
        if not proposed.get(tier_id, {}).get("coming_soon"):
            label = proposed.get(tier_id, {}).get("label", tier_id)
            problems.append(
                f"{label} would become purchasable. New subscriptions must stay closed while "
                "launch mode is on."
            )

    # 2. the one thing for sale stays sellable
    # (not enforced during a wind-down on its own, where closing everything is the point)
    sellable = proposed.get(SELLABLE_TIER, {})
    if require_sellable and sellable.get("coming_soon"):
        problems.append("Quick Analysis would be marked Coming soon, leaving nothing for sale.")
    if require_sellable and sellable.get("mode") == "free":
        problems.append("Quick Analysis would be set to Free, leaving nothing to buy.")

    # 3. subscribers keep everything that is theirs
    protected = set(tid for tid, n in subscribers_by_tier.items() if n > 0) | {SELLABLE_TIER}
    for tier_id in sorted(protected):
        old, new = current.get(tier_id), proposed.get(tier_id)
        if old is None:
            continue
        label = old.get("label", tier_id)
        if new is None:
            problems.append(f"{label} would be removed while it has subscribers or buyers.")
            continue
        if old.get("billing") != new.get("billing"):
            problems.append(f"{label}'s billing type would change.")
        lost = [f for f in (old.get("features") or []) if f not in (new.get("features") or [])]
        if lost:
            problems.append(f"{label} would lose features its subscribers have: {', '.join(lost)}.")
        for key, old_value in old.items():
            if _is_quota_key(key) and _quota_reduced(old_value, new.get(key)):
                problems.append(f"{label}'s {key.replace('_', ' ')} would be reduced for existing subscribers.")
    return problems


def check_settings_change(
    free_features_after: Optional[list[str]],
    panels_after: dict,
    sections_after: dict,
    tiers: dict,
    subscribers_by_tier: dict,
) -> list[str]:
    """Rules for an admin settings save. Pass None/{} for anything the request
    does not change."""
    problems: list[str] = []

    if free_features_after is not None:
        for feature in REQUIRED_FREE_FEATURES:
            if feature not in free_features_after:
                problems.append(
                    f"'{feature}' would stop being free. It is the way new users reach a report "
                    "to buy Quick Analysis from."
                )

    # Hiding something a subscriber's plan includes blocks what is theirs.
    for panel, shown in panels_after.items():
        if shown is False and panel in PANEL_FEATURES:
            if _holders_of(PANEL_FEATURES[panel], tiers, subscribers_by_tier):
                problems.append(
                    f"Hiding the '{panel}' home panel would hide it from active subscribers whose plan includes it."
                )
    for section, shown in sections_after.items():
        feature = NI_SECTION_FEATURES.get(section)
        if shown is False and feature and _holders_of(feature, tiers, subscribers_by_tier):
            problems.append(
                f"Hiding the '{section}' Neighborhood Insights section would hide it from active "
                "subscribers whose plan includes it."
            )
    return problems


def check_live_state(
    tiers: dict, free_features: list[str], subscription_tier_ids: list[str], launch_active: bool = True
) -> list[str]:
    """Drift check on what is stored right now (not a proposed change)."""
    problems = []
    for tier_id in subscription_tier_ids:
        if not tiers.get(tier_id, {}).get("coming_soon"):
            problems.append(f"tier:{tier_id}:open")
    if not launch_active:
        return problems  # wind-down alone: only "no new subscriptions" applies
    sellable = tiers.get(SELLABLE_TIER, {})
    if sellable.get("coming_soon"):
        problems.append("tier:insight_addon:coming_soon")
    if sellable.get("mode") == "free":
        problems.append("tier:insight_addon:free")
    for feature in REQUIRED_FREE_FEATURES:
        if feature not in free_features:
            problems.append(f"free:{feature}:missing")
    return problems
