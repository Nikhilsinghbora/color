"""Pydantic request/response schemas for game endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


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
