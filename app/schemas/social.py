"""Pydantic request/response schemas for social endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class FriendRequest(BaseModel):
    """Request body for adding a friend by username."""

    username: str = Field(..., min_length=3, max_length=50)


class InviteCodeResponse(BaseModel):
    """Response schema for a generated invite code."""

    invite_code: str
    round_id: UUID


class ProfileResponse(BaseModel):
    """Response schema for a player's public profile."""

    username: str
    total_games_played: int = 0
    win_rate: Decimal = Decimal("0.00")
    leaderboard_rank: Optional[int] = None
    member_since: datetime
