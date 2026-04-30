"""Responsible gambling models: DepositLimit, SelfExclusion, SessionLimit."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import uuid4, UUID

from sqlalchemy import (
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class LimitPeriod(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class DepositLimit(Base):
    __tablename__ = "deposit_limits"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    player_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"), nullable=False, index=True)
    period: Mapped[LimitPeriod] = mapped_column(nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    current_usage: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"))
    resets_at: Mapped[datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("player_id", "period", name="uq_player_deposit_limit_period"),
    )


class SelfExclusion(Base):
    __tablename__ = "self_exclusions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    player_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"), nullable=False, index=True)
    duration: Mapped[str] = mapped_column(String(20), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(default=func.now())
    ends_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())


class SessionLimit(Base):
    __tablename__ = "session_limits"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    player_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"), nullable=False, index=True)
    duration_minutes: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
