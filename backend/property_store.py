import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from backend.db import get_connection


def initialize_property_store() -> None:
    """Two tables: `properties` (one physical plot — plot spec, shared
    materials/labor selections, shared site elements like a pool or
    driveway, lock state) and `property_floors` (many per property — each
    floor's own room layout). Site elements and material selections live
    at the property level, not per floor, since a pool or a choice of
    flooring tile realistically applies to the whole build, not one floor
    — matching how the rest of Construction Studio already treats these."""

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS properties (
                    property_id TEXT PRIMARY KEY,
                    user_email TEXT NOT NULL,
                    name TEXT NOT NULL,
                    plot_spec TEXT NOT NULL,
                    selections TEXT NOT NULL,
                    labor_selections TEXT NOT NULL,
                    site_elements TEXT NOT NULL,
                    locked INTEGER NOT NULL DEFAULT 0,
                    locked_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS property_floors (
                    floor_id TEXT PRIMARY KEY,
                    property_id TEXT NOT NULL REFERENCES properties(property_id) ON DELETE CASCADE,
                    floor_number INTEGER NOT NULL,
                    floor_label TEXT NOT NULL,
                    rooms TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_properties_user_email ON properties(user_email)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_property_floors_property_id ON property_floors(property_id)"
            )
        connection.commit()


def _row_to_property(row: dict[str, Any], floors: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "property_id": row["property_id"],
        "user_email": row["user_email"],
        "name": row["name"],
        "plot_spec": json.loads(row["plot_spec"]),
        "selections": json.loads(row["selections"]),
        "labor_selections": json.loads(row["labor_selections"]),
        "site_elements": json.loads(row["site_elements"]),
        "locked": bool(row["locked"]),
        "locked_at": row["locked_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "floors": floors,
    }


def _row_to_floor(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "floor_id": row["floor_id"],
        "property_id": row["property_id"],
        "floor_number": row["floor_number"],
        "floor_label": row["floor_label"],
        "rooms": json.loads(row["rooms"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def count_saved_properties(user_email: str) -> int:
    """How many properties this user currently has saved — checked against
    the tier's saved_designs_limit before allowing a new save."""
    user_email = user_email.strip().lower()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM properties WHERE user_email = %s", (user_email,))
            return cursor.fetchone()["n"]


def create_property(
    *,
    user_email: str,
    name: str,
    plot_spec: dict[str, Any],
    selections: dict[str, str],
    labor_selections: dict[str, str],
    site_elements: list[dict[str, Any]],
    floors: list[dict[str, Any]],
) -> dict[str, Any]:
    """`floors` = [{"floor_number": int, "floor_label": str, "rooms": [...]}, ...] — at least one required."""
    user_email = user_email.strip().lower()
    property_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO properties (
                    property_id, user_email, name, plot_spec, selections, labor_selections,
                    site_elements, locked, locked_at, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 0, NULL, %s, %s)
                """,
                (
                    property_id, user_email, name, json.dumps(plot_spec), json.dumps(selections),
                    json.dumps(labor_selections), json.dumps(site_elements), now, now,
                ),
            )
            for floor in floors:
                cursor.execute(
                    """
                    INSERT INTO property_floors (
                        floor_id, property_id, floor_number, floor_label, rooms, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid.uuid4()), property_id, floor["floor_number"], floor["floor_label"],
                        json.dumps(floor["rooms"]), now, now,
                    ),
                )
        connection.commit()

    return get_property(property_id)


def list_properties_for_user(user_email: str) -> list[dict[str, Any]]:
    """Summary list for the Studio landing page — doesn't include full
    floor room data, just enough to show a picker (name, plot size,
    floor count, lock state, last updated)."""
    user_email = user_email.strip().lower()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM properties WHERE user_email = %s ORDER BY updated_at DESC",
                (user_email,),
            )
            rows = cursor.fetchall()
            summaries = []
            for row in rows:
                cursor.execute(
                    "SELECT COUNT(*) AS n FROM property_floors WHERE property_id = %s",
                    (row["property_id"],),
                )
                floor_count = cursor.fetchone()["n"]
                plot_spec = json.loads(row["plot_spec"])
                summaries.append({
                    "property_id": row["property_id"],
                    "name": row["name"],
                    "plot_size_sqft": plot_spec.get("plot_size_sqft"),
                    "floor_count": floor_count,
                    "locked": bool(row["locked"]),
                    "updated_at": row["updated_at"],
                    # Needed by the Studio designs list to flag a design
                    # as cross-site (belongs to a different country than
                    # the current site) directly on the list itself,
                    # without fetching each design's full details first —
                    # a real reported gap: cross-site locking previously
                    # only kicked in once a design was already opened.
                    "country": plot_spec.get("country"),
                })
            return summaries


def get_property(property_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM properties WHERE property_id = %s", (property_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            cursor.execute(
                "SELECT * FROM property_floors WHERE property_id = %s ORDER BY floor_number ASC",
                (property_id,),
            )
            floors = [_row_to_floor(r) for r in cursor.fetchall()]
            return _row_to_property(row, floors)


def update_property(
    *,
    property_id: str,
    name: Optional[str] = None,
    plot_spec: Optional[dict[str, Any]] = None,
    selections: Optional[dict[str, str]] = None,
    labor_selections: Optional[dict[str, str]] = None,
    site_elements: Optional[list[dict[str, Any]]] = None,
) -> Optional[dict[str, Any]]:
    """Partial update — only provided fields change. Refuses to modify a
    locked property (callers must unlock first via the OTP-gated flow)."""
    existing = get_property(property_id)
    if existing is None:
        return None
    if existing["locked"]:
        raise PermissionError("property is locked")

    now = datetime.now(timezone.utc).isoformat()
    fields = {
        "name": name if name is not None else existing["name"],
        "plot_spec": json.dumps(plot_spec if plot_spec is not None else existing["plot_spec"]),
        "selections": json.dumps(selections if selections is not None else existing["selections"]),
        "labor_selections": json.dumps(labor_selections if labor_selections is not None else existing["labor_selections"]),
        "site_elements": json.dumps(site_elements if site_elements is not None else existing["site_elements"]),
    }

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE properties SET
                    name = %s, plot_spec = %s, selections = %s, labor_selections = %s,
                    site_elements = %s, updated_at = %s
                WHERE property_id = %s
                """,
                (fields["name"], fields["plot_spec"], fields["selections"], fields["labor_selections"],
                 fields["site_elements"], now, property_id),
            )
        connection.commit()

    return get_property(property_id)


def upsert_floor(*, property_id: str, floor_id: Optional[str], floor_number: int, floor_label: str, rooms: list[dict[str, Any]]) -> dict[str, Any]:
    """Creates a new floor if floor_id is None, otherwise updates the
    existing one. Refuses on a locked property."""
    existing = get_property(property_id)
    if existing is None:
        raise ValueError("property not found")
    if existing["locked"]:
        raise PermissionError("property is locked")

    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            if floor_id:
                cursor.execute(
                    """
                    UPDATE property_floors SET floor_number = %s, floor_label = %s, rooms = %s, updated_at = %s
                    WHERE floor_id = %s AND property_id = %s
                    """,
                    (floor_number, floor_label, json.dumps(rooms), now, floor_id, property_id),
                )
            else:
                floor_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO property_floors (floor_id, property_id, floor_number, floor_label, rooms, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (floor_id, property_id, floor_number, floor_label, json.dumps(rooms), now, now),
                )
            cursor.execute("UPDATE properties SET updated_at = %s WHERE property_id = %s", (now, property_id))
        connection.commit()

    return get_property(property_id)


def delete_floor(*, property_id: str, floor_id: str) -> None:
    existing = get_property(property_id)
    if existing is None:
        raise ValueError("property not found")
    if existing["locked"]:
        raise PermissionError("property is locked")
    if len(existing["floors"]) <= 1:
        raise ValueError("cannot delete the only floor — a property must have at least one")

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM property_floors WHERE floor_id = %s AND property_id = %s",
                (floor_id, property_id),
            )
        connection.commit()


def sync_property(
    *,
    property_id: str,
    name: Optional[str] = None,
    plot_spec: Optional[dict[str, Any]] = None,
    selections: Optional[dict[str, str]] = None,
    labor_selections: Optional[dict[str, str]] = None,
    site_elements: Optional[list[dict[str, Any]]] = None,
    floors: list[dict[str, Any]],
) -> dict[str, Any]:
    """Saves the property's fields AND its complete floor set in ONE
    database round-trip, instead of the old pattern of one HTTP request
    for the property fields plus one more per floor plus a final re-fetch
    — that chain meant more requests, more chances for any single one to
    fail (a real "Failed to fetch" report traced to exactly this), and a
    real correctness bug: floors removed locally were never actually
    deleted server-side (upsert-only, never sync), so a deleted floor
    would silently reappear on the next load.

    `floors` is the COMPLETE current set — each with an optional floor_id
    (present = update in place, absent = brand new). Any existing floor
    NOT included here is deleted. Must include at least one floor."""

    if not floors:
        raise ValueError("a property must have at least one floor")

    existing = get_property(property_id)
    if existing is None:
        raise ValueError("property not found")
    if existing["locked"]:
        raise PermissionError("property is locked")

    now = datetime.now(timezone.utc).isoformat()
    fields = {
        "name": name if name is not None else existing["name"],
        "plot_spec": json.dumps(plot_spec if plot_spec is not None else existing["plot_spec"]),
        "selections": json.dumps(selections if selections is not None else existing["selections"]),
        "labor_selections": json.dumps(labor_selections if labor_selections is not None else existing["labor_selections"]),
        "site_elements": json.dumps(site_elements if site_elements is not None else existing["site_elements"]),
    }

    incoming_floor_ids = {f["floor_id"] for f in floors if f.get("floor_id")}

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE properties SET
                    name = %s, plot_spec = %s, selections = %s, labor_selections = %s,
                    site_elements = %s, updated_at = %s
                WHERE property_id = %s
                """,
                (fields["name"], fields["plot_spec"], fields["selections"], fields["labor_selections"],
                 fields["site_elements"], now, property_id),
            )

            # Delete any floor that existed before but isn't in this save.
            for existing_floor in existing["floors"]:
                if existing_floor["floor_id"] not in incoming_floor_ids:
                    cursor.execute(
                        "DELETE FROM property_floors WHERE floor_id = %s AND property_id = %s",
                        (existing_floor["floor_id"], property_id),
                    )

            for floor in floors:
                floor_id = floor.get("floor_id")
                if floor_id:
                    cursor.execute(
                        """
                        UPDATE property_floors SET floor_number = %s, floor_label = %s, rooms = %s, updated_at = %s
                        WHERE floor_id = %s AND property_id = %s
                        """,
                        (floor["floor_number"], floor["floor_label"], json.dumps(floor["rooms"]), now,
                         floor_id, property_id),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO property_floors (floor_id, property_id, floor_number, floor_label, rooms, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (str(uuid.uuid4()), property_id, floor["floor_number"], floor["floor_label"],
                         json.dumps(floor["rooms"]), now, now),
                    )
        connection.commit()

    return get_property(property_id)


def set_locked(*, property_id: str, locked: bool) -> Optional[dict[str, Any]]:
    """Locking never requires extra verification (protecting your own
    work is always allowed). Unlocking's OTP gate is enforced by the
    caller (api.py) BEFORE this is invoked — this function just flips the
    flag once that's already been confirmed."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE properties SET locked = %s, locked_at = %s, updated_at = %s WHERE property_id = %s",
                (1 if locked else 0, now if locked else None, now, property_id),
            )
        connection.commit()
    return get_property(property_id)


def delete_property(property_id: str) -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM properties WHERE property_id = %s", (property_id,))
        connection.commit()
