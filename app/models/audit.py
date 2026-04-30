"""Audit trail model."""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4, UUID

from sqlalchemy import ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditEventType(str, Enum):
    AUTH_LOGIN = "auth_login"
    AUTH_LOGOUT = "auth_logout"
    AUTH_FAILED = "auth_failed"
    WALLET_DEPOSIT = "wallet_deposit"
    WALLET_WITHDRAWAL = "wallet_withdrawal"
    ADMIN_CONFIG_CHANGE = "admin_config_change"
    ADMIN_PLAYER_ACTION = "admin_player_action"
    RESPONSIBLE_GAMBLING = "responsible_gambling"


class AuditTrail(Base):
    __tablename__ = "audit_trail"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event_type: Mapped[AuditEventType] = mapped_column(nullable=False, index=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"), nullable=False, index=True)
    target_id: Mapped[Optional[UUID]] = mapped_column(nullable=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now(), index=True)
