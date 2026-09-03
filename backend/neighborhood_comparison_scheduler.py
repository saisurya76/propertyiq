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

from backend.neighborhood_comparison_store import list_monitored_comparisons, update_comparison_results

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
