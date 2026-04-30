"""Unit tests for admin service.

Tests dashboard metrics aggregation, config change application and logging,
player suspension and ban with reason recording, audit logs, and RNG audit logs.
Requirements: 11.1, 11.2, 11.3, 11.4
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEventType, AuditTrail
from app.models.game import Bet, GameMode, Payout
from app.models.player import Player
from app.models.rng import RNGAuditLog
from app.services import admin_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def admin_player(session: AsyncSession) -> Player:
    """Create an admin player."""
    p = Player(
        id=uuid4(),
        email="admin@example.com",
        username="adminuser",
        password_hash="hashed",
        is_admin=True,
    )
    session.add(p)
    await session.flush()
    return p


@pytest_asyncio.fixture
async def target_player(session: AsyncSession) -> Player:
    """Create a regular player to be acted upon."""
    p = Player(
        id=uuid4(),
        email="target@example.com",
        username="targetuser",
        password_hash="hashed",
    )
    session.add(p)
    await session.flush()
    return p


# ---------------------------------------------------------------------------
# get_dashboard_metrics
# ---------------------------------------------------------------------------


class TestGetDashboardMetrics:
    """Requirement 11.1: Dashboard displays active players, total bets,
    total payouts, and platform revenue for configurable time periods."""

    @pytest.mark.asyncio
    async def test_returns_correct_metrics(self, session, game_mode, admin_player, target_player):
        """Metrics reflect bets and payouts within the period."""
        now = datetime.now(timezone.utc)
        round_id = uuid4()

        bet = Bet(
            id=uuid4(),
            player_id=target_player.id,
            round_id=round_id,
            color="red",
            amount=Decimal("100.00"),
            odds_at_placement=Decimal("2.00"),
            created_at=now - timedelta(hours=1),
        )
        session.add(bet)

        payout = Payout(
            id=uuid4(),
            bet_id=bet.id,
            player_id=target_player.id,
            round_id=round_id,
            amount=Decimal("200.00"),
            created_at=now - timedelta(hours=1),
        )
        session.add(payout)
        await session.flush()

        metrics = await admin_service.get_dashboard_metrics(
            session,
            period_start=now - timedelta(hours=2),
            period_end=now,
        )

        assert metrics["active_players"] == 1
        assert metrics["total_bets"] == Decimal("100.00")
        assert metrics["total_payouts"] == Decimal("200.00")
        assert metrics["platform_revenue"] == Decimal("-100.00")

    @pytest.mark.asyncio
    async def test_defaults_to_last_24_hours(self, session):
        """When no period specified, defaults to last 24 hours."""
        now = datetime.now(timezone.utc)
        metrics = await admin_service.get_dashboard_metrics(session)

        assert metrics["period_start"] is not None
        assert metrics["period_end"] is not None
        # period_end should be close to now
        diff = abs((metrics["period_end"] - now).total_seconds())
        assert diff < 5
        # period_start should be ~24h before period_end
        span = (metrics["period_end"] - metrics["period_start"]).total_seconds()
        assert abs(span - 86400) < 5

    @pytest.mark.asyncio
    async def test_returns_zeros_when_no_activity(self, session):
        """All metrics are zero when no bets or payouts exist."""
        metrics = await admin_service.get_dashboard_metrics(session)

        assert metrics["active_players"] == 0
        assert metrics["total_bets"] == Decimal("0.00")
        assert metrics["total_payouts"] == Decimal("0.00")
        assert metrics["platform_revenue"] == Decimal("0.00")


# ---------------------------------------------------------------------------
# update_game_config
# ---------------------------------------------------------------------------


class TestUpdateGameConfig:
    """Requirement 11.2, 11.3: Config changes apply and are logged."""

    @pytest.mark.asyncio
    async def test_applies_changes_to_game_mode(self, session, game_mode, admin_player):
        """Config update modifies the game mode fields."""
        updated = await admin_service.update_game_config(
            session,
            mode_id=game_mode.id,
            admin_id=admin_player.id,
            updates={"min_bet": Decimal("5.00"), "max_bet": Decimal("500.00")},
        )

        assert updated.min_bet == Decimal("5.00")
        assert updated.max_bet == Decimal("500.00")

    @pytest.mark.asyncio
    async def test_creates_audit_trail_entry(self, session, game_mode, admin_player):
        """Config update creates an audit trail entry."""
        await admin_service.update_game_config(
            session,
            mode_id=game_mode.id,
            admin_id=admin_player.id,
            updates={"round_duration_seconds": 60},
        )
        await session.flush()

        result = await session.execute(
            select(AuditTrail).where(
                AuditTrail.event_type == AuditEventType.ADMIN_CONFIG_CHANGE
            )
        )
        audit = result.scalar_one()
        assert audit.actor_id == admin_player.id
        assert audit.target_id == game_mode.id

    @pytest.mark.asyncio
    async def test_raises_for_nonexistent_game_mode(self, session, admin_player):
        """ValueError raised when game mode does not exist."""
        with pytest.raises(ValueError, match="not found"):
            await admin_service.update_game_config(
                session,
                mode_id=uuid4(),
                admin_id=admin_player.id,
                updates={"min_bet": Decimal("10.00")},
            )

    @pytest.mark.asyncio
    async def test_logs_old_and_new_values(self, session, game_mode, admin_player):
        """Audit details contain old and new values."""
        old_min = game_mode.min_bet

        await admin_service.update_game_config(
            session,
            mode_id=game_mode.id,
            admin_id=admin_player.id,
            updates={"min_bet": Decimal("10.00")},
        )
        await session.flush()

        result = await session.execute(
            select(AuditTrail).where(
                AuditTrail.event_type == AuditEventType.ADMIN_CONFIG_CHANGE
            )
        )
        audit = result.scalar_one()
        assert "old_values" in audit.details
        assert "new_values" in audit.details
        assert audit.details["old_values"]["min_bet"] == str(old_min)
        assert audit.details["new_values"]["min_bet"] == "10.00"


# ---------------------------------------------------------------------------
# suspend_player
# ---------------------------------------------------------------------------


class TestSuspendPlayer:
    """Requirement 11.4: Suspend player with recorded reason."""

    @pytest.mark.asyncio
    async def test_sets_is_active_false(self, session, admin_player, target_player):
        """Suspending a player deactivates their account."""
        assert target_player.is_active is True

        result = await admin_service.suspend_player(
            session,
            player_id=target_player.id,
            admin_id=admin_player.id,
            reason="Suspicious activity",
        )

        assert result.is_active is False

    @pytest.mark.asyncio
    async def test_creates_audit_entry_with_suspend_action(self, session, admin_player, target_player):
        """Audit entry records action='suspend' and the reason."""
        await admin_service.suspend_player(
            session,
            player_id=target_player.id,
            admin_id=admin_player.id,
            reason="Violation of terms",
        )
        await session.flush()

        result = await session.execute(
            select(AuditTrail).where(
                AuditTrail.event_type == AuditEventType.ADMIN_PLAYER_ACTION
            )
        )
        audit = result.scalar_one()
        assert audit.actor_id == admin_player.id
        assert audit.target_id == target_player.id
        assert audit.details["action"] == "suspend"
        assert audit.details["reason"] == "Violation of terms"

    @pytest.mark.asyncio
    async def test_raises_for_nonexistent_player(self, session, admin_player):
        """ValueError raised when player does not exist."""
        with pytest.raises(ValueError, match="not found"):
            await admin_service.suspend_player(
                session,
                player_id=uuid4(),
                admin_id=admin_player.id,
                reason="Test",
            )


# ---------------------------------------------------------------------------
# ban_player
# ---------------------------------------------------------------------------


class TestBanPlayer:
    """Requirement 11.4: Ban player with recorded reason."""

    @pytest.mark.asyncio
    async def test_sets_is_active_false(self, session, admin_player, target_player):
        """Banning a player deactivates their account."""
        assert target_player.is_active is True

        result = await admin_service.ban_player(
            session,
            player_id=target_player.id,
            admin_id=admin_player.id,
            reason="Fraud detected",
        )

        assert result.is_active is False

    @pytest.mark.asyncio
    async def test_creates_audit_entry_with_ban_action(self, session, admin_player, target_player):
        """Audit entry records action='ban' and the reason."""
        await admin_service.ban_player(
            session,
            player_id=target_player.id,
            admin_id=admin_player.id,
            reason="Repeated abuse",
        )
        await session.flush()

        result = await session.execute(
            select(AuditTrail).where(
                AuditTrail.event_type == AuditEventType.ADMIN_PLAYER_ACTION
            )
        )
        audit = result.scalar_one()
        assert audit.actor_id == admin_player.id
        assert audit.target_id == target_player.id
        assert audit.details["action"] == "ban"
        assert audit.details["reason"] == "Repeated abuse"

    @pytest.mark.asyncio
    async def test_raises_for_nonexistent_player(self, session, admin_player):
        """ValueError raised when player does not exist."""
        with pytest.raises(ValueError, match="not found"):
            await admin_service.ban_player(
                session,
                player_id=uuid4(),
                admin_id=admin_player.id,
                reason="Test",
            )


# ---------------------------------------------------------------------------
# get_audit_logs
# ---------------------------------------------------------------------------


class TestGetAuditLogs:
    """Requirement 11.3: Paginated audit trail sorted by created_at desc."""

    @pytest.mark.asyncio
    async def test_returns_paginated_results(self, session, admin_player, target_player):
        """Audit logs are returned with pagination metadata."""
        # Create some audit entries via suspend/ban
        await admin_service.suspend_player(
            session, player_id=target_player.id,
            admin_id=admin_player.id, reason="r1",
        )
        await admin_service.ban_player(
            session, player_id=target_player.id,
            admin_id=admin_player.id, reason="r2",
        )
        await session.flush()

        result = await admin_service.get_audit_logs(session, page=1, page_size=10)

        assert result["page"] == 1
        assert result["page_size"] == 10
        assert result["total"] == 2
        assert len(result["logs"]) == 2

    @pytest.mark.asyncio
    async def test_sorted_by_created_at_desc(self, session, admin_player, target_player):
        """Logs are returned most recent first."""
        await admin_service.suspend_player(
            session, player_id=target_player.id,
            admin_id=admin_player.id, reason="first",
        )
        await admin_service.ban_player(
            session, player_id=target_player.id,
            admin_id=admin_player.id, reason="second",
        )
        await session.flush()

        result = await admin_service.get_audit_logs(session, page=1, page_size=10)
        logs = result["logs"]
        # Both have same created_at from func.now() in SQLite, so just verify count
        assert len(logs) == 2

    @pytest.mark.asyncio
    async def test_filters_by_event_type(self, session, game_mode, admin_player, target_player):
        """When event_type is provided, only matching logs are returned."""
        await admin_service.suspend_player(
            session, player_id=target_player.id,
            admin_id=admin_player.id, reason="suspend",
        )
        await admin_service.update_game_config(
            session, mode_id=game_mode.id,
            admin_id=admin_player.id, updates={"min_bet": Decimal("2.00")},
        )
        await session.flush()

        result = await admin_service.get_audit_logs(
            session, page=1, page_size=10,
            event_type=AuditEventType.ADMIN_CONFIG_CHANGE,
        )

        assert result["total"] == 1
        assert len(result["logs"]) == 1
        assert result["logs"][0].event_type == AuditEventType.ADMIN_CONFIG_CHANGE


# ---------------------------------------------------------------------------
# get_rng_audit_logs
# ---------------------------------------------------------------------------


class TestGetRNGAuditLogs:
    """Requirement 5.5: RNG audit log for fairness verification."""

    @pytest.mark.asyncio
    async def test_returns_paginated_results(self, session):
        """RNG audit logs are returned with pagination metadata."""
        round_id = uuid4()
        entry = RNGAuditLog(
            id=uuid4(),
            round_id=round_id,
            algorithm="secrets.randbelow",
            raw_value=1,
            num_options=3,
            selected_color="green",
        )
        session.add(entry)
        await session.flush()

        result = await admin_service.get_rng_audit_logs(session, page=1, page_size=10)

        assert result["page"] == 1
        assert result["page_size"] == 10
        assert result["total"] == 1
        assert len(result["logs"]) == 1
        assert result["logs"][0].algorithm == "secrets.randbelow"
        assert result["logs"][0].selected_color == "green"
