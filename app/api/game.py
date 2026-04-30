"""Game API endpoints.

Routes:
- GET  /api/v1/game/modes              — list active game modes
- GET  /api/v1/game/modes/{mode_id}    — get a single game mode
- GET  /api/v1/game/rounds/{round_id}  — get round state
- POST /api/v1/game/rounds/{round_id}/bet — place a bet
"""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
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
    GameHistoryEntry,
    GameModeResponse,
    MyHistoryEntry,
    PaginatedGameHistory,
    PaginatedMyHistory,
    PlaceBetRequest,
    ResultSummaryResponse,
    RoundStateResponse,
)
from app.services import game_engine, game_mode_service
from app.services.game_mode_service import GameModeNotFoundError

router = APIRouter(prefix="/api/v1/game", tags=["game"])


@router.get("/modes", response_model=list[GameModeResponse])
async def list_modes(db: AsyncSession = Depends(get_db)):
    """List all active game modes with color options, odds, and active round."""
    modes = await game_mode_service.list_game_modes(db, active_only=True)
    results = []
    for m in modes:
        data = GameModeResponse.model_validate(m)
        active_round = await game_engine.get_active_round_for_mode(db, m.id)
        data.active_round_id = active_round.id if active_round else None
        results.append(data)
    return results


@router.get("/history", response_model=PaginatedGameHistory)
async def get_game_history(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    mode_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Return paginated completed game rounds, most recent first.

    Derives big_small_label from winning_number: "Big" if >= 5, else "Small".
    """
    # Base filter: only completed rounds
    base_filter = GameRound.phase == RoundPhase.RESULT
    filters = [base_filter]
    if mode_id:
        try:
            from uuid import UUID as _UUID
            parsed_mode_id = _UUID(mode_id)
            filters.append(GameRound.game_mode_id == parsed_mode_id)
        except ValueError:
            pass  # Invalid UUID — ignore the filter

    # Total count
    count_stmt = select(func.count()).select_from(GameRound).where(*filters)
    total = (await db.execute(count_stmt)).scalar_one()

    # Paginated query
    offset = (page - 1) * size
    stmt = (
        select(GameRound)
        .where(*filters)
        .order_by(GameRound.completed_at.desc())
        .offset(offset)
        .limit(size)
    )
    result = await db.execute(stmt)
    rounds = result.scalars().all()

    items = [
        GameHistoryEntry(
            period_number=r.period_number,
            winning_number=r.winning_number,
            winning_color=r.winning_color,
            big_small_label="Big" if r.winning_number is not None and r.winning_number >= 5 else "Small",
            completed_at=r.completed_at,
        )
        for r in rounds
    ]

    return PaginatedGameHistory(
        items=items,
        total=total,
        page=page,
        size=size,
        has_more=(offset + size) < total,
    )


@router.get("/my-history", response_model=PaginatedMyHistory)
async def get_my_history(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    player_id: UUID = Depends(get_current_player_id),
):
    """Return paginated bet history for the authenticated player.

    Joins Bet with GameRound for period_number and optionally with Payout
    for payout_amount. Ordered by bet created_at descending.
    """
    # Count total bets for this player
    count_stmt = (
        select(func.count())
        .select_from(Bet)
        .where(Bet.player_id == player_id)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    # Paginated query: Bet joined with GameRound and optionally Payout
    offset = (page - 1) * size
    stmt = (
        select(
            Bet.color,
            Bet.amount,
            Bet.is_winner,
            Bet.created_at,
            GameRound.period_number,
            Payout.amount.label("payout_amount"),
        )
        .join(GameRound, Bet.round_id == GameRound.id)
        .outerjoin(Payout, Payout.bet_id == Bet.id)
        .where(Bet.player_id == player_id)
        .order_by(Bet.created_at.desc())
        .offset(offset)
        .limit(size)
    )
    result = await db.execute(stmt)
    rows = result.all()

    items = [
        MyHistoryEntry(
            period_number=row.period_number,
            bet_type=row.color,
            bet_amount=row.amount,
            is_winner=row.is_winner,
            payout_amount=row.payout_amount if row.payout_amount is not None else Decimal("0.00"),
            created_at=row.created_at,
        )
        for row in rows
    ]

    return PaginatedMyHistory(
        items=items,
        total=total,
        page=page,
        size=size,
        has_more=(offset + size) < total,
    )


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

    # Broadcast bet update to all connected clients
    await game_engine.broadcast_bet_update(db, round_id)

    return BetResponse.model_validate(bet)
