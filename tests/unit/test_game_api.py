"""Unit tests for game API endpoints."""

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
    assert data[0]["odds"] == {"red": 2.0, "green": 3.0, "blue": 5.0}


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
