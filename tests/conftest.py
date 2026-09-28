import pytest


@pytest.fixture(scope="session", autouse=True)
def _reset_database():
    """Runs once before the whole test session. Ensures all tables exist,
    then truncates them so every test run starts from a clean slate —
    replaces the old per-run SQLite file isolation now that all stores
    share one persistent Postgres database (DATABASE_URL).

    Importing backend.api (below) already runs every real store's own
    initialize_*_store() at module level — see the block of
    initialize_*_store() calls right after the FastAPI app is created —
    so this fixture doesn't need its own separate, hand-maintained list
    of stores to initialize; it only needs the tables to exist before
    truncating them, which that same import already guarantees.

    The TRUNCATE list itself is read from information_schema rather than
    hardcoded, on purpose: a hardcoded list silently stops covering a
    table the moment a new store adds one (this is exactly how
    agent_clients/agent_client_properties, price_watches,
    one_time_tier_grants, refunds/refund_requests, deleted_accounts,
    neighborhood_comparisons, processed_webhook_events,
    property_challenges, and user_profiles ended up NOT being cleared
    between test-session runs — 9 real tables' worth of state quietly
    leaking across runs on a shared persistent Postgres DB, causing
    order-dependent failures like a client-limit test seeing leftover
    clients from a previous run). Querying the schema for "every real
    table" instead means a future store's table is covered automatically,
    with nothing to remember to add here."""

    import backend.api  # noqa: F401 -- import alone runs every store's initialize_*_store()
    from backend.db import get_connection
    from backend.config_store import initialize_config_store

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )
            all_tables = [row["tablename"] for row in cursor.fetchall()]
            if all_tables:
                cursor.execute(f"TRUNCATE {', '.join(all_tables)} RESTART IDENTITY CASCADE")
        connection.commit()

    # app_config was wiped along with everything else — reseed the default
    # tier config so tests that read it (e.g. GET /api/tiers) see real data.
    initialize_config_store()

    yield


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Runs before EVERY test (function-scoped, unlike the database
    reset above) — the rate limiter's in-memory attempt history is
    process-wide state that would otherwise accumulate across tests
    regardless of which database they use, since it doesn't live in
    Postgres at all. Without this, tests that deliberately trigger
    auth failures (wrong admin password, wrong OTP code) could start
    tripping the real rate limit and failing with 429 instead of the
    403/401 they're actually testing for — a real, order-dependent
    flakiness risk this closes rather than working around per-test."""
    from backend.rate_limiter import _attempts
    _attempts.clear()
    yield
