"""Game API endpoints.

Routes:
- GET  /api/v1/game/modes              — list active game modes
- GET  /api/v1/game/modes/{mode_id}    — get a single game mode
- GET  /api/v1/game/rounds/{round_id}  — get round state
- POST /api/v1/game/rounds/{round_id}/bet — place a bet
"""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_player_id, get_db
from app.exceptions import (
    BetLimitError,
    BettingClosedError,
    InsufficientBalanceError,
    InvalidTransitionError,
)
from app.models.game import Bet, GameRound, Payout, RoundPhase
from app.schemas.game import (
    BetResponse,
    GameModeResponse,
    PlaceBetRequest,
    ResultSummaryResponse,
    RoundStateResponse,
)
from app.services import game_engine, game_mode_service
from app.services.game_mode_service import GameModeNotFoundError

router = APIRouter(prefix="/api/v1/game", tags=["game"])


@router.get("/modes", response_model=list[GameModeResponse])
async def list_modes(db: AsyncSession = Depends(get_db)):
    """List all active game modes with color options and odds."""
    modes = await game_mode_service.list_game_modes(db, active_only=True)
    return [GameModeResponse.model_validate(m) for m in modes]


@router.get("/modes/{mode_id}", response_model=GameModeResponse)
async def get_mode(mode_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a single game mode by ID."""
    try:
        mode = await game_mode_service.get_game_mode(db, mode_id)
    except GameModeNotFoundError:
        raise HTTPException(status_code=404, detail="Game mode not found")
    return GameModeResponse.model_validate(mode)


@router.get("/rounds/{round_id}", response_model=RoundStateResponse)
async def get_round(round_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get the current state of a game round."""
    try:
        state = await game_engine.get_round_state(db, round_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Round not found")
    return RoundStateResponse(
        round_id=state.round_id,
        game_mode_id=state.game_mode_id,
        phase=state.phase.value,
        winning_color=state.winning_color,
        total_bets=state.total_bets,
        total_payouts=state.total_payouts,
        betting_ends_at=state.betting_ends_at,
        resolved_at=state.resolved_at,
        completed_at=state.completed_at,
    )


@router.post("/rounds/{round_id}/bet", response_model=BetResponse | ResultSummaryResponse)
async def place_bet(
    round_id: UUID,
    body: PlaceBetRequest,
    db: AsyncSession = Depends(get_db),
    player_id: UUID = Depends(get_current_player_id),
):
    """Place a bet on a color for a given round.

    During BETTING phase: returns the placed bet with odds.
    After RESULT phase: the round endpoint shows the result summary.
    """
    try:
        bet = await game_engine.place_bet(
            db,
            player_id=player_id,
            round_id=round_id,
            color=body.color,
            amount=body.amount,
        )
    except BettingClosedError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "BETTING_CLOSED",
                "message": str(exc),
            },
        )
    except BetLimitError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "BET_LIMIT_ERROR",
                "message": str(exc),
                "min_bet": str(exc.min_bet),
                "max_bet": str(exc.max_bet),
            },
        )
    except InsufficientBalanceError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INSUFFICIENT_BALANCE",
                "message": str(exc),
                "balance": str(exc.balance),
                "requested": str(exc.requested),
            },
        )
    except InvalidTransitionError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "INVALID_TRANSITION",
                "message": str(exc),
            },
        )

    return BetResponse.model_validate(bet)
