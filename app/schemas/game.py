"""Pydantic request/response schemas for game endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class PlaceBetRequest(BaseModel):
    """Request body for placing a bet."""
    color: str = Field(..., min_length=1, max_length=20)
    amount: Decimal = Field(..., gt=0, decimal_places=2)


class GameModeResponse(BaseModel):
    """Response schema for a game mode."""
    id: UUID
    name: str
    mode_type: str
    color_options: list[str]
    odds: dict[str, float]
    min_bet: Decimal
    max_bet: Decimal
    round_duration_seconds: int
    is_active: bool
    active_round_id: UUID | None = None
    mode_prefix: str = "100"

    model_config = {"from_attributes": True}


class RoundStateResponse(BaseModel):
    """Response schema for round state."""
    round_id: UUID
    game_mode_id: UUID
    phase: str
    winning_color: Optional[str] = None
    total_bets: Decimal
    total_payouts: Decimal
    betting_ends_at: datetime
    resolved_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class BetResponse(BaseModel):
    """Response schema for a placed bet."""
    id: UUID
    player_id: UUID
    round_id: UUID
    color: str
    amount: Decimal
    odds_at_placement: Decimal
    is_winner: Optional[bool] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ResultSummaryResponse(BaseModel):
    """Result summary shown after RESULT phase."""
    round_id: UUID
    winning_color: str
    player_prediction: str
    bet_amount: Decimal
    odds_at_placement: Decimal
    is_winner: bool
    payout: Decimal


class GameHistoryEntry(BaseModel):
    """A single completed round in the game history."""
    period_number: str | None
    winning_number: int | None
    winning_color: str | None
    big_small_label: str  # "Big" or "Small"
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class PaginatedGameHistory(BaseModel):
    """Paginated response for game history."""
    items: list[GameHistoryEntry]
    total: int
    page: int
    size: int
    has_more: bool


class MyHistoryEntry(BaseModel):
    """A single bet entry in the player's bet history."""
    period_number: str | None
    bet_type: str
    bet_amount: Decimal
    is_winner: bool | None
    payout_amount: Decimal
    created_at: datetime


class PaginatedMyHistory(BaseModel):
    """Paginated response for player bet history."""
    items: list[MyHistoryEntry]
    total: int
    page: int
    size: int
    has_more: bool
