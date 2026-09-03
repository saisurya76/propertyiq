import json
from datetime import datetime, timezone
from typing import Any, Optional

from backend.db import get_connection


def initialize_construction_store() -> None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS construction_designs (
                    design_id TEXT PRIMARY KEY,
                    user_email TEXT NOT NULL,
                    region TEXT NOT NULL,
                    currency TEXT NOT NULL,
                    plot_spec TEXT NOT NULL,
                    selections TEXT NOT NULL,
                    cost_estimate TEXT NOT NULL,
                    vastu_result TEXT,
                    risks TEXT,
                    dxf_path TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            # A real admin lever for a real support scenario: a customer
            # whose monthly generate quota was consumed by a bug, a
            # confusing UI moment, or anything else worth a goodwill
            # reset, without waiting for the calendar month to roll
            # over. Deliberately NOT deleting rows from
            # construction_designs itself to achieve this -- that table
            # is a genuine generate-history log (see count_designs_this_
            # month's own docstring), and destroying real history to
            # fake a lower count would make the log dishonest for any
            # future audit/support need. Instead, count_designs_this_
            # month only counts designs created AFTER the user's most
            # recent reset (if one exists and falls within the current
            # month) -- the full history stays intact, just no longer
            # counted against this month's quota from that point on.
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS quota_resets (
                    user_email TEXT PRIMARY KEY,
                    reset_at TEXT NOT NULL,
                    admin_note TEXT
                )
                """
            )
        connection.commit()


def save_design(
    *,
    design_id: str,
    user_email: str,
    region: str,
    currency: str,
    plot_spec: dict[str, Any],
    selections: dict[str, str],
    cost_estimate: dict[str, Any],
    vastu_result: Optional[dict[str, Any]] = None,
    risks: Optional[list[str]] = None,
    dxf_path: Optional[str] = None,
) -> None:
    # Normalized here for the same reason count_designs_this_month now
    # normalizes its own parameter: every real caller today already
    # passes an already-lowercased email (the session layer normalizes
    # at login), but storing it un-normalized would make this table
    # silently inconsistent with quota_resets/count_designs_this_month
    # the moment any future caller passed a differently-cased one.
    user_email = user_email.strip().lower()
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO construction_designs (
                    design_id, user_email, region, currency, plot_spec, selections,
                    cost_estimate, vastu_result, risks, dxf_path, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    design_id,
                    user_email,
                    region,
                    currency,
                    json.dumps(plot_spec, separators=(",", ":")),
                    json.dumps(selections, separators=(",", ":")),
                    json.dumps(cost_estimate, separators=(",", ":")),
                    json.dumps(vastu_result, separators=(",", ":")) if vastu_result else None,
                    json.dumps(risks, separators=(",", ":")) if risks else None,
                    dxf_path,
                    now,
                    now,
                ),
            )
        connection.commit()


def save_design_if_under_quota(
    *,
    quota: Optional[int],
    design_id: str,
    user_email: str,
    region: str,
    currency: str,
    plot_spec: dict[str, Any],
    selections: dict[str, str],
    cost_estimate: dict[str, Any],
    vastu_result: Optional[dict[str, Any]] = None,
    risks: Optional[list[str]] = None,
    dxf_path: Optional[str] = None,
) -> bool:
    """The real, race-safe version of the quota-then-save sequence the
    generate-design endpoint needs. A real, previously-unfixed gap:
    the endpoint's own quota check (count_designs_this_month) and the
    actual save happened as two entirely separate, unsynchronized
    operations, with real work in between (Vastu compliance checking,
    risk identification, DXF file generation) — a genuine window where
    two concurrent requests from the same user could each pass the
    quota check before either one's save landed, letting them generate
    more designs in a month than their tier actually allows.

    Fixed with a real Postgres advisory transaction lock
    (pg_advisory_xact_lock), keyed by a hash of the user's own email
    (not a single global lock, which would serialize every user's
    saves against each other) — held for the lifetime of this one
    transaction, automatically released on commit or rollback. Re-
    counts this month's real designs INSIDE that lock, immediately
    before the insert, so two concurrent calls for the same user are
    forced to run this check-then-insert sequence one at a time rather
    than interleaving. Returns False (and saves nothing) if the quota
    would be exceeded — the caller is responsible for turning that
    into the actual 403 response, since only it knows the tier's
    label/limit for a clear error message.

    Deliberately a new function rather than changing save_design
    itself: this locked, quota-aware path is specific to the one real
    caller that needs race-safety (the generate-design endpoint);
    other callers of the plain save_design (if any exist or are added
    later) aren't quota-gated at all and shouldn't pay for a lock they
    don't need."""
    user_email = user_email.strip().lower()
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            # hashtext() is Postgres's own stable string hash — using it
            # (rather than Python's hash(), which isn't stable across
            # process restarts by design) means the same email always
            # maps to the same lock key, which is what actually makes
            # this serialize correctly across separate requests/workers.
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (user_email,))

            if quota is not None:
                month_prefix = now[:7]
                reset = get_quota_reset(user_email)
                if reset and reset["reset_at"].startswith(month_prefix):
                    cursor.execute(
                        "SELECT COUNT(*) as cnt FROM construction_designs WHERE user_email = %s AND created_at > %s",
                        (user_email, reset["reset_at"]),
                    )
                else:
                    cursor.execute(
                        "SELECT COUNT(*) as cnt FROM construction_designs WHERE user_email = %s AND created_at LIKE %s",
                        (user_email, f"{month_prefix}%"),
                    )
                used = cursor.fetchone()["cnt"]
                if used >= quota:
                    connection.rollback()
                    return False

            cursor.execute(
                """
                INSERT INTO construction_designs (
                    design_id, user_email, region, currency, plot_spec, selections,
                    cost_estimate, vastu_result, risks, dxf_path, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    design_id,
                    user_email,
                    region,
                    currency,
                    json.dumps(plot_spec, separators=(",", ":")),
                    json.dumps(selections, separators=(",", ":")),
                    json.dumps(cost_estimate, separators=(",", ":")),
                    json.dumps(vastu_result, separators=(",", ":")) if vastu_result else None,
                    json.dumps(risks, separators=(",", ":")) if risks else None,
                    dxf_path,
                    now,
                    now,
                ),
            )
        connection.commit()
    return True


def get_design(design_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM construction_designs WHERE design_id = %s",
                (design_id,),
            )
            row = cursor.fetchone()

    if row is None:
        return None

    result = dict(row)
    result["plot_spec"] = json.loads(result["plot_spec"])
    result["selections"] = json.loads(result["selections"])
    result["cost_estimate"] = json.loads(result["cost_estimate"])
    result["vastu_result"] = json.loads(result["vastu_result"]) if result["vastu_result"] else None
    result["risks"] = json.loads(result["risks"]) if result["risks"] else None
    return result


def count_designs_this_month(user_email: str) -> int:
    """Counts designs created in the current calendar month for a user,
    used for tier-quota enforcement. If an admin has reset this user's
    quota this month (see reset_quota_for_user), only counts designs
    created AFTER that reset — not from the start of the month — so a
    reset genuinely gives a fresh count rather than a no-op.

    Normalizes user_email once, here, rather than trusting every
    caller to have already done so — a real, previously-latent
    inconsistency: get_quota_reset always normalized internally before
    its own lookup, but the construction_designs query in this same
    function used the raw, un-normalized parameter directly. Every
    existing caller already happened to pass an already-lowercased
    email (from the session layer, which normalizes at login), so this
    never actually misfired in production — but it was one careless
    future caller away from silently returning 0 for a real user with
    a differently-cased email."""
    user_email = user_email.strip().lower()
    now = datetime.now(timezone.utc)
    month_prefix = now.strftime("%Y-%m")

    reset = get_quota_reset(user_email)
    if reset and reset["reset_at"].startswith(month_prefix):
        with get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) as cnt FROM construction_designs WHERE user_email = %s AND created_at > %s",
                    (user_email, reset["reset_at"]),
                )
                row = cursor.fetchone()
        return row["cnt"] if row else 0

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) as cnt FROM construction_designs WHERE user_email = %s AND created_at LIKE %s",
                (user_email, f"{month_prefix}%"),
            )
            row = cursor.fetchone()
    return row["cnt"] if row else 0


def reset_quota_for_user(user_email: str, admin_note: Optional[str] = None) -> None:
    """Admin action: gives a user a fresh generate quota for the
    current month, without touching or deleting any row in
    construction_designs itself — see initialize_construction_store's
    own comment on why the history is deliberately preserved. Setting
    reset_at to right now means every design generated before this
    moment stops counting against this month's quota; the full history
    (used for anything else, e.g. real usage analytics) is untouched."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO quota_resets (user_email, reset_at, admin_note)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_email) DO UPDATE SET reset_at = EXCLUDED.reset_at, admin_note = EXCLUDED.admin_note
                """,
                (user_email.strip().lower(), now, admin_note),
            )
        connection.commit()


def get_quota_reset(user_email: str) -> Optional[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM quota_resets WHERE user_email = %s", (user_email.strip().lower(),))
            return cursor.fetchone()
