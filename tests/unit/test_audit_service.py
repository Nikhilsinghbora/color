"""Unit tests for audit trail service.

Tests create_audit_entry, get_audit_entries, and append-only guarantees.
Requirements: 12.5
"""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEventType, AuditTrail
from app.models.player import Player
from app.services import audit_service


@pytest_asyncio.fixture
async def actor(session: AsyncSession) -> Player:
    """Create a player to act as the audit actor."""
    p = Player(
        id=uuid4(),
        email="actor@example.com",
        username="actor",
        password_hash="hashed",
    )
    session.add(p)
    await session.flush()
    return p


class TestCreateAuditEntry:
    """Test create_audit_entry produces correct, immutable records."""

    @pytest.mark.asyncio
    async def test_creates_entry_with_all_fields(self, session, actor):
        target = uuid4()
        entry = await audit_service.create_audit_entry(
            session,
            event_type=AuditEventType.AUTH_LOGIN,
            actor_id=actor.id,
            target_id=target,
            details={"method": "email_password"},
            ip_address="192.168.1.1",
        )

        assert entry.id is not None
        assert entry.event_type == AuditEventType.AUTH_LOGIN
        assert entry.actor_id == actor.id
        assert entry.target_id == target
        assert entry.details == {"method": "email_password"}
        assert entry.ip_address == "192.168.1.1"
        assert entry.created_at is not None

    @pytest.mark.asyncio
    async def test_creates_entry_with_minimal_fields(self, session, actor):
        entry = await audit_service.create_audit_entry(
            session,
            event_type=AuditEventType.AUTH_FAILED,
            actor_id=actor.id,
        )

        assert entry.id is not None
        assert entry.event_type == AuditEventType.AUTH_FAILED
        assert entry.actor_id == actor.id
        assert entry.target_id is None
        assert entry.details == {}
        assert entry.ip_address is None

    @pytest.mark.asyncio
    async def test_different_event_types(self, session, actor):
        """Each event type can be recorded."""
        for evt in [
            AuditEventType.WALLET_DEPOSIT,
            AuditEventType.WALLET_WITHDRAWAL,
            AuditEventType.ADMIN_CONFIG_CHANGE,
        ]:
            entry = await audit_service.create_audit_entry(
                session, event_type=evt, actor_id=actor.id,
            )
            assert entry.event_type == evt


class TestGetAuditEntries:
    """Test paginated retrieval and filtering of audit entries."""

    @pytest.mark.asyncio
    async def test_returns_paginated_results(self, session, actor):
        for _ in range(3):
            await audit_service.create_audit_entry(
                session, event_type=AuditEventType.AUTH_LOGIN, actor_id=actor.id,
            )

        result = await audit_service.get_audit_entries(session, page=1, page_size=2)

        assert result["total"] == 3
        assert result["page"] == 1
        assert result["page_size"] == 2
        assert len(result["entries"]) == 2

    @pytest.mark.asyncio
    async def test_page_two(self, session, actor):
        for _ in range(3):
            await audit_service.create_audit_entry(
                session, event_type=AuditEventType.AUTH_LOGIN, actor_id=actor.id,
            )

        result = await audit_service.get_audit_entries(session, page=2, page_size=2)

        assert result["total"] == 3
        assert len(result["entries"]) == 1

    @pytest.mark.asyncio
    async def test_filters_by_event_type(self, session, actor):
        await audit_service.create_audit_entry(
            session, event_type=AuditEventType.AUTH_LOGIN, actor_id=actor.id,
        )
        await audit_service.create_audit_entry(
            session, event_type=AuditEventType.WALLET_DEPOSIT, actor_id=actor.id,
        )

        result = await audit_service.get_audit_entries(
            session, event_type=AuditEventType.WALLET_DEPOSIT,
        )

        assert result["total"] == 1
        assert result["entries"][0].event_type == AuditEventType.WALLET_DEPOSIT

    @pytest.mark.asyncio
    async def test_filters_by_actor_id(self, session, actor):
        other = Player(
            id=uuid4(), email="other@example.com",
            username="other", password_hash="hashed",
        )
        session.add(other)
        await session.flush()

        await audit_service.create_audit_entry(
            session, event_type=AuditEventType.AUTH_LOGIN, actor_id=actor.id,
        )
        await audit_service.create_audit_entry(
            session, event_type=AuditEventType.AUTH_LOGIN, actor_id=other.id,
        )

        result = await audit_service.get_audit_entries(session, actor_id=actor.id)

        assert result["total"] == 1
        assert result["entries"][0].actor_id == actor.id

    @pytest.mark.asyncio
    async def test_empty_result(self, session):
        result = await audit_service.get_audit_entries(session)

        assert result["total"] == 0
        assert result["entries"] == []


class TestAppendOnlyGuarantee:
    """The audit service exposes no update or delete functions."""

    def test_no_update_function(self):
        assert not hasattr(audit_service, "update_audit_entry")

    def test_no_delete_function(self):
        assert not hasattr(audit_service, "delete_audit_entry")
