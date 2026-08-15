import pytest


@pytest.fixture(scope="session", autouse=True)
def _reset_database():
    """Runs once before the whole test session. Ensures all tables exist,
    then truncates them so every test run starts from a clean slate —
    replaces the old per-run SQLite file isolation now that all stores
    share one persistent Postgres database (DATABASE_URL)."""

    from backend.db import get_connection
    from backend.auth_store import initialize_auth_store
    from backend.config_store import initialize_config_store
    from backend.subscription_store import initialize_subscription_store
    from backend.insight_store import initialize_insight_store
    from backend.construction_store import initialize_construction_store
    from backend.payment_store import initialize_payment_store

    initialize_auth_store()
    initialize_config_store()
    initialize_subscription_store()
    initialize_insight_store()
    initialize_construction_store()
    initialize_payment_store()

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                TRUNCATE
                    users, otp_codes, sessions,
                    app_config,
                    subscriptions,
                    insight_grants,
                    construction_designs,
                    report_orders
                RESTART IDENTITY CASCADE
                """
            )
        connection.commit()

    # app_config was wiped along with everything else — reseed the default
    # tier config so tests that read it (e.g. GET /api/tiers) see real data.
    initialize_config_store()

    yield
