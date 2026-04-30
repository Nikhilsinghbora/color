"""Pydantic request/response schemas for responsible gambling endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class DepositLimitRequest(BaseModel):
    """Request body for setting a deposit limit."""

    period: str = Field(..., description="Limit period: daily, weekly, or monthly")
    amount: Decimal = Field(..., gt=0, le=Decimal("999999.99"), decimal_places=2)

    @field_validator("period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        allowed = {"daily", "weekly", "monthly"}
        if v not in allowed:
            raise ValueError(f"Period must be one of: {', '.join(sorted(allowed))}")
        return v


class DepositLimitResponse(BaseModel):
    """Response schema for a deposit limit."""

    period: str
    amount: Decimal
    current_usage: Decimal
    remaining: Decimal
    resets_at: datetime

    model_config = {"from_attributes": True}


class SessionLimitRequest(BaseModel):
    """Request body for setting a session time limit."""

    duration_minutes: int = Field(..., gt=0, le=1440, description="Session limit in minutes (max 24h)")


class SelfExclusionRequest(BaseModel):
    """Request body for self-exclusion."""

    duration: str = Field(..., description="Exclusion duration: 24h, 7d, 30d, or permanent")

    @field_validator("duration")
    @classmethod
    def validate_duration(cls, v: str) -> str:
        allowed = {"24h", "7d", "30d", "permanent"}
        if v not in allowed:
            raise ValueError(f"Duration must be one of: {', '.join(sorted(allowed))}")
        return v
