"""Webhook delivery deduplication.

A real, confirmed gap this closes: Dodo's own webhook documentation is
explicit that a webhook handler must be idempotent against redelivery
of the same event (network retries, timeouts on a slow-but-successful
first attempt, etc. are all normal, expected occurrences for any
at-least-once webhook delivery system) — "use the webhook-id header to
implement idempotency and prevent duplicate processing... this ensures
that retried deliveries do not cause duplicate actions like double-
charging or sending multiple confirmation emails."

Before this module existed, PropertyIQ's own webhook handler had no
such check at all. Individual actions inside it were idempotent on
their own merits where it happened to matter for data correctness
(granting Insight access uses ON CONFLICT DO NOTHING), but side effects
without their own natural idempotency — most notably, the payment
confirmation email — would genuinely re-fire on every redelivery of
the same event, sending a customer multiple confirmation emails for
one single payment.
"""

from datetime import datetime, timezone
from typing import Any, Optional

from backend.db import get_connection


def initialize_webhook_store() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS processed_webhook_events (
                    webhook_id TEXT PRIMARY KEY,
                    event_type TEXT,
                    processed_at TEXT NOT NULL
                )
                """
            )
        connection.commit()


def try_claim_webhook_event(webhook_id: str, event_type: Optional[str]) -> bool:
    """Atomically claims this webhook_id for processing. Returns True
    the first time a given webhook_id is seen (the caller should go
    ahead and process the event), False every subsequent time (the
    caller should skip processing entirely — this is a redelivery of
    an event already handled).

    Uses INSERT ... ON CONFLICT DO NOTHING and checks the actual row
    count affected, rather than a separate SELECT-then-INSERT, so two
    genuinely concurrent deliveries of the same event (a real
    possibility, not just a sequential retry) can't both pass a
    check-then-act race and double-process."""
    if not webhook_id:
        # No webhook-id header at all (shouldn't happen for a real,
        # signature-verified Dodo delivery, but fails open to
        # "process it" rather than silently swallowing a genuine event
        # if it ever does) — there's nothing to dedupe against.
        return True

    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO processed_webhook_events (webhook_id, event_type, processed_at) "
                "VALUES (%s, %s, %s) ON CONFLICT (webhook_id) DO NOTHING",
                (webhook_id, event_type, now),
            )
            claimed = cursor.rowcount > 0
        connection.commit()
    return claimed


def get_processed_webhook_event(webhook_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM processed_webhook_events WHERE webhook_id = %s", (webhook_id,))
            return cursor.fetchone()
