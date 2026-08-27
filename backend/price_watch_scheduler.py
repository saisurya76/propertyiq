"""Periodic background re-checker for URL-based price watches.

Runs as an asyncio task within this same FastAPI process — a real,
working choice given Render's standard web-service tier keeps the
process running continuously, so this needs no separate paid cron
service. Started once from api.py's lifespan handler, stopped cleanly
on shutdown so it doesn't leave a dangling task during hot reloads/tests.

Deliberately only re-checks URL-based watches (see price_watch_store's
own docstring for why manual-entry watches can't be automatically
re-checked at all).
"""

import asyncio
import logging

from backend.price_watch_store import list_active_url_watches, check_price_watch

logger = logging.getLogger(__name__)

# Every 6 hours — frequent enough to catch a real price change within a
# reasonable window, infrequent enough not to hammer listing sites (which
# already have their own bot-detection this feature has to respect, same
# as property_url_import) or the Gemini fallback budget.
CHECK_INTERVAL_SECONDS = 6 * 60 * 60


async def _run_one_check_cycle() -> None:
    watches = list_active_url_watches()
    for watch in watches:
        try:
            check_price_watch(watch["watch_id"])
        except Exception:
            # One watch failing (a genuinely broken record, an unexpected
            # error) must never stop the rest of the batch from being
            # checked — logged, not silently swallowed, but not fatal.
            logger.exception("Failed to check price watch %s", watch.get("watch_id"))


async def price_watch_check_loop() -> None:
    """Runs forever until cancelled — call asyncio.create_task on this
    once at startup, and cancel the returned task on shutdown."""
    while True:
        await _run_one_check_cycle()
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
