"""Property-based tests for leaderboard service.

Property 18: Leaderboard sorting correctness — For any metric, leaderboard
returns players sorted descending; entry[i].value >= entry[i+1].value.

Validates: Requirements 8.1
"""

from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from app.services.leaderboard_service import (
    LeaderboardEntry,
    VALID_METRICS,
    VALID_PERIODS,
    get_leaderboard,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

st_username = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="_"),
    min_size=3,
    max_size=20,
).filter(lambda s: len(s) >= 3)

st_score = st.decimals(
    min_value=Decimal("0.00"),
    max_value=Decimal("999999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

st_metric = st.sampled_from(list(VALID_METRICS))
st_period = st.sampled_from(list(VALID_PERIODS))


def _make_redis_entries(players: list[tuple[str, Decimal]]) -> list[tuple[str, float]]:
    """Build mock Redis ZREVRANGE return data from (username, score) pairs.

    Entries are pre-sorted descending by score to simulate Redis behaviour.
    """
    sorted_players = sorted(players, key=lambda x: x[1], reverse=True)
    return [(f"{uuid4()}:{uname}", float(score)) for uname, score in sorted_players]


# ---------------------------------------------------------------------------
# Property 18: Leaderboard sorting correctness
# ---------------------------------------------------------------------------


class TestProperty18LeaderboardSortingCorrectness:
    """**Validates: Requirements 8.1**"""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        data=st.data(),
        metric=st_metric,
        period=st_period,
    )
    @pytest.mark.asyncio
    async def test_entries_sorted_descending(self, data, metric, period):
        """For any set of player scores, the leaderboard returns entries
        sorted in descending order by value."""
        num_players = data.draw(st.integers(min_value=0, max_value=50))
        players = [
            (data.draw(st_username), data.draw(st_score))
            for _ in range(num_players)
        ]

        redis_data = _make_redis_entries(players)

        mock_client = AsyncMock()
        mock_client.zcard.return_value = len(redis_data)
        mock_client.zrevrange.return_value = redis_data
        mock_client.aclose = AsyncMock()

        with patch(
            "app.services.leaderboard_service._get_redis",
            return_value=mock_client,
        ):
            result = await get_leaderboard(metric=metric, period=period)

        entries = result["entries"]

        # Verify descending order
        for i in range(len(entries) - 1):
            assert entries[i].value >= entries[i + 1].value, (
                f"Entry at rank {entries[i].rank} (value={entries[i].value}) "
                f"should be >= entry at rank {entries[i+1].rank} (value={entries[i+1].value})"
            )

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(
        data=st.data(),
        metric=st_metric,
        period=st_period,
    )
    @pytest.mark.asyncio
    async def test_ranks_are_sequential(self, data, metric, period):
        """Ranks are sequential starting from 1."""
        num_players = data.draw(st.integers(min_value=1, max_value=50))
        players = [
            (data.draw(st_username), data.draw(st_score))
            for _ in range(num_players)
        ]

        redis_data = _make_redis_entries(players)

        mock_client = AsyncMock()
        mock_client.zcard.return_value = len(redis_data)
        mock_client.zrevrange.return_value = redis_data
        mock_client.aclose = AsyncMock()

        with patch(
            "app.services.leaderboard_service._get_redis",
            return_value=mock_client,
        ):
            result = await get_leaderboard(metric=metric, period=period)

        entries = result["entries"]
        for i, entry in enumerate(entries):
            assert entry.rank == i + 1

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(metric=st_metric, period=st_period)
    @pytest.mark.asyncio
    async def test_empty_leaderboard_returns_empty(self, metric, period):
        """An empty leaderboard returns no entries."""
        mock_client = AsyncMock()
        mock_client.zcard.return_value = 0
        mock_client.zrevrange.return_value = []
        mock_client.aclose = AsyncMock()

        with patch(
            "app.services.leaderboard_service._get_redis",
            return_value=mock_client,
        ):
            result = await get_leaderboard(metric=metric, period=period)

        assert result["entries"] == []
        assert result["total"] == 0
