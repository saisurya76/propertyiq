"""Periodic background refresher for "keep monitoring" neighborhood
comparisons.

Runs as an asyncio task within this same FastAPI process, same real,
working choice (and same reasoning) as price_watch_scheduler.py's own
docstring: Render's standard web-service tier keeps this process
running continuously, so no separate paid cron service is needed.
Started once from api.py's lifespan handler, stopped cleanly on
shutdown.
"""

import asyncio
import logging

from backend.neighborhood_comparison_store import list_monitored_comparisons, update_comparison_results, set_monitoring

logger = logging.getLogger(__name__)

# Hourly, per the actual requirement this was built for — short enough
# that a monitored comparison's infrastructure/resale data stays
# genuinely current, long enough not to hammer Tavily/the comparables
# data source for comparisons nobody has looked at in days.
CHECK_INTERVAL_SECONDS = 60 * 60


async def _refresh_one_comparison(comparison: dict) -> None:
    # Imported here, not at module load time, to avoid a real circular
    # import: api.py (which defines _fetch_area_comparison_data and the
    # NeighborhoodComparisonArea model this needs) imports this
    # scheduler module itself, at startup, to launch the loop below.
    from backend.api import _fetch_area_comparison_data, NeighborhoodComparisonArea
    from backend.subscription_store import get_active_tier
    from backend.config_store import has_feature

    # A real, necessary re-check every cycle, not just at creation time:
    # "keep monitoring" is a paid feature that costs real, recurring
    # backend work on every single refresh — a subscription cancelled
    # (or downgraded to a tier without this feature) after monitoring
    # was turned on must not keep getting free, ongoing refreshes
    # forever. Auto-disables monitoring rather than silently skipping
    # the refresh forever, so the comparison's own "keep monitoring"
    # toggle stays honest about its real, current state next time
    # anyone loads the page.
    created_by = comparison.get("created_by_email")
    tier_id = get_active_tier(created_by) if created_by else None
    if not tier_id or not has_feature(tier_id, "area_comparison"):
        set_monitoring(comparison["comparison_id"], False)
        logger.info(
            "Disabled monitoring for comparison %s: creator %s no longer has an active area_comparison entitlement",
            comparison["comparison_id"], created_by,
        )
        return

    areas = [NeighborhoodComparisonArea(**area) for area in comparison["areas"]]
    results = [_fetch_area_comparison_data(area) for area in areas]
    update_comparison_results(comparison["comparison_id"], results)


async def _run_one_refresh_cycle() -> None:
    comparisons = list_monitored_comparisons()
    for comparison in comparisons:
        try:
            await _refresh_one_comparison(comparison)
        except Exception:
            # One comparison failing (a Tavily hiccup, a since-invalid
            # area) must never stop the rest of the batch from
            # refreshing — logged, not silently swallowed, but not
            # fatal to the whole cycle.
            logger.exception("Failed to refresh neighborhood comparison %s", comparison.get("comparison_id"))


async def neighborhood_comparison_refresh_loop() -> None:
    """Runs forever until cancelled — call asyncio.create_task on this
    once at startup, and cancel the returned task on shutdown."""
    while True:
        await _run_one_refresh_cycle()
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
