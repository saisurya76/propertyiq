"""Backs the Neighborhood Insights comparison feature: up to 5 areas
(any city, any country) compared side by side, with an optional
"keep monitoring" mode that refreshes the comparison automatically
every hour so it's ready with fresh data the next time the page loads,
rather than the visitor waiting on a live fetch.

Deliberately not tied to a user account — Neighborhood Insights is a
public, no-signup page (same reasoning as its own resale-signal and
autocomplete endpoints), so a comparison is identified purely by its
own generated ID, the same pattern price_watches already uses for a
no-login "watch" that still needs to persist and be found again later.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from backend.db import get_connection

MAX_AREAS_PER_COMPARISON = 5


def initialize_neighborhood_comparison_store() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS neighborhood_comparisons (
                    comparison_id TEXT PRIMARY KEY,
                    areas TEXT NOT NULL,
                    results TEXT NOT NULL,
                    monitoring BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TEXT NOT NULL,
                    last_refreshed_at TEXT NOT NULL
                )
                """
            )
        connection.commit()


def create_comparison(areas: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    """`areas` is the caller-supplied list of up to MAX_AREAS_PER_COMPARISON
    {city, country, locality, lat, lon} dicts; `results` is the already-
    fetched comparison data per area (fetching itself is the API layer's
    job, same division of responsibility as price_watch_store's own
    create_price_watch/api_create_price_watch split) — this function is
    persistence only."""
    if len(areas) > MAX_AREAS_PER_COMPARISON:
        raise ValueError(f"A comparison can include at most {MAX_AREAS_PER_COMPARISON} areas.")
    if len(areas) < 2:
        raise ValueError("A comparison needs at least 2 areas.")

    comparison_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO neighborhood_comparisons
                    (comparison_id, areas, results, monitoring, created_at, last_refreshed_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (comparison_id, json.dumps(areas), json.dumps(results), False, now, now),
            )
        connection.commit()
    return get_comparison(comparison_id)


def get_comparison(comparison_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM neighborhood_comparisons WHERE comparison_id = %s", (comparison_id,))
            row = cursor.fetchone()
    if row is None:
        return None
    result = dict(row)
    result["areas"] = json.loads(result["areas"])
    result["results"] = json.loads(result["results"])
    return result


def update_comparison_results(comparison_id: str, results: list[dict[str, Any]]) -> None:
    """Overwrites a comparison's cached results after a refresh (manual
    or the hourly monitoring loop) — the areas being compared don't
    change on a refresh, only the data about them."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE neighborhood_comparisons SET results = %s, last_refreshed_at = %s WHERE comparison_id = %s",
                (json.dumps(results), now, comparison_id),
            )
        connection.commit()


def set_monitoring(comparison_id: str, monitoring: bool) -> Optional[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE neighborhood_comparisons SET monitoring = %s WHERE comparison_id = %s",
                (monitoring, comparison_id),
            )
        connection.commit()
    return get_comparison(comparison_id)


def list_monitored_comparisons() -> list[dict[str, Any]]:
    """For the hourly background scheduler to iterate — only
    comparisons someone has actually opted into "keep monitoring" for;
    everyone else's one-off comparison just sits there unchanged
    (and un-refreshed) until they come back and ask for a new one."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM neighborhood_comparisons WHERE monitoring = TRUE")
            rows = cursor.fetchall()
    results = []
    for row in rows:
        result = dict(row)
        result["areas"] = json.loads(result["areas"])
        results.append(result)
    return results
