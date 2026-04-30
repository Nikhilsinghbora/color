"""Unit tests for game API endpoints."""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_player_id
from app.api.game import router
from app.models.game import GameMode, GameRound, RoundPhase
from app.models.player import Player, Wallet


def _create_app(session: AsyncSession, player_id=None) -> FastAPI:
    """Build a minimal FastAPI app wired to the game router with test overrides."""
    app = FastAPI()
    app.include_router(router)

    async def _override_db():
        yield session

    app.dependency_overrides[get_db] = _override_db

    if player_id is not None:
        app.dependency_overrides[get_current_player_id] = lambda: player_id

    return app


@pytest.mark.asyncio
async def test_list_modes_returns_active(session, game_mode):
    app = _create_app(session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/game/modes")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["name"] == "Classic"
    assert data[0]["color_options"] == ["red", "green", "blue"]
    assert data[0]["odds"] == {"red": 2.0, "green": 3.0, "blue": 5.0, "violet": 4.8, "number": 9.6, "big": 2.0, "small": 2.0}


@pytest.mark.asyncio
async def test_list_modes_includes_active_round_id(session, game_mode, betting_round):
    """GET /modes should include active_round_id when a BETTING round exists."""
    app = _create_app(session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/game/modes")
    assert resp.status_code == 200
    data = resp.json()
    mode_data = next(m for m in data if m["id"] == str(game_mode.id))
    assert mode_data["active_round_id"] == str(betting_round.id)


@pytest.mark.asyncio
async def test_list_modes_active_round_id_none_when_no_active_round(session, game_mode):
    """GET /modes should return active_round_id as None when no active round exists."""
    app = _create_app(session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/game/modes")
    assert resp.status_code == 200
    data = resp.json()
    mode_data = next(m for m in data if m["id"] == str(game_mode.id))
    assert mode_data["active_round_id"] is None


@pytest.mark.asyncio
async def test_list_modes_includes_mode_prefix(session, game_mode):
    """GET /modes should include mode_prefix field."""
    app = _create_app(session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/game/modes")
    assert resp.status_code == 200
    data = resp.json()
    mode_data = next(m for m in data if m["id"] == str(game_mode.id))
    assert "mode_prefix" in mode_data
    assert mode_data["mode_prefix"] == "100"


@pytest.mark.asyncio
async def test_get_mode_by_id(session, game_mode):
    app = _create_app(session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/game/modes/{game_mode.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Classic"
    assert data["min_bet"] == "1.00"
    assert data["max_bet"] == "1000.00"


@pytest.mark.asyncio
async def test_get_mode_not_found(session):
    app = _create_app(session)
    fake_id = uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/game/modes/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_round_state(session, betting_round):
    app = _create_app(session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/game/rounds/{betting_round.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["phase"] == "betting"
    assert data["winning_color"] is None


@pytest.mark.asyncio
async def test_get_round_not_found(session):
    app = _create_app(session)
    fake_id = uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/game/rounds/{fake_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_place_bet_success(session, game_mode, betting_round, player_with_wallet):
    player, wallet = player_with_wallet
    app = _create_app(session, player_id=player.id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/game/rounds/{betting_round.id}/bet",
            json={"color": "red", "amount": "10.00"},
            headers={"X-Player-Id": str(player.id)},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["color"] == "red"
    assert Decimal(data["amount"]) == Decimal("10.00")
    assert Decimal(data["odds_at_placement"]) == Decimal("2.00")


@pytest.mark.asyncio
async def test_place_bet_betting_closed(session, game_mode, player_with_wallet):
    """Bet on a round in RESOLUTION phase should fail with 409."""
    player, wallet = player_with_wallet

    # Create a round and move it to RESOLUTION
    from app.services.game_engine import start_round, resolve_round
    game_round = await start_round(session, game_mode.id)
    await resolve_round(session, game_round.id)

    app = _create_app(session, player_id=player.id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/game/rounds/{game_round.id}/bet",
            json={"color": "red", "amount": "10.00"},
            headers={"X-Player-Id": str(player.id)},
        )
    assert resp.status_code == 409
    assert "BETTING_CLOSED" in str(resp.json())


@pytest.mark.asyncio
async def test_place_bet_below_min(session, game_mode, betting_round, player_with_wallet):
    """Bet below min_bet should fail with 400."""
    player, wallet = player_with_wallet
    app = _create_app(session, player_id=player.id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/game/rounds/{betting_round.id}/bet",
            json={"color": "red", "amount": "0.50"},
            headers={"X-Player-Id": str(player.id)},
        )
    assert resp.status_code == 400
    assert "BET_LIMIT_ERROR" in str(resp.json())


@pytest.mark.asyncio
async def test_place_bet_insufficient_balance(session, game_mode, betting_round, player_with_wallet):
    """Bet exceeding wallet balance should fail with 400."""
    player, wallet = player_with_wallet
    app = _create_app(session, player_id=player.id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/game/rounds/{betting_round.id}/bet",
            json={"color": "red", "amount": "999.00"},
            headers={"X-Player-Id": str(player.id)},
        )
    assert resp.status_code == 400
    assert "INSUFFICIENT_BALANCE" in str(resp.json())


@pytest.mark.asyncio
async def test_place_bet_invalid_amount(session, game_mode, betting_round, player_with_wallet):
    """Negative or zero bet amount should be rejected by Pydantic validation."""
    player, wallet = player_with_wallet
    app = _create_app(session, player_id=player.id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/game/rounds/{betting_round.id}/bet",
            json={"color": "red", "amount": "-5.00"},
            headers={"X-Player-Id": str(player.id)},
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Game History endpoint tests
# ---------------------------------------------------------------------------


async def _create_completed_round(
    session: AsyncSession,
    game_mode: GameMode,
    winning_number: int,
    winning_color: str,
    period_number: str | None = None,
    completed_at: datetime | None = None,
) -> GameRound:
    """Helper to create a completed (RESULT phase) round."""
    from datetime import timezone

    now = completed_at or datetime.now(timezone.utc)
    game_round = GameRound(
        id=uuid4(),
        game_mode_id=game_mode.id,
        phase=RoundPhase.RESULT,
        winning_number=winning_number,
        winning_color=winning_color,
        period_number=period_number,
        betting_ends_at=now - timedelta(seconds=30),
        resolved_at=now - timedelta(seconds=5),
        completed_at=now,
    )
    session.add(game_round)
    await session.flush()
    return game_round


@pytest.mark.asyncio
async def test_history_returns_completed_rounds(session, game_mode):
    """GET /history returns only completed rounds with correct fields."""
    r = await _create_completed_round(
        session, game_mode, winning_number=7, winning_color="green",
        period_number="20250429100000001",
    )
    app = _create_app(session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/game/history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["page"] == 1
    assert data["size"] == 10
    item = data["items"][0]
    assert item["period_number"] == "20250429100000001"
    assert item["winning_number"] == 7
    assert item["winning_color"] == "green"
    assert item["big_small_label"] == "Big"
    assert item["completed_at"] is not None


@pytest.mark.asyncio
async def test_history_big_small_label_small(session, game_mode):
    """Winning number < 5 should produce big_small_label 'Small'."""
    await _create_completed_round(
        session, game_mode, winning_number=3, winning_color="red",
        period_number="20250429100000002",
    )
    app = _create_app(session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/game/history")
    assert resp.status_code == 200
    items = resp.json()["items"]
    # Find the round with winning_number=3
    entry = next(i for i in items if i["winning_number"] == 3)
    assert entry["big_small_label"] == "Small"


@pytest.mark.asyncio
async def test_history_big_small_label_boundary(session, game_mode):
    """Winning number == 5 should produce big_small_label 'Big'."""
    await _create_completed_round(
        session, game_mode, winning_number=5, winning_color="green",
        period_number="20250429100000003",
    )
    app = _create_app(session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/game/history")
    assert resp.status_code == 200
    items = resp.json()["items"]
    entry = next(i for i in items if i["winning_number"] == 5)
    assert entry["big_small_label"] == "Big"


@pytest.mark.asyncio
async def test_history_ordered_by_completed_at_desc(session, game_mode):
    """Results should be ordered by completed_at descending (most recent first)."""
    from datetime import timezone

    base = datetime(2025, 4, 29, 12, 0, 0, tzinfo=timezone.utc)
    await _create_completed_round(
        session, game_mode, winning_number=1, winning_color="red",
        period_number="20250429100000010",
        completed_at=base,
    )
    await _create_completed_round(
        session, game_mode, winning_number=9, winning_color="green",
        period_number="20250429100000011",
        completed_at=base + timedelta(hours=1),
    )
    app = _create_app(session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/game/history")
    assert resp.status_code == 200
    items = resp.json()["items"]
    # Most recent first
    assert len(items) >= 2
    first_completed = items[0]["completed_at"]
    second_completed = items[1]["completed_at"]
    assert first_completed >= second_completed


@pytest.mark.asyncio
async def test_history_pagination(session, game_mode):
    """Pagination should limit results and report has_more correctly."""
    from datetime import timezone

    base = datetime(2025, 5, 1, 0, 0, 0, tzinfo=timezone.utc)
    for i in range(5):
        await _create_completed_round(
            session, game_mode, winning_number=i, winning_color="red",
            period_number=f"20250501100{i:06d}",
            completed_at=base + timedelta(minutes=i),
        )
    app = _create_app(session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/game/history?page=1&size=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] >= 5
    assert data["has_more"] is True
    assert data["page"] == 1
    assert data["size"] == 2


@pytest.mark.asyncio
async def test_history_excludes_non_result_rounds(session, game_mode, betting_round):
    """Rounds not in RESULT phase should not appear in history."""
    app = _create_app(session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/game/history")
    assert resp.status_code == 200
    items = resp.json()["items"]
    # betting_round is in BETTING phase, should not appear
    round_ids = [i.get("period_number") for i in items]
    assert betting_round.period_number not in round_ids or betting_round.period_number is None


@pytest.mark.asyncio
async def test_history_filter_by_mode_id(session):
    """Filtering by mode_id should return only rounds for that mode."""
    mode_a = GameMode(
        id=uuid4(), name="ModeA", mode_type="classic",
        color_options=["red", "green"], min_bet=Decimal("1.00"),
        max_bet=Decimal("100.00"), round_duration_seconds=30,
        odds={"red": 2.0, "green": 2.0, "big": 2.0, "small": 2.0},
    )
    mode_b = GameMode(
        id=uuid4(), name="ModeB", mode_type="classic",
        color_options=["red", "green"], min_bet=Decimal("1.00"),
        max_bet=Decimal("100.00"), round_duration_seconds=60,
        odds={"red": 2.0, "green": 2.0, "big": 2.0, "small": 2.0},
    )
    session.add_all([mode_a, mode_b])
    await session.flush()

    await _create_completed_round(
        session, mode_a, winning_number=8, winning_color="red",
        period_number="20250501200000001",
    )
    await _create_completed_round(
        session, mode_b, winning_number=2, winning_color="green",
        period_number="20250501201000001",
    )

    app = _create_app(session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/v1/game/history?mode_id={mode_a.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["winning_number"] == 8


# ---------------------------------------------------------------------------
# My History endpoint tests
# ---------------------------------------------------------------------------

from app.models.game import Bet, Payout


async def _create_bet(
    session: AsyncSession,
    player_id,
    round_id,
    color: str = "red",
    amount: Decimal = Decimal("10.00"),
    odds: Decimal = Decimal("2.00"),
    is_winner: bool | None = None,
    created_at: datetime | None = None,
) -> Bet:
    """Helper to create a Bet record directly."""
    from datetime import timezone

    bet = Bet(
        id=uuid4(),
        player_id=player_id,
        round_id=round_id,
        color=color,
        amount=amount,
        odds_at_placement=odds,
        is_winner=is_winner,
        created_at=created_at or datetime.now(timezone.utc),
    )
    session.add(bet)
    await session.flush()
    return bet


async def _create_payout(
    session: AsyncSession,
    bet_id,
    player_id,
    round_id,
    amount: Decimal = Decimal("20.00"),
) -> Payout:
    """Helper to create a Payout record directly."""
    payout = Payout(
        id=uuid4(),
        bet_id=bet_id,
        player_id=player_id,
        round_id=round_id,
        amount=amount,
    )
    session.add(payout)
    await session.flush()
    return payout


@pytest.mark.asyncio
async def test_my_history_returns_player_bets(session, game_mode, player_with_wallet):
    """GET /my-history returns the authenticated player's bets with correct fields."""
    player, wallet = player_with_wallet
    game_round = await _create_completed_round(
        session, game_mode, winning_number=7, winning_color="green",
        period_number="20250501100000100",
    )
    bet = await _create_bet(
        session, player.id, game_round.id,
        color="green", amount=Decimal("50.00"), is_winner=True,
    )
    await _create_payout(
        session, bet.id, player.id, game_round.id, amount=Decimal("98.00"),
    )

    app = _create_app(session, player_id=player.id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/game/my-history")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert data["page"] == 1
    assert data["size"] == 10
    item = data["items"][0]
    assert item["period_number"] == "20250501100000100"
    assert item["bet_type"] == "green"
    assert Decimal(item["bet_amount"]) == Decimal("50.00")
    assert item["is_winner"] is True
    assert Decimal(item["payout_amount"]) == Decimal("98.00")
    assert item["created_at"] is not None


@pytest.mark.asyncio
async def test_my_history_no_payout_returns_zero(session, game_mode, player_with_wallet):
    """Bets without a payout record should show payout_amount as 0.00."""
    player, wallet = player_with_wallet
    game_round = await _create_completed_round(
        session, game_mode, winning_number=3, winning_color="red",
        period_number="20250501100000101",
    )
    await _create_bet(
        session, player.id, game_round.id,
        color="green", amount=Decimal("25.00"), is_winner=False,
    )

    app = _create_app(session, player_id=player.id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/game/my-history")
    assert resp.status_code == 200
    items = resp.json()["items"]
    losing_bet = next(i for i in items if i["bet_type"] == "green" and Decimal(i["bet_amount"]) == Decimal("25.00"))
    assert Decimal(losing_bet["payout_amount"]) == Decimal("0.00")
    assert losing_bet["is_winner"] is False


@pytest.mark.asyncio
async def test_my_history_only_own_bets(session, game_mode, player_with_wallet):
    """GET /my-history should only return bets for the authenticated player."""
    player, wallet = player_with_wallet
    game_round = await _create_completed_round(
        session, game_mode, winning_number=5, winning_color="green",
        period_number="20250501100000102",
    )
    # Create a bet for the authenticated player
    await _create_bet(
        session, player.id, game_round.id,
        color="red", amount=Decimal("10.00"),
    )
    # Create a bet for a different player
    other_player_id = uuid4()
    other_player = Player(
        id=other_player_id,
        email="other@example.com",
        username="otherplayer",
        password_hash="hashed",
    )
    session.add(other_player)
    await session.flush()
    await _create_bet(
        session, other_player_id, game_round.id,
        color="big", amount=Decimal("100.00"),
    )

    app = _create_app(session, player_id=player.id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/game/my-history")
    assert resp.status_code == 200
    data = resp.json()
    # All returned bets should belong to the authenticated player
    for item in data["items"]:
        # The other player's bet of 100.00 on "big" should not appear
        if Decimal(item["bet_amount"]) == Decimal("100.00") and item["bet_type"] == "big":
            pytest.fail("Other player's bet appeared in my-history")


@pytest.mark.asyncio
async def test_my_history_ordered_by_created_at_desc(session, game_mode, player_with_wallet):
    """Results should be ordered by created_at descending (most recent first)."""
    from datetime import timezone

    player, wallet = player_with_wallet
    base = datetime(2025, 5, 1, 12, 0, 0, tzinfo=timezone.utc)
    game_round = await _create_completed_round(
        session, game_mode, winning_number=8, winning_color="red",
        period_number="20250501100000103",
    )
    await _create_bet(
        session, player.id, game_round.id,
        color="red", amount=Decimal("10.00"), created_at=base,
    )
    await _create_bet(
        session, player.id, game_round.id,
        color="big", amount=Decimal("20.00"), created_at=base + timedelta(hours=1),
    )

    app = _create_app(session, player_id=player.id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/game/my-history")
    assert resp.status_code == 200
    items = resp.json()["items"]
    # Most recent first
    assert len(items) >= 2
    first_created = items[0]["created_at"]
    second_created = items[1]["created_at"]
    assert first_created >= second_created


@pytest.mark.asyncio
async def test_my_history_pagination(session, game_mode, player_with_wallet):
    """Pagination should limit results and report has_more correctly."""
    from datetime import timezone

    player, wallet = player_with_wallet
    base = datetime(2025, 5, 2, 0, 0, 0, tzinfo=timezone.utc)
    game_round = await _create_completed_round(
        session, game_mode, winning_number=1, winning_color="green",
        period_number="20250502100000001",
    )
    for i in range(5):
        await _create_bet(
            session, player.id, game_round.id,
            color="red", amount=Decimal("5.00"),
            created_at=base + timedelta(minutes=i),
        )

    app = _create_app(session, player_id=player.id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/game/my-history?page=1&size=2")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 2
    assert data["total"] >= 5
    assert data["has_more"] is True
    assert data["page"] == 1
    assert data["size"] == 2


@pytest.mark.asyncio
async def test_my_history_big_small_bet_type(session, game_mode, player_with_wallet):
    """Big/small bets should appear with correct bet_type in my-history."""
    player, wallet = player_with_wallet
    game_round = await _create_completed_round(
        session, game_mode, winning_number=7, winning_color="green",
        period_number="20250502100000002",
    )
    await _create_bet(
        session, player.id, game_round.id,
        color="big", amount=Decimal("30.00"), is_winner=True,
    )

    app = _create_app(session, player_id=player.id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/game/my-history")
    assert resp.status_code == 200
    items = resp.json()["items"]
    big_bet = next(i for i in items if i["bet_type"] == "big")
    assert Decimal(big_bet["bet_amount"]) == Decimal("30.00")
    assert big_bet["is_winner"] is True
