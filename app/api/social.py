"""Social API endpoints.

Routes:
- POST /api/v1/social/invite              — create private round with invite code
- POST /api/v1/social/join/{invite_code}   — join a private round via invite code
- POST /api/v1/social/friends              — add a friend by username
- GET  /api/v1/social/friends              — list friends
- GET  /api/v1/social/profile/{username}   — view a player's public profile

Requirements: 9.1, 9.2, 9.4, 9.5
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_player_id, get_db
from app.schemas.social import FriendRequest, InviteCodeResponse, ProfileResponse
from app.services import social_service

router = APIRouter(prefix="/api/v1/social", tags=["social"])


class CreateInviteRequest(BaseModel):
    """Request body for creating a private round with invite code."""
    game_mode_id: UUID


class JoinRoundResponse(BaseModel):
    """Response after joining a private round."""
    round_id: UUID
    phase: str
    game_mode_id: UUID


class FriendListEntry(BaseModel):
    """Single entry in the friends list."""
    friend_id: str
    username: str


class FriendListResponse(BaseModel):
    """Response for the friends list endpoint."""
    friends: list[FriendListEntry]


class FriendAddResponse(BaseModel):
    """Response after adding a friend."""
    message: str
    friend_username: str


@router.post("/invite", response_model=InviteCodeResponse)
async def create_invite(
    body: CreateInviteRequest,
    db: AsyncSession = Depends(get_db),
    player_id: UUID = Depends(get_current_player_id),
):
    """Create a private game round and return its invite code.

    Requirement 9.1: Generate unique invite code for private rounds.
    """
    try:
        game_round, invite_code = await social_service.create_private_round(
            session=db,
            player_id=player_id,
            game_mode_id=body.game_mode_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return InviteCodeResponse(invite_code=invite_code, round_id=game_round.id)


@router.post("/join/{invite_code}", response_model=JoinRoundResponse)
async def join_round(
    invite_code: str,
    db: AsyncSession = Depends(get_db),
    player_id: UUID = Depends(get_current_player_id),
):
    """Join a private game round using an invite code.

    Requirement 9.2: Join private round via invite code.
    """
    try:
        game_round = await social_service.join_private_round(
            session=db,
            player_id=player_id,
            invite_code=invite_code,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return JoinRoundResponse(
        round_id=game_round.id,
        phase=game_round.phase.value,
        game_mode_id=game_round.game_mode_id,
    )


@router.post("/friends", response_model=FriendAddResponse)
async def add_friend(
    body: FriendRequest,
    db: AsyncSession = Depends(get_db),
    player_id: UUID = Depends(get_current_player_id),
):
    """Add a friend by username.

    Requirement 9.4: Add friends by username.
    """
    try:
        await social_service.add_friend(
            session=db,
            player_id=player_id,
            friend_username=body.username,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return FriendAddResponse(
        message=f"Added {body.username} as a friend",
        friend_username=body.username,
    )


@router.get("/friends", response_model=FriendListResponse)
async def list_friends(
    db: AsyncSession = Depends(get_db),
    player_id: UUID = Depends(get_current_player_id),
):
    """List the current player's friends.

    Requirement 9.4: Friend list management.
    """
    friends = await social_service.get_friends(session=db, player_id=player_id)
    return FriendListResponse(
        friends=[FriendListEntry(**f) for f in friends],
    )


@router.get("/profile/{username}", response_model=ProfileResponse)
async def get_profile(
    username: str,
    db: AsyncSession = Depends(get_db),
    _player_id: UUID = Depends(get_current_player_id),
):
    """View a player's public profile with statistics.

    Requirement 9.5: Display friend public statistics.
    """
    try:
        stats = await social_service.get_profile(session=db, username=username)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return ProfileResponse(
        username=stats.username,
        total_games_played=stats.total_games_played,
        win_rate=stats.win_rate,
        leaderboard_rank=stats.leaderboard_rank,
        member_since=stats.member_since,
    )
