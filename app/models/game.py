"""Game-related models: GameMode, GameRound, Bet, Payout."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import uuid4, UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RoundPhase(str, Enum):
    BETTING = "betting"
    RESOLUTION = "resolution"
    RESULT = "result"


class GameMode(Base):
    __tablename__ = "game_modes"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    mode_type: Mapped[str] = mapped_column(String(20), nullable=False)
    color_options: Mapped[list] = mapped_column(JSON, nullable=False)
    odds: Mapped[dict] = mapped_column(JSON, nullable=False)
    min_bet: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    max_bet: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    round_duration_seconds: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    mode_prefix: Mapped[str] = mapped_column(String(3), nullable=False, default="100")
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())


class GameRound(Base):
    __tablename__ = "game_rounds"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    game_mode_id: Mapped[UUID] = mapped_column(ForeignKey("game_modes.id"), nullable=False, index=True)
    phase: Mapped[RoundPhase] = mapped_column(nullable=False, default=RoundPhase.BETTING)
    winning_color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    winning_number: Mapped[Optional[int]] = mapped_column(nullable=True)
    total_bets: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    total_payouts: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
    flagged_for_review: Mapped[bool] = mapped_column(default=False)
    invite_code: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True, index=True)
    created_by: Mapped[Optional[UUID]] = mapped_column(ForeignKey("players.id"), nullable=True)
    betting_ends_at: Mapped[datetime] = mapped_column(nullable=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    period_number: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    # Profit management fields
    total_payout_pool: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    house_profit: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    total_calculated_payouts: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    payout_reduced: Mapped[bool] = mapped_column(default=False)
    applied_house_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    applied_winners_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)


class Bet(Base):
    __tablename__ = "bets"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    player_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"), nullable=False, index=True)
    round_id: Mapped[UUID] = mapped_column(ForeignKey("game_rounds.id"), nullable=False, index=True)
    color: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    odds_at_placement: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    is_winner: Mapped[Optional[bool]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    __table_args__ = (
        CheckConstraint("amount > 0", name="bet_positive_amount"),
    )


class Payout(Base):
    __tablename__ = "payouts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    bet_id: Mapped[UUID] = mapped_column(ForeignKey("bets.id"), unique=True, nullable=False)
    player_id: Mapped[UUID] = mapped_column(ForeignKey("players.id"), nullable=False, index=True)
    round_id: Mapped[UUID] = mapped_column(ForeignKey("game_rounds.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    credited: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())


class ProfitSettings(Base):
    __tablename__ = "profit_settings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    house_profit_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    winners_pool_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("house_profit_percentage >= 0 AND house_profit_percentage <= 100", name="valid_house_percentage"),
        CheckConstraint("winners_pool_percentage >= 0 AND winners_pool_percentage <= 100", name="valid_winners_percentage"),
        CheckConstraint("house_profit_percentage + winners_pool_percentage = 100", name="total_percentage_is_100"),
    )


class PeriodSequence(Base):
    __tablename__ = "period_sequences"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    game_mode_id: Mapped[UUID] = mapped_column(ForeignKey("game_modes.id"), nullable=False)
    date_str: Mapped[str] = mapped_column(String(8), nullable=False)
    last_sequence: Mapped[int] = mapped_column(default=0)

    __table_args__ = (UniqueConstraint("game_mode_id", "date_str"),)
