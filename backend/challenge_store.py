"""PropertyIQ "Should I Buy This?" Challenge — a shareable, no-account
prediction game. A user creates a challenge for a specific property
(price/city/type/area, the same minimal input as the other quick-check
features); anyone with the link can view it, guess a price, and see how
their guess compares to PropertyIQ's real, comparables-backed fair value
— all without an account. Genuinely new infrastructure compared to the
other quick-check features: this one needs persistent storage, since a
challenge must remain viewable via a stable link long after creation, to
however many different recipients open it.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from backend.db import get_connection


def initialize_challenge_store() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS property_challenges (
                    challenge_id TEXT PRIMARY KEY,
                    price DOUBLE PRECISION NOT NULL,
                    city TEXT NOT NULL,
                    property_type TEXT NOT NULL,
                    area_value DOUBLE PRECISION NOT NULL,
                    area_unit TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            # A separate, safe migration for a table that may already
            # exist in production without this column — ADD COLUMN IF
            # NOT EXISTS never touches or drops any existing row's data.
            cursor.execute(
                "ALTER TABLE property_challenges ADD COLUMN IF NOT EXISTS location TEXT"
            )
        connection.commit()


def create_challenge(
    *,
    price: float,
    city: str,
    property_type: str,
    area_value: float,
    area_unit: str = "sqft",
    location: Optional[str] = None,
) -> dict[str, Any]:
    """Creates a new shareable challenge and returns its full record,
    including the generated challenge_id the caller uses to build the
    shareable link. No account/email required — matching the feature's
    own explicit "no account required" design.

    `location` (a specific locality/neighborhood) is stored and returned
    for context/display only — see compute_instant_score's own docstring
    for why it doesn't (yet) change the underlying scoring, which is
    city-level."""
    if price <= 0 or area_value <= 0:
        raise ValueError("Price and area must both be greater than zero.")
    if area_unit not in ("sqft", "sqm"):
        raise ValueError("area_unit must be 'sqft' or 'sqm'.")
    if not city or not city.strip():
        raise ValueError("City is required.")
    if not property_type or not property_type.strip():
        raise ValueError("Property type is required.")

    challenge_id = uuid.uuid4().hex[:10]
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO property_challenges
                    (challenge_id, price, city, property_type, area_value, area_unit, location, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (challenge_id, price, city, property_type, area_value, area_unit, location, now),
            )
        connection.commit()

    return {
        "challenge_id": challenge_id,
        "price": price,
        "city": city,
        "property_type": property_type,
        "area_value": area_value,
        "area_unit": area_unit,
        "location": location,
        "created_at": now,
    }


def get_challenge(challenge_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM property_challenges WHERE challenge_id = %s",
                (challenge_id,),
            )
            row = cursor.fetchone()
    if row is None:
        return None
    return {
        "challenge_id": row["challenge_id"],
        "price": row["price"],
        "city": row["city"],
        "property_type": row["property_type"],
        "area_value": row["area_value"],
        "area_unit": row["area_unit"],
        "location": row.get("location"),
        "created_at": row["created_at"],
    }


def reveal_challenge_guess(challenge_id: str, guessed_price: float) -> dict[str, Any]:
    """Reveals how a recipient's guess compares to PropertyIQ's real,
    comparables-backed fair value. Deliberately reuses compute_instant_score
    and find_hidden_deal_insights internally rather than re-implementing
    the same price-vs-comparables math — so a challenge's reveal can
    never disagree with what Instant Score/Hidden Deal would say about
    the exact same property. Raises ValueError if the challenge doesn't
    exist, or if guessed_price isn't a positive number."""
    if guessed_price <= 0:
        raise ValueError("guessed_price must be greater than zero.")

    challenge = get_challenge(challenge_id)
    if challenge is None:
        raise ValueError(f"No challenge found with id {challenge_id!r}.")

    # Imported here, not at module load time, to avoid a circular import
    # (instant_score/hidden_deal don't need to know about challenges at
    # all, so this module depends on them, not the other way around).
    from backend.instant_score import compute_instant_score
    from backend.hidden_deal import find_hidden_deal_insights

    score_result = compute_instant_score(
        price=challenge["price"], city=challenge["city"], property_type=challenge["property_type"],
        area_value=challenge["area_value"], area_unit=challenge["area_unit"], location=challenge.get("location"),
    )
    deal_result = find_hidden_deal_insights(
        price=challenge["price"], city=challenge["city"], property_type=challenge["property_type"],
        area_value=challenge["area_value"], area_unit=challenge["area_unit"], location=challenge.get("location"),
    )

    if score_result["coverage"] == "unsupported":
        return {
            "coverage": "unsupported",
            "challenge": challenge,
            "guessed_price": guessed_price,
            "reason": score_result["reason"],
        }

    area_sqft = challenge["area_value"] * 10.7639 if challenge["area_unit"] == "sqm" else challenge["area_value"]
    fair_value = round(score_result["market_average_price_per_sqft"] * area_sqft)
    guess_diff_percent = round(((guessed_price - fair_value) / fair_value) * 100) if fair_value else 0

    return {
        "coverage": "supported",
        "challenge": challenge,
        "guessed_price": guessed_price,
        "fair_value": fair_value,
        "market_position": score_result["label"],
        "score": score_result["score"],
        "guess_diff_percent": guess_diff_percent,
        "findings": deal_result["findings"],
    }

