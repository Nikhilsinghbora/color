"""Unit tests for social features.

Tests cover:
- Friend add by username
- Invite code generation and join flow
- Profile display with public statistics

Requirements: 9.1, 9.2, 9.4, 9.5
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.game import GameRound, RoundPhase
from app.models.player import Player
from app.models.social import FriendLink
from app.services import social_service
from app.services.social_service import (
    _generate_invite_code,
    _INVITE_CODE_ALPHABET,
    _INVITE_CODE_LENGTH,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_player(username="alice", player_id=None):
    """Create a mock Player object."""
    p = MagicMock(spec=Player)
    p.id = player_id or uuid4()
    p.username = username
    p.email = f"{username}@example.com"
    p.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return p


def _make_session():
    """Create a mock async session."""
    session = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.rollback = AsyncMock()
    return session


def _mock_execute_scalar(session, return_value):
    """Configure session.execute to return a scalar_one_or_none result."""
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = return_value
    result_mock.scalar_one.return_value = return_value
    result_mock.scalar.return_value = return_value
    session.execute = AsyncMock(return_value=result_mock)
    return session


# ---------------------------------------------------------------------------
# Invite code generation tests
# ---------------------------------------------------------------------------

class TestInviteCodeGeneration:
    """Tests for invite code generation."""

    def test_code_has_correct_length(self):
        code = _generate_invite_code()
        assert len(code) == _INVITE_CODE_LENGTH

    def test_code_uses_allowed_characters(self):
        code = _generate_invite_code()
        for ch in code:
            assert ch in _INVITE_CODE_ALPHABET

    def test_multiple_codes_are_unique(self):
        codes = {_generate_invite_code() for _ in range(100)}
        assert len(codes) == 100

    def test_code_is_string(self):
        code = _generate_invite_code()
        assert isinstance(code, str)


# ---------------------------------------------------------------------------
# Friend add by username tests
# ---------------------------------------------------------------------------

class TestAddFriend:
    """Tests for adding friends by username. Requirement 9.4."""

    @pytest.mark.asyncio
    async def test_add_friend_success(self):
        """Successfully add a friend by username."""
        player_id = uuid4()
        friend = _make_player("bob")
        session = _make_session()

        # First execute: find friend by username
        friend_result = MagicMock()
        friend_result.scalar_one_or_none.return_value = friend

        # Second execute: check existing friendship
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = None

        session.execute = AsyncMock(side_effect=[friend_result, existing_result])

        link = await social_service.add_friend(session, player_id, "bob")

        assert link is not None
        assert session.add.call_count == 2  # bidirectional links

    @pytest.mark.asyncio
    async def test_add_friend_not_found(self):
        """Adding a non-existent username raises ValueError."""
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(ValueError, match="not found"):
            await social_service.add_friend(session, uuid4(), "nonexistent")

    @pytest.mark.asyncio
    async def test_add_self_as_friend_raises(self):
        """Adding yourself as a friend raises ValueError."""
        player_id = uuid4()
        player = _make_player("self_user", player_id=player_id)
        session = _make_session()

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = player
        session.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(ValueError, match="Cannot add yourself"):
            await social_service.add_friend(session, player_id, "self_user")

    @pytest.mark.asyncio
    async def test_add_duplicate_friend_raises(self):
        """Adding an already-existing friend raises ValueError."""
        player_id = uuid4()
        friend = _make_player("bob")
        existing_link = MagicMock(spec=FriendLink)
        session = _make_session()

        # First execute: find friend
        friend_result = MagicMock()
        friend_result.scalar_one_or_none.return_value = friend

        # Second execute: existing link found
        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = existing_link

        session.execute = AsyncMock(side_effect=[friend_result, existing_result])

        with pytest.raises(ValueError, match="Already friends"):
            await social_service.add_friend(session, player_id, "bob")


# ---------------------------------------------------------------------------
# Get friends list tests
# ---------------------------------------------------------------------------

class TestGetFriends:
    """Tests for listing friends. Requirement 9.4."""

    @pytest.mark.asyncio
    async def test_get_friends_returns_list(self):
        """Returns a list of friend entries."""
        player_id = uuid4()
        friend_id = uuid4()
        session = _make_session()

        result_mock = MagicMock()
        result_mock.all.return_value = [(friend_id, "bob")]
        session.execute = AsyncMock(return_value=result_mock)

        friends = await social_service.get_friends(session, player_id)

        assert len(friends) == 1
        assert friends[0]["username"] == "bob"
        assert friends[0]["friend_id"] == str(friend_id)

    @pytest.mark.asyncio
    async def test_get_friends_empty(self):
        """Returns empty list when player has no friends."""
        session = _make_session()
        result_mock = MagicMock()
        result_mock.all.return_value = []
        session.execute = AsyncMock(return_value=result_mock)

        friends = await social_service.get_friends(session, uuid4())
        assert friends == []


# ---------------------------------------------------------------------------
# Join private round tests
# ---------------------------------------------------------------------------

class TestJoinPrivateRound:
    """Tests for joining a private round via invite code. Requirement 9.2."""

    @pytest.mark.asyncio
    async def test_join_valid_invite_code(self):
        """Successfully join a round with a valid invite code in BETTING phase."""
        session = _make_session()
        game_round = MagicMock(spec=GameRound)
        game_round.id = uuid4()
        game_round.phase = RoundPhase.BETTING
        game_round.invite_code = "ABCD1234"

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = game_round
        session.execute = AsyncMock(return_value=result_mock)

        joined = await social_service.join_private_round(session, uuid4(), "ABCD1234")
        assert joined.id == game_round.id

    @pytest.mark.asyncio
    async def test_join_invalid_invite_code(self):
        """Invalid invite code raises ValueError."""
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(ValueError, match="Invalid invite code"):
            await social_service.join_private_round(session, uuid4(), "INVALID1")

    @pytest.mark.asyncio
    async def test_join_round_not_in_betting_phase(self):
        """Joining a round not in BETTING phase raises ValueError."""
        session = _make_session()
        game_round = MagicMock(spec=GameRound)
        game_round.phase = RoundPhase.RESULT
        game_round.invite_code = "ABCD1234"

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = game_round
        session.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(ValueError, match="no longer accepting"):
            await social_service.join_private_round(session, uuid4(), "ABCD1234")


# ---------------------------------------------------------------------------
# Profile display tests
# ---------------------------------------------------------------------------

class TestGetProfile:
    """Tests for profile display with public statistics. Requirement 9.5."""

    @pytest.mark.asyncio
    async def test_profile_with_games(self):
        """Profile shows correct stats for a player with game history."""
        player = _make_player("alice")
        session = _make_session()

        # Mock: find player, total games, wins, leaderboard rank
        player_result = MagicMock()
        player_result.scalar_one_or_none.return_value = player

        games_result = MagicMock()
        games_result.scalar.return_value = 10

        wins_result = MagicMock()
        wins_result.scalar.return_value = 4

        session.execute = AsyncMock(side_effect=[player_result, games_result, wins_result])

        with patch(
            "app.services.social_service.leaderboard_service.get_player_rank",
            new_callable=AsyncMock,
        ) as mock_rank:
            from app.services.leaderboard_service import PlayerRank
            mock_rank.return_value = PlayerRank(rank=5, username="alice", value=Decimal("100.00"))

            stats = await social_service.get_profile(session, "alice")

        assert stats.username == "alice"
        assert stats.total_games_played == 10
        assert stats.win_rate == Decimal("0.40")
        assert stats.leaderboard_rank == 5

    @pytest.mark.asyncio
    async def test_profile_no_games(self):
        """Profile shows zero stats for a player with no game history."""
        player = _make_player("newbie")
        session = _make_session()

        player_result = MagicMock()
        player_result.scalar_one_or_none.return_value = player

        games_result = MagicMock()
        games_result.scalar.return_value = 0

        session.execute = AsyncMock(side_effect=[player_result, games_result])

        with patch(
            "app.services.social_service.leaderboard_service.get_player_rank",
            new_callable=AsyncMock,
        ) as mock_rank:
            from app.services.leaderboard_service import PlayerRank
            mock_rank.return_value = PlayerRank(rank=None, username="newbie", value=None)

            stats = await social_service.get_profile(session, "newbie")

        assert stats.total_games_played == 0
        assert stats.win_rate == Decimal("0.00")
        assert stats.leaderboard_rank is None

    @pytest.mark.asyncio
    async def test_profile_not_found(self):
        """Non-existent username raises ValueError."""
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result_mock)

        with pytest.raises(ValueError, match="not found"):
            await social_service.get_profile(session, "ghost")

    @pytest.mark.asyncio
    async def test_profile_leaderboard_unavailable(self):
        """Profile still works when leaderboard service is unavailable."""
        player = _make_player("alice")
        session = _make_session()

        player_result = MagicMock()
        player_result.scalar_one_or_none.return_value = player

        games_result = MagicMock()
        games_result.scalar.return_value = 5

        wins_result = MagicMock()
        wins_result.scalar.return_value = 2

        session.execute = AsyncMock(side_effect=[player_result, games_result, wins_result])

        with patch(
            "app.services.social_service.leaderboard_service.get_player_rank",
            new_callable=AsyncMock,
            side_effect=Exception("Redis down"),
        ):
            stats = await social_service.get_profile(session, "alice")

        assert stats.leaderboard_rank is None
        assert stats.total_games_played == 5
