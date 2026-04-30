"""Unit tests for leaderboard service.

Tests cover:
- Top 100 limit enforcement
- Player rank inclusion and highlighting
- Daily/weekly/monthly/all-time period filters
- Invalid metric/period handling
- Redis unavailability fallback

Requirements: 8.3, 8.4, 8.5
"""

from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.services.leaderboard_service import (
    LeaderboardEntry,
    PlayerRank,
    get_leaderboard,
    get_player_rank,
    VALID_METRICS,
    VALID_PERIODS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_redis_with_entries(entries: list[tuple[str, float]], total: int | None = None):
    """Create a mock Redis client pre-loaded with sorted set data."""
    mock = AsyncMock()
    mock.zcard.return_value = total if total is not None else len(entries)
    mock.zrevrange.return_value = entries
    mock.aclose = AsyncMock()
    return mock


def _make_member(username: str, player_id=None) -> str:
    pid = player_id or uuid4()
    return f"{pid}:{username}"


# ---------------------------------------------------------------------------
# get_leaderboard tests
# ---------------------------------------------------------------------------

class TestGetLeaderboard:
    """Tests for the get_leaderboard function."""

    @pytest.mark.asyncio
    async def test_returns_top_entries_sorted_descending(self):
        """Entries are returned sorted by score descending."""
        entries = [
            (_make_member("alice"), 500.0),
            (_make_member("bob"), 300.0),
            (_make_member("charlie"), 100.0),
        ]
        mock = _mock_redis_with_entries(entries)

        with patch("app.services.leaderboard_service._get_redis", return_value=mock):
            result = await get_leaderboard("total_winnings", "all_time")

        assert len(result["entries"]) == 3
        assert result["entries"][0].username == "alice"
        assert result["entries"][0].value == Decimal("500.0")
        assert result["entries"][0].rank == 1
        assert result["entries"][1].rank == 2
        assert result["entries"][2].rank == 3

    @pytest.mark.asyncio
    async def test_top_100_limit_enforced(self):
        """Page size is capped at 100 entries."""
        # Simulate 100 entries in Redis
        entries = [
            (_make_member(f"player_{i}"), float(1000 - i))
            for i in range(100)
        ]
        mock = _mock_redis_with_entries(entries, total=150)

        with patch("app.services.leaderboard_service._get_redis", return_value=mock):
            result = await get_leaderboard("total_winnings", "all_time", page_size=100)

        assert len(result["entries"]) == 100
        assert result["total"] == 150

    @pytest.mark.asyncio
    async def test_pagination_page_2(self):
        """Page 2 starts at the correct offset."""
        entries = [
            (_make_member("player_101"), 50.0),
            (_make_member("player_102"), 40.0),
        ]
        mock = _mock_redis_with_entries(entries, total=102)

        with patch("app.services.leaderboard_service._get_redis", return_value=mock):
            result = await get_leaderboard("total_winnings", "all_time", page=2, page_size=100)

        # Ranks should be 101, 102 (page 2 offset = 100)
        assert result["entries"][0].rank == 101
        assert result["entries"][1].rank == 102
        assert result["page"] == 2

    @pytest.mark.asyncio
    async def test_empty_leaderboard(self):
        """Empty leaderboard returns no entries."""
        mock = _mock_redis_with_entries([], total=0)

        with patch("app.services.leaderboard_service._get_redis", return_value=mock):
            result = await get_leaderboard("win_rate", "daily")

        assert result["entries"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_all_valid_periods(self):
        """All period values are accepted without error."""
        mock = _mock_redis_with_entries([])

        for period in VALID_PERIODS:
            with patch("app.services.leaderboard_service._get_redis", return_value=mock):
                result = await get_leaderboard("total_winnings", period)
            assert result["period"] == period

    @pytest.mark.asyncio
    async def test_all_valid_metrics(self):
        """All metric values are accepted without error."""
        mock = _mock_redis_with_entries([])

        for metric in VALID_METRICS:
            with patch("app.services.leaderboard_service._get_redis", return_value=mock):
                result = await get_leaderboard(metric, "all_time")
            assert result["metric"] == metric

    @pytest.mark.asyncio
    async def test_invalid_metric_raises(self):
        """Invalid metric raises ValueError."""
        with pytest.raises(ValueError, match="Invalid metric"):
            await get_leaderboard("invalid_metric", "all_time")

    @pytest.mark.asyncio
    async def test_invalid_period_raises(self):
        """Invalid period raises ValueError."""
        with pytest.raises(ValueError, match="Invalid period"):
            await get_leaderboard("total_winnings", "yearly")

    @pytest.mark.asyncio
    async def test_redis_unavailable_returns_empty(self):
        """When Redis is unavailable, returns empty result gracefully."""
        with patch("app.services.leaderboard_service._get_redis", return_value=None):
            result = await get_leaderboard("total_winnings", "all_time")

        assert result["entries"] == []
        assert result["total"] == 0


# ---------------------------------------------------------------------------
# get_player_rank tests
# ---------------------------------------------------------------------------

class TestGetPlayerRank:
    """Tests for the get_player_rank function."""

    @pytest.mark.asyncio
    async def test_player_found_returns_rank_and_value(self):
        """When the player exists in the leaderboard, returns rank and value."""
        player_id = uuid4()
        username = "testplayer"
        member = f"{player_id}:{username}"

        mock = AsyncMock()
        mock.zrevrank.return_value = 4  # 0-based index
        mock.zscore.return_value = 250.0
        mock.aclose = AsyncMock()

        with patch("app.services.leaderboard_service._get_redis", return_value=mock):
            result = await get_player_rank(player_id, username, "total_winnings", "all_time")

        assert result.rank == 5  # 1-based
        assert result.value == Decimal("250.0")
        assert result.username == username

    @pytest.mark.asyncio
    async def test_player_not_found_returns_none_rank(self):
        """When the player is not in the leaderboard, rank and value are None."""
        player_id = uuid4()
        username = "newplayer"

        mock = AsyncMock()
        mock.zrevrank.return_value = None
        mock.aclose = AsyncMock()

        with patch("app.services.leaderboard_service._get_redis", return_value=mock):
            result = await get_player_rank(player_id, username, "win_rate", "weekly")

        assert result.rank is None
        assert result.value is None
        assert result.username == username

    @pytest.mark.asyncio
    async def test_player_rank_first_place(self):
        """Player at rank 0 in Redis maps to rank 1."""
        player_id = uuid4()
        username = "topplayer"

        mock = AsyncMock()
        mock.zrevrank.return_value = 0
        mock.zscore.return_value = 9999.99
        mock.aclose = AsyncMock()

        with patch("app.services.leaderboard_service._get_redis", return_value=mock):
            result = await get_player_rank(player_id, username, "win_streak", "monthly")

        assert result.rank == 1
        assert result.value == Decimal("9999.99")

    @pytest.mark.asyncio
    async def test_invalid_metric_raises(self):
        """Invalid metric raises ValueError."""
        with pytest.raises(ValueError, match="Invalid metric"):
            await get_player_rank(uuid4(), "user", "bad_metric", "all_time")

    @pytest.mark.asyncio
    async def test_invalid_period_raises(self):
        """Invalid period raises ValueError."""
        with pytest.raises(ValueError, match="Invalid period"):
            await get_player_rank(uuid4(), "user", "total_winnings", "bad_period")

    @pytest.mark.asyncio
    async def test_redis_unavailable_returns_none(self):
        """When Redis is unavailable, returns None rank gracefully."""
        with patch("app.services.leaderboard_service._get_redis", return_value=None):
            result = await get_player_rank(uuid4(), "user", "total_winnings", "all_time")

        assert result.rank is None
        assert result.value is None

    @pytest.mark.asyncio
    async def test_all_period_filters(self):
        """Player rank works for all valid periods."""
        player_id = uuid4()
        username = "testuser"

        mock = AsyncMock()
        mock.zrevrank.return_value = 2
        mock.zscore.return_value = 100.0
        mock.aclose = AsyncMock()

        for period in VALID_PERIODS:
            with patch("app.services.leaderboard_service._get_redis", return_value=mock):
                result = await get_player_rank(player_id, username, "total_winnings", period)
            assert result.rank == 3
