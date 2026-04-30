"""Pydantic request/response schemas for leaderboard endpoints."""

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class LeaderboardEntry(BaseModel):
    """A single entry in the leaderboard."""

    rank: int = Field(..., ge=1)
    username: str
    value: Decimal


class LeaderboardResponse(BaseModel):
    """Response schema for leaderboard queries."""

    metric: str = Field(..., description="Ranking metric: total_winnings, win_rate, or win_streak")
    period: str = Field(..., description="Time period: daily, weekly, monthly, or all_time")
    entries: list[LeaderboardEntry] = []
    page: int = 1
    page_size: int = 100
    total: int = 0


class PlayerRankResponse(BaseModel):
    """Response schema for a player's own rank."""

    metric: str
    period: str
    rank: Optional[int] = None
    value: Optional[Decimal] = None
    username: str
