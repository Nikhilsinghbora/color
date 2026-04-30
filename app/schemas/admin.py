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
