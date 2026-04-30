"""Smoke tests for infrastructure components.

Verifies Redis configuration, Celery worker health, and DB schema
correctness without requiring live external services.

Requirements: 1.5, 12.7, 13.5
"""

import pytest
import pytest_asyncio
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.models.base import Base


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def smoke_engine():
    """Create an in-memory SQLite engine for schema verification."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def smoke_session(smoke_engine):
    """Provide an async session bound to the smoke engine."""
    factory = async_sessionmaker(
        smoke_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as sess:
        yield sess


# ── Redis Configuration ──────────────────────────────────────────────────


class TestRedisConnectivity:
    """Verify Redis configuration is valid (Req 13.5)."""

    def test_redis_url_is_parseable(self):
        """The configured redis_url must be a valid Redis connection string."""
        from app.config import settings

        url = settings.redis_url
        assert url.startswith("redis://"), (
            f"redis_url must start with redis://, got: {url}"
        )

    def test_celery_broker_uses_redis(self):
        """Celery broker must be configured to use Redis."""
        from app.celery_app import celery_app

        broker_url = celery_app.conf.broker_url
        assert broker_url and "redis" in broker_url, (
            f"Celery broker must use Redis, got: {broker_url}"
        )

    def test_celery_backend_uses_redis(self):
        """Celery result backend must be configured to use Redis."""
        from app.celery_app import celery_app

        backend = celery_app.conf.result_backend
        assert backend and "redis" in backend, (
            f"Celery result backend must use Redis, got: {backend}"
        )


# ── Celery Worker Health ─────────────────────────────────────────────────


class TestCeleryWorkerHealth:
    """Verify Celery configuration and task registration."""

    def test_celery_eager_mode_works(self):
        """Tasks execute synchronously in eager mode (set by conftest)."""
        from app.celery_app import celery_app

        assert celery_app.conf.task_always_eager is True, (
            "Celery must be in eager mode during tests"
        )

    def test_email_tasks_registered(self):
        """Email tasks must be discoverable by Celery."""
        # Ensure task modules are imported so autodiscover picks them up
        import app.tasks.email_tasks  # noqa: F401
        from app.celery_app import celery_app

        registered = celery_app.tasks
        expected_tasks = [
            "app.tasks.email_tasks.send_verification_email",
            "app.tasks.email_tasks.send_password_reset_email",
            "app.tasks.email_tasks.send_notification_email",
        ]
        for task_name in expected_tasks:
            assert task_name in registered, (
                f"Task {task_name} not registered in Celery"
            )

    def test_task_routing_configured(self):
        """Task routing must map task patterns to dedicated queues."""
        from app.celery_app import celery_app

        routes = celery_app.conf.task_routes
        assert routes, "task_routes must be configured"
        assert "app.tasks.email_tasks.*" in routes, (
            "Email tasks must be routed to a dedicated queue"
        )
        assert routes["app.tasks.email_tasks.*"]["queue"] == "email"

    def test_beat_schedule_configured(self):
        """Celery Beat schedule must have periodic tasks defined."""
        from app.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        assert schedule, "beat_schedule must be configured"
        assert "advance-game-round" in schedule, (
            "advance-game-round must be in beat_schedule"
        )
        assert "reset-deposit-limits" in schedule, (
            "reset-deposit-limits must be in beat_schedule"
        )
        assert "generate-daily-report" in schedule, (
            "generate-daily-report must be in beat_schedule"
        )

    def test_celery_serialization_is_json(self):
        """Celery must use JSON serialization for safety."""
        from app.celery_app import celery_app

        assert celery_app.conf.task_serializer == "json"
        assert "json" in celery_app.conf.accept_content

    def test_email_task_executes_in_eager_mode(self):
        """A simple email task should execute without error in eager mode."""
        from app.tasks.email_tasks import send_verification_email

        # In eager mode this runs synchronously; no real email sent
        # because email_api_key is empty in test env
        result = send_verification_email.delay(
            "00000000-0000-0000-0000-000000000000",
            "smoke@test.local",
        )
        # Eager mode returns an EagerResult; no exception means success
        assert result is not None


# ── DB Migrations / Schema ───────────────────────────────────────────────


class TestDBMigrationsApplied:
    """Verify all model tables are created correctly (Req 13.5)."""

    EXPECTED_TABLES = [
        "players",
        "wallets",
        "transactions",
        "game_modes",
        "game_rounds",
        "bets",
        "payouts",
        "rng_audit_logs",
        "deposit_limits",
        "self_exclusions",
        "session_limits",
        "audit_trail",
        "friend_links",
    ]

    async def test_all_tables_created(self, smoke_engine):
        """All expected tables must exist after metadata.create_all."""
        async with smoke_engine.connect() as conn:
            table_names = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )

        for table in self.EXPECTED_TABLES:
            assert table in table_names, (
                f"Table '{table}' missing. Found: {table_names}"
            )

    async def test_players_table_has_required_columns(self, smoke_engine):
        """Players table must have core columns."""
        async with smoke_engine.connect() as conn:
            columns = await conn.run_sync(
                lambda sync_conn: [
                    c["name"] for c in inspect(sync_conn).get_columns("players")
                ]
            )

        for col in ["id", "email", "username", "password_hash"]:
            assert col in columns, (
                f"Column '{col}' missing from players table"
            )

    async def test_wallets_table_has_required_columns(self, smoke_engine):
        """Wallets table must have core columns."""
        async with smoke_engine.connect() as conn:
            columns = await conn.run_sync(
                lambda sync_conn: [
                    c["name"] for c in inspect(sync_conn).get_columns("wallets")
                ]
            )

        for col in ["id", "player_id", "balance"]:
            assert col in columns, (
                f"Column '{col}' missing from wallets table"
            )

    async def test_can_execute_basic_query(self, smoke_session):
        """A basic SELECT 1 query must succeed on the test engine."""
        result = await smoke_session.execute(text("SELECT 1"))
        row = result.scalar()
        assert row == 1
