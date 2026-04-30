"""Pydantic request/response schemas for wallet endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DepositRequest(BaseModel):
    """Request body for depositing funds."""

    amount: Decimal = Field(..., gt=0, le=Decimal("999999.99"), decimal_places=2)
    stripe_token: str = Field(..., min_length=1, max_length=512)


class WithdrawRequest(BaseModel):
    """Request body for withdrawing funds."""

    amount: Decimal = Field(..., gt=0, le=Decimal("999999.99"), decimal_places=2)


class TransactionResponse(BaseModel):
    """Response schema for a single transaction."""

    id: UUID
    wallet_id: UUID
    player_id: UUID
    type: str
    amount: Decimal
    balance_after: Decimal
    reference_id: Optional[UUID] = None
    description: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class WalletResponse(BaseModel):
    """Response schema for wallet balance and transaction history."""

    balance: Decimal
    transactions: list[TransactionResponse] = []
    page: int = 1
    page_size: int = 20
    total: int = 0
