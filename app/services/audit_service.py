"""Audit trail service for recording all auditable events.

Provides append-only audit logging in PostgreSQL. No update or delete
functions are exposed — the audit trail is immutable by design.

Requirements: 12.5
"""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEventType, AuditTrail

logger = logging.getLogger(__name__)


async def create_audit_entry(
    session: AsyncSession,
    event_type: AuditEventType,
    actor_id: UUID,
    target_id: UUID | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> AuditTrail:
    """Create and flush an immutable audit trail entry.

    This is the single entry point for all audit logging across the platform.
    """
    entry = AuditTrail(
        event_type=event_type,
        actor_id=actor_id,
        target_id=target_id,
        details=details or {},
        ip_address=ip_address,
    )
    session.add(entry)
    await session.flush()
    return entry


async def get_audit_entries(
    session: AsyncSession,
    event_type: AuditEventType | None = None,
    actor_id: UUID | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Return paginated audit trail entries, most recent first.

    Supports optional filtering by event_type and/or actor_id.

    Returns a dict with keys: entries, page, page_size, total.
    """
    # Build base query
    query = select(AuditTrail).order_by(AuditTrail.created_at.desc())
    count_q = select(func.count(AuditTrail.id))

    if event_type is not None:
        query = query.where(AuditTrail.event_type == event_type)
        count_q = count_q.where(AuditTrail.event_type == event_type)

    if actor_id is not None:
        query = query.where(AuditTrail.actor_id == actor_id)
        count_q = count_q.where(AuditTrail.actor_id == actor_id)

    # Total count
    total_result = await session.execute(count_q)
    total = total_result.scalar_one()

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    result = await session.execute(query)
    entries = list(result.scalars().all())

    return {
        "entries": entries,
        "page": page,
        "page_size": page_size,
        "total": total,
    }
