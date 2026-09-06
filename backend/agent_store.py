"""Agent Intelligence: a workspace layer on top of everything else this
app already does. An agent (a paying Studio subscriber whose tier
includes the "agent_intelligence" feature) organizes real clients and
real properties, then generates one consolidated advisory report per
property by calling the exact same functions the rest of the app
already uses (assessment, neighborhood insights, EMI, cost of living)
— this module is purely the CRUD layer underneath that; the report
itself is built in agent_report.py.

Two tables, same real quota/race-safety pattern as saved_designs_limit
elsewhere in this app: `agent_clients` (an agent's own client list) and
`agent_client_properties` (each client's own properties, using the
exact same fields PropertyRequest already defines — no new schema
invented for what's already a well-defined shape).
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from backend.db import get_connection


def initialize_agent_store() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_clients (
                    client_id TEXT PRIMARY KEY,
                    agent_email TEXT NOT NULL,
                    client_name TEXT NOT NULL,
                    client_contact TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute("ALTER TABLE agent_clients ADD COLUMN IF NOT EXISTS requirements TEXT")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_client_properties (
                    property_id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
                    agent_email TEXT NOT NULL,
                    property_payload TEXT NOT NULL,
                    lat REAL,
                    lon REAL,
                    created_at TEXT NOT NULL
                )
                """
            )
            cursor.execute(
                "ALTER TABLE agent_client_properties ADD COLUMN IF NOT EXISTS stage TEXT NOT NULL DEFAULT 'Lead'"
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_clients_email ON agent_clients (agent_email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_agent_props_client ON agent_client_properties (client_id)")
        connection.commit()


def count_clients_for_agent(agent_email: str) -> int:
    agent_email = agent_email.strip().lower()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM agent_clients WHERE agent_email = %s", (agent_email,))
            return cursor.fetchone()["n"]


def count_properties_for_client(client_id: str) -> int:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS n FROM agent_client_properties WHERE client_id = %s", (client_id,))
            return cursor.fetchone()["n"]


def create_client_if_under_limit(*, limit: Optional[int], agent_email: str, client_name: str, client_contact: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Same real, race-safe check-and-insert pattern as
    save_design_if_under_quota/create_property_if_under_limit
    elsewhere in this app — a Postgres advisory transaction lock keyed
    per-agent, the real count re-read inside that lock immediately
    before the insert, not two separate, racy operations."""
    agent_email = agent_email.strip().lower()
    if not client_name or not client_name.strip():
        raise ValueError("Client name is required.")

    client_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (agent_email,))
            if limit is not None:
                cursor.execute("SELECT COUNT(*) AS n FROM agent_clients WHERE agent_email = %s", (agent_email,))
                if cursor.fetchone()["n"] >= limit:
                    connection.rollback()
                    return None
            cursor.execute(
                "INSERT INTO agent_clients (client_id, agent_email, client_name, client_contact, created_at) VALUES (%s, %s, %s, %s, %s)",
                (client_id, agent_email, client_name.strip(), client_contact, now),
            )
        connection.commit()
    return get_client(client_id)


def get_client(client_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM agent_clients WHERE client_id = %s", (client_id,))
            row = cursor.fetchone()
    return dict(row) if row else None


def list_clients_for_agent(agent_email: str) -> list[dict[str, Any]]:
    agent_email = agent_email.strip().lower()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM agent_clients WHERE agent_email = %s ORDER BY created_at DESC", (agent_email,))
            rows = cursor.fetchall()
    return [dict(row) for row in rows]


def update_client(*, client_id: str, client_name: str, client_contact: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Editing never touches the client-count quota — it's the same
    row, not a new one — so no limit check is needed here, unlike
    create_client_if_under_limit."""
    if not client_name or not client_name.strip():
        raise ValueError("Client name is required.")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE agent_clients SET client_name = %s, client_contact = %s WHERE client_id = %s",
                (client_name.strip(), client_contact, client_id),
            )
        connection.commit()
    return get_client(client_id)


def update_client_requirements(*, client_id: str, requirements: Optional[str]) -> Optional[dict[str, Any]]:
    """A separate, focused update — same reasoning as
    update_property_stage — rather than folding this into
    update_client, since requirements is edited independently
    (typically from the requirements-search box itself, not the
    client-details edit form)."""
    cleaned = requirements.strip() if requirements and requirements.strip() else None
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE agent_clients SET requirements = %s WHERE client_id = %s",
                (cleaned, client_id),
            )
        connection.commit()
    return get_client(client_id)


def delete_client(client_id: str) -> None:
    """Cascades to the client's own properties too -- a deleted client
    has no real, ongoing reason to keep an orphaned property list
    around, and this also correctly frees the agent's own client-count
    quota slot without leaving unreachable property rows behind."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM agent_client_properties WHERE client_id = %s", (client_id,))
            cursor.execute("DELETE FROM agent_clients WHERE client_id = %s", (client_id,))
        connection.commit()


def create_client_property_if_under_limit(*, limit: Optional[int], client_id: str, agent_email: str, property_payload: dict[str, Any], lat: Optional[float] = None, lon: Optional[float] = None) -> Optional[dict[str, Any]]:
    """Same real, race-safe pattern as create_client_if_under_limit,
    keyed by client_id this time (max_properties_per_client is a
    per-client limit, not a per-agent one)."""
    property_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (client_id,))
            if limit is not None:
                cursor.execute("SELECT COUNT(*) AS n FROM agent_client_properties WHERE client_id = %s", (client_id,))
                if cursor.fetchone()["n"] >= limit:
                    connection.rollback()
                    return None
            cursor.execute(
                "INSERT INTO agent_client_properties (property_id, client_id, agent_email, property_payload, lat, lon, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (property_id, client_id, agent_email.strip().lower(), json.dumps(property_payload), lat, lon, now),
            )
        connection.commit()
    return get_client_property(property_id)


def get_client_property(property_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM agent_client_properties WHERE property_id = %s", (property_id,))
            row = cursor.fetchone()
    if row is None:
        return None
    result = dict(row)
    result["property_payload"] = json.loads(result["property_payload"])
    return result


def list_properties_for_client(client_id: str) -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM agent_client_properties WHERE client_id = %s ORDER BY created_at DESC", (client_id,))
            rows = cursor.fetchall()
    results = []
    for row in rows:
        result = dict(row)
        result["property_payload"] = json.loads(result["property_payload"])
        results.append(result)
    return results


# The real workflow every agent's own deal genuinely moves through,
# in order -- shared here (not duplicated per-caller) so the backend
# validates against the same list the frontend renders as a dropdown.
PIPELINE_STAGES = [
    "Lead", "Evaluation", "Shortlisted", "Client Viewed",
    "Site Visit", "Negotiation", "Due Diligence", "Deal", "Lost",
]


def update_client_property(*, property_id: str, property_payload: dict[str, Any], lat: Optional[float] = None, lon: Optional[float] = None) -> Optional[dict[str, Any]]:
    """Same real reasoning as update_client — editing an existing
    property doesn't touch the per-client property-count quota, since
    it's the same row, not a new one."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE agent_client_properties SET property_payload = %s, lat = %s, lon = %s WHERE property_id = %s",
                (json.dumps(property_payload), lat, lon, property_id),
            )
        connection.commit()
    return get_client_property(property_id)


def update_property_stage(*, property_id: str, stage: str) -> Optional[dict[str, Any]]:
    if stage not in PIPELINE_STAGES:
        raise ValueError(f"Invalid stage. Must be one of: {', '.join(PIPELINE_STAGES)}")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE agent_client_properties SET stage = %s WHERE property_id = %s",
                (stage, property_id),
            )
        connection.commit()
    return get_client_property(property_id)


def delete_client_property(property_id: str) -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM agent_client_properties WHERE property_id = %s", (property_id,))
        connection.commit()
