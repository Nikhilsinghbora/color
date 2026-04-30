"""Pydantic request/response schemas for admin endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class DashboardResponse(BaseModel):
    """Response schema for the admin dashboard."""

    active_players: int = 0
    total_bets: Decimal = Decimal("0.00")
    total_payouts: Decimal = Decimal("0.00")
    platform_revenue: Decimal = Decimal("0.00")
    period_start: datetime
    period_end: datetime


class GameConfigUpdateRequest(BaseModel):
    """Request body for updating game mode configuration."""

    color_options: Optional[list[str]] = Field(None, min_length=2, max_length=20)
    odds: Optional[dict[str, float]] = None
    min_bet: Optional[Decimal] = Field(None, gt=0, le=Decimal("999999.99"))
    max_bet: Optional[Decimal] = Field(None, gt=0, le=Decimal("999999.99"))
    round_duration_seconds: Optional[int] = Field(None, gt=0, le=3600)
    is_active: Optional[bool] = None

    @field_validator("color_options")
    @classmethod
    def validate_color_options(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is not None:
            for color in v:
                if not color or len(color) > 20:
                    raise ValueError("Each color option must be 1-20 characters")
            if len(v) != len(set(v)):
                raise ValueError("Color options must be unique")
        return v


class PlayerActionRequest(BaseModel):
    """Request body for admin actions on a player (suspend/ban)."""

    action: str = Field(..., description="Action to take: suspend or ban")
    reason: str = Field(..., min_length=1, max_length=500)

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed = {"suspend", "ban"}
        if v not in allowed:
            raise ValueError(f"Action must be one of: {', '.join(sorted(allowed))}")
        return v


class ProfitSettingsRequest(BaseModel):
    """Request body for updating profit settings."""

    house_profit_percentage: Decimal = Field(
        ...,
        ge=Decimal("0.00"),
        le=Decimal("100.00"),
        description="House profit percentage (0-100)"
    )
    winners_pool_percentage: Decimal = Field(
        ...,
        ge=Decimal("0.00"),
        le=Decimal("100.00"),
        description="Winners pool percentage (0-100)"
    )

    @field_validator("winners_pool_percentage")
    @classmethod
    def validate_total_percentage(cls, v: Decimal, info) -> Decimal:
        if "house_profit_percentage" in info.data:
            house = info.data["house_profit_percentage"]
            if house + v != Decimal("100.00"):
                raise ValueError("house_profit_percentage + winners_pool_percentage must equal 100")
        return v


class ProfitSettingsResponse(BaseModel):
    """Response schema for profit settings."""

    id: UUID
    house_profit_percentage: Decimal
    winners_pool_percentage: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RoundProfitDetailsResponse(BaseModel):
    """Response schema for round profit details."""

    round_id: UUID
    total_bets: Decimal
    total_payout_pool: Optional[Decimal]
    house_profit: Optional[Decimal]
    total_calculated_payouts: Optional[Decimal]
    total_actual_payouts: Decimal
    payout_reduced: bool
    applied_house_percentage: Optional[Decimal]
    applied_winners_percentage: Optional[Decimal]
    flagged_for_review: bool

    model_config = {"from_attributes": True}


class ProfitGraphPoint(BaseModel):
    """A single data point for the profit/margin graph."""

    date: str                       # ISO date or datetime string
    total_bets: Decimal
    total_payouts: Decimal
    house_profit: Decimal
    profit_margin_pct: Decimal      # (house_profit / total_bets) * 100
    rounds_played: int


class ProfitGraphResponse(BaseModel):
    """Response schema for the profit & margin graph data."""

    points: list[ProfitGraphPoint]
    period: str                     # "daily" | "weekly" | "monthly"
    target_margin_pct: Decimal      # current admin-configured house %
    summary_total_bets: Decimal
    summary_total_payouts: Decimal
    summary_total_profit: Decimal
    summary_avg_margin_pct: Decimal
