"""PropertyIQ "Price Drop Alert" — watches a property's price against a
user-set target, emailing them when it's reached.

Honest, deliberate design constraint, not an oversight: PropertyIQ has no
live feed into any listing site — the only way to genuinely learn a
property's current price is either (a) re-running the same free/paid
extraction the property_url_import feature already uses, if the watch was
created from a URL, or (b) the user manually telling us their price
changed, if the watch was created from manual price/city/type/area entry
(no URL to re-check). A manual-entry watch's "current price" therefore
never changes on its own — it only updates via update_watch_price, called
explicitly by the user. This is stated plainly to the user in the
frontend, not silently glossed over as if it "watches" a listing it has
no actual way to observe.

The periodic re-check itself (backend/price_watch_scheduler.py) runs as
an asyncio background task within this same FastAPI process — a real,
working choice given Render's standard web-service tier keeps the
process running continuously, rather than requiring a separate paid cron
service.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from backend.db import get_connection


def initialize_price_watch_store() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS price_watches (
                    watch_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    url TEXT,
                    price DOUBLE PRECISION NOT NULL,
                    city TEXT NOT NULL,
                    property_type TEXT NOT NULL,
                    area_value DOUBLE PRECISION NOT NULL,
                    area_unit TEXT NOT NULL,
                    target_price DOUBLE PRECISION NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_checked_at TEXT
                )
                """
            )
            cursor.execute(
                "ALTER TABLE price_watches ADD COLUMN IF NOT EXISTS location TEXT"
            )
        connection.commit()


def create_price_watch(
    *,
    email: str,
    price: float,
    city: str,
    property_type: str,
    area_value: float,
    target_price: float,
    area_unit: str = "sqft",
    url: Optional[str] = None,
    location: Optional[str] = None,
) -> dict[str, Any]:
    """Creates a watch. Persistence only — resolving price/city/
    property_type/area_value from a listing URL (when the caller hasn't
    already supplied them manually) is the API layer's job
    (api_create_price_watch in api.py), which has its own fallback
    rules for what's strictly required vs nice-to-have from a real
    extraction. Keeping that resolution logic in exactly one place
    avoids the two layers silently disagreeing about it.

    `location` is stored and returned for context/display only — see
    compute_instant_score's own docstring for why it doesn't (yet)
    change the underlying scoring, which is city-level."""
    if price <= 0 or area_value <= 0 or target_price <= 0:
        raise ValueError("Price, area, and target price must all be greater than zero.")
    if area_unit not in ("sqft", "sqm"):
        raise ValueError("area_unit must be 'sqft' or 'sqm'.")
    if "@" not in email:
        raise ValueError("A valid email is required to be notified.")
    if not city or not city.strip():
        raise ValueError("City is required.")
    if not property_type or not property_type.strip():
        raise ValueError("Property type is required.")

    watch_id = uuid.uuid4().hex[:10]
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO price_watches
                    (watch_id, email, url, price, city, property_type, area_value, area_unit,
                     target_price, status, created_at, last_checked_at, location)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (watch_id, email, url, price, city, property_type, area_value, area_unit,
                 target_price, "active", now, None, location),
            )
        connection.commit()

    return get_price_watch(watch_id)


def get_price_watch(watch_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM price_watches WHERE watch_id = %s", (watch_id,))
            row = cursor.fetchone()
    if row is None:
        return None
    return dict(row)


def list_active_url_watches() -> list[dict[str, Any]]:
    """Only URL-based watches can be genuinely, automatically re-checked
    — a manual-entry watch has no source to re-fetch from, so it's
    deliberately excluded here; it only changes via update_watch_price."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM price_watches WHERE status = 'active' AND url IS NOT NULL"
            )
            rows = cursor.fetchall()
    return [dict(row) for row in rows]


def count_active_watches_for_email(email: str) -> int:
    """Backs the per-tier max_price_watches limit — counts only
    'active' watches (a 'triggered' one has already served its purpose
    and shouldn't count against the limit, letting a user watch a new
    property once an old watch fires)."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS count FROM price_watches WHERE email = %s AND status = 'active'",
                (email,),
            )
            row = cursor.fetchone()
    return row["count"] if row else 0


def update_watch_price(watch_id: str, new_price: float) -> dict[str, Any]:
    """Lets a user with a manual-entry (no-URL) watch tell PropertyIQ
    their price changed — the only way that kind of watch can ever
    reflect a new price, since there's nothing to automatically
    re-fetch. Also re-evaluates against the target immediately."""
    if new_price <= 0:
        raise ValueError("Price must be greater than zero.")

    watch = get_price_watch(watch_id)
    if watch is None:
        raise ValueError(f"No price watch found with id {watch_id!r}.")

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE price_watches SET price = %s WHERE watch_id = %s",
                (new_price, watch_id),
            )
        connection.commit()

    return check_price_watch(watch_id)


def _mark_checked(watch_id: str, new_price: Optional[float], triggered: bool) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            if new_price is not None:
                cursor.execute(
                    "UPDATE price_watches SET last_checked_at = %s, price = %s, "
                    "status = %s WHERE watch_id = %s",
                    (now, new_price, "triggered" if triggered else "active", watch_id),
                )
            else:
                cursor.execute(
                    "UPDATE price_watches SET last_checked_at = %s, "
                    "status = %s WHERE watch_id = %s",
                    (now, "triggered" if triggered else "active", watch_id),
                )
        connection.commit()


def check_price_watch(watch_id: str, send_email_on_trigger: bool = True) -> dict[str, Any]:
    """Re-evaluates one watch against its target. For a URL-based watch,
    re-fetches and re-extracts the current price first (the genuine
    "watching" this feature can actually do); for a manual-entry watch,
    just re-evaluates whatever price is currently stored (unchanged
    unless update_watch_price was called first). Sends an email and
    marks the watch "triggered" the first time the price reaches the
    target — never re-sends for an already-triggered watch. Raises
    ValueError if the watch doesn't exist."""
    watch = get_price_watch(watch_id)
    if watch is None:
        raise ValueError(f"No price watch found with id {watch_id!r}.")

    if watch["status"] == "triggered":
        return watch  # already notified once; nothing further to do

    current_price = watch["price"]
    new_price_from_refetch = None

    if watch["url"]:
        # Imported here (not at module load) to avoid a circular import,
        # same reasoning as challenge_store's reveal function.
        from backend.property_url_extract import extract_property_data
        try:
            extracted = extract_property_data(watch["url"])
            if extracted.get("quotedPrice"):
                current_price = extracted["quotedPrice"]
                new_price_from_refetch = current_price
        except Exception:
            # A fetch failure (site blocked, temporarily down, etc) during
            # a background re-check must not crash the whole check loop —
            # just leave this watch's price as it was, try again next cycle.
            pass

    triggered = current_price <= watch["target_price"]

    if triggered and send_email_on_trigger:
        from backend.auth import send_email
        try:
            send_email(
                watch["email"],
                "PropertyIQ: this property just hit your target price",
                f"<p>Good news — the property you're watching in {watch['city']} just reached "
                f"your target price.</p>"
                f"<p><strong>Your target:</strong> {watch['target_price']:,.0f}<br>"
                f"<strong>Current price:</strong> {current_price:,.0f}</p>"
                f"<p>This might be a good time to take a closer look.</p>"
            )
        except Exception:
            # Don't let an email-sending failure prevent the watch from
            # being correctly marked triggered — the price genuinely did
            # cross the target regardless of whether the notification
            # itself succeeded.
            pass

    _mark_checked(watch_id, new_price_from_refetch, triggered)
    return get_price_watch(watch_id)
