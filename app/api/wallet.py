"""Wallet API endpoints.

Routes:
- GET  /api/v1/wallet/balance       — get current wallet balance
- POST /api/v1/wallet/deposit       — deposit funds via Stripe
- POST /api/v1/wallet/withdraw      — request a withdrawal
- GET  /api/v1/wallet/transactions  — paginated transaction history

All endpoints require re-authentication if the JWT was issued more than
10 minutes ago (Requirement 12.4).
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_recent_auth
from app.exceptions import InsufficientBalanceError
from app.schemas.wallet import (
    DepositRequest,
    TransactionResponse,
    WalletResponse,
    WithdrawRequest,
)
from app.services import wallet_service
from app.tasks.wallet_tasks import process_withdrawal

router = APIRouter(prefix="/api/v1/wallet", tags=["wallet"])


@router.get("/balance", response_model=WalletResponse)
async def get_balance(
    db: AsyncSession = Depends(get_db),
    player_id: UUID = Depends(require_recent_auth),
):
    """Return the current wallet balance for the authenticated player."""
    balance = await wallet_service.get_balance(db, player_id)
    return WalletResponse(balance=balance)


@router.post("/deposit", response_model=TransactionResponse)
async def deposit(
    body: DepositRequest,
    db: AsyncSession = Depends(get_db),
    player_id: UUID = Depends(require_recent_auth),
):
    """Process a Stripe payment and credit the player's wallet."""
    transaction = await wallet_service.deposit(
        db,
        player_id=player_id,
        amount=body.amount,
        stripe_token=body.stripe_token,
    )
    return TransactionResponse.model_validate(transaction)


@router.post("/withdraw", response_model=TransactionResponse)
async def withdraw(
    body: WithdrawRequest,
    db: AsyncSession = Depends(get_db),
    player_id: UUID = Depends(require_recent_auth),
):
    """Validate balance and create a withdrawal transaction.

    The actual Stripe payout is processed asynchronously by a Celery task.
    """
    transaction = await wallet_service.withdraw(
        db,
        player_id=player_id,
        amount=body.amount,
    )
    # Enqueue async Celery task for Stripe payout processing
    process_withdrawal.delay(str(transaction.id))
    return TransactionResponse.model_validate(transaction)


@router.get("/transactions", response_model=WalletResponse)
async def get_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    player_id: UUID = Depends(require_recent_auth),
):
    """Return paginated transaction history sorted by most recent first."""
    result = await wallet_service.get_transactions(
        db,
        player_id=player_id,
        page=page,
        page_size=page_size,
    )
    return WalletResponse(
        balance=await wallet_service.get_balance(db, player_id),
        transactions=[
            TransactionResponse.model_validate(t)
            for t in result["transactions"]
        ],
        page=result["page"],
        page_size=result["page_size"],
        total=result["total"],
    )
