"""Property-based tests for responsible gambling controls.

Uses Hypothesis to generate random test data for verifying deposit limit
enforcement and cumulative loss threshold warning invariants.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import DepositLimitExceededError
from app.models.player import Player, Transaction, TransactionType, Wallet
from app.models.responsible_gambling import DepositLimit, LimitPeriod
from app.services import responsible_gambling_service


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

st_limit_amount = st.decimals(
    min_value=Decimal("10.00"),
    max_value=Decimal("99999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

st_deposit_amount = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("99999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

st_usage_fraction = st.floats(min_value=0.0, max_value=1.0)

st_period = st.sampled_from([LimitPeriod.DAILY, LimitPeriod.WEEKLY, LimitPeriod.MONTHLY])

st_loss_amount = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("50000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

st_threshold = st.decimals(
    min_value=Decimal("10.00"),
    max_value=Decimal("50000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_player(session: AsyncSession) -> Player:
    """Create a fresh player for each Hypothesis iteration."""
    player = Player(
        id=uuid4(),
        email=f"{uuid4().hex[:8]}@test.com",
        username=f"user-{uuid4().hex[:8]}",
        password_hash="hashed",
    )
    session.add(player)
    await session.flush()
    return player


async def _create_player_with_wallet(session: AsyncSession) -> tuple[Player, Wallet]:
    """Create a fresh player with a wallet for transaction tests."""
    player = await _create_player(session)
    wallet = Wallet(
        id=uuid4(),
        player_id=player.id,
        balance=Decimal("0.00"),
        version=0,
    )
    session.add(wallet)
    await session.flush()
    return player, wallet


async def _set_deposit_limit_directly(
    session: AsyncSession,
    player_id,
    period: LimitPeriod,
    amount: Decimal,
    current_usage: Decimal,
) -> DepositLimit:
    """Insert a deposit limit row directly for controlled testing."""
    now = datetime.now(timezone.utc)
    resets_at = responsible_gambling_service._compute_reset_time(period, now)
    limit = DepositLimit(
        id=uuid4(),
        player_id=player_id,
        period=period,
        amount=amount,
        current_usage=current_usage,
        resets_at=resets_at,
    )
    session.add(limit)
    await session.flush()
    return limit


async def _insert_transaction(
    session: AsyncSession,
    player_id,
    wallet_id,
    txn_type: TransactionType,
    amount: Decimal,
    created_at: datetime,
) -> Transaction:
    """Insert a transaction row directly for controlled testing."""
    txn = Transaction(
        id=uuid4(),
        wallet_id=wallet_id,
        player_id=player_id,
        type=txn_type,
        amount=amount,
        balance_after=Decimal("0.00"),
        created_at=created_at,
    )
    session.add(txn)
    await session.flush()
    return txn


# ---------------------------------------------------------------------------
# Property 20: Deposit limit enforcement
# Deposit rejected when current_usage + deposit > limit; response includes
# remaining allowance and reset date. When current_usage + deposit <= limit,
# deposit is allowed with remaining = limit - current_usage.
# Validates: Requirements 10.2
# ---------------------------------------------------------------------------


class TestProperty20DepositLimitEnforcement:
    """**Validates: Requirements 10.2**"""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(data=st.data())
    async def test_deposit_rejected_when_exceeding_limit(self, session, data):
        """For any limit L, usage U, and deposit D where U + D > L,
        check_deposit_limit SHALL raise DepositLimitExceededError with
        remaining = L - U and a non-null resets_at."""
        limit_amount = data.draw(st_limit_amount)
        period = data.draw(st_period)

        # Generate usage that leaves some room (0 to limit - 0.01)
        max_usage = limit_amount - Decimal("0.01")
        if max_usage < Decimal("0.00"):
            max_usage = Decimal("0.00")
        current_usage = data.draw(
            st.decimals(
                min_value=Decimal("0.00"),
                max_value=max_usage,
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )

        remaining = limit_amount - current_usage
        # Deposit must exceed remaining allowance
        min_deposit = remaining + Decimal("0.01")
        assume(min_deposit <= Decimal("99999.99"))
        deposit = data.draw(
            st.decimals(
                min_value=min_deposit,
                max_value=Decimal("99999.99"),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )

        player = await _create_player(session)
        await _set_deposit_limit_directly(
            session, player.id, period, limit_amount, current_usage
        )

        with pytest.raises(DepositLimitExceededError) as exc_info:
            await responsible_gambling_service.check_deposit_limit(
                session, player.id, deposit
            )

        err = exc_info.value
        assert err.remaining == limit_amount - current_usage
        assert err.resets_at is not None

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(data=st.data())
    async def test_deposit_allowed_when_within_limit(self, session, data):
        """For any limit L, usage U, and deposit D where U + D <= L,
        check_deposit_limit SHALL return allowed=True with
        remaining = L - U."""
        limit_amount = data.draw(st_limit_amount)
        period = data.draw(st_period)

        # Generate usage from 0 to limit
        current_usage = data.draw(
            st.decimals(
                min_value=Decimal("0.00"),
                max_value=limit_amount,
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )

        remaining = limit_amount - current_usage
        if remaining < Decimal("0.01"):
            # No room for any deposit — skip this case
            assume(False)

        # Deposit within remaining allowance
        deposit = data.draw(
            st.decimals(
                min_value=Decimal("0.01"),
                max_value=remaining,
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )

        player = await _create_player(session)
        await _set_deposit_limit_directly(
            session, player.id, period, limit_amount, current_usage
        )

        result = await responsible_gambling_service.check_deposit_limit(
            session, player.id, deposit
        )

        assert result.allowed is True
        assert result.remaining == remaining
        assert result.resets_at is not None


# ---------------------------------------------------------------------------
# Property 21: Cumulative loss threshold warning
# Warning triggered when 24h losses > threshold; no warning when <= threshold.
# Losses = sum(bet_debits) - sum(payout_credits) over last 24 hours.
# Validates: Requirements 10.6
# ---------------------------------------------------------------------------


class TestProperty21CumulativeLossThresholdWarning:
    """**Validates: Requirements 10.6**"""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(data=st.data())
    async def test_warning_triggered_when_losses_exceed_threshold(self, session, data):
        """For any set of 24h transactions where net loss > threshold,
        check_loss_threshold SHALL return True."""
        threshold = data.draw(st_threshold)

        # Generate total debits that exceed threshold + credits
        total_credits = data.draw(
            st.decimals(
                min_value=Decimal("0.00"),
                max_value=Decimal("20000.00"),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )
        # Net loss must exceed threshold, so debits > threshold + credits
        min_debits = total_credits + threshold + Decimal("0.01")
        assume(min_debits <= Decimal("99999.99"))
        total_debits = data.draw(
            st.decimals(
                min_value=min_debits,
                max_value=min(min_debits + Decimal("10000.00"), Decimal("99999.99")),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )
        assume(total_debits - total_credits > threshold)

        player, wallet = await _create_player_with_wallet(session)
        now = datetime.now(timezone.utc)

        # Insert bet_debit transaction within 24h window
        if total_debits > Decimal("0.00"):
            await _insert_transaction(
                session, player.id, wallet.id,
                TransactionType.BET_DEBIT, total_debits,
                created_at=now - timedelta(hours=1),
            )

        # Insert payout_credit transaction within 24h window
        if total_credits > Decimal("0.00"):
            await _insert_transaction(
                session, player.id, wallet.id,
                TransactionType.PAYOUT_CREDIT, total_credits,
                created_at=now - timedelta(minutes=30),
            )

        result = await responsible_gambling_service.check_loss_threshold(
            session, player.id, threshold=threshold
        )
        assert result is True

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(data=st.data())
    async def test_no_warning_when_losses_at_or_below_threshold(self, session, data):
        """For any set of 24h transactions where net loss <= threshold,
        check_loss_threshold SHALL return False."""
        threshold = data.draw(st_threshold)

        # Generate credits first
        total_credits = data.draw(
            st.decimals(
                min_value=Decimal("0.00"),
                max_value=Decimal("20000.00"),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )
        # Net loss must be <= threshold, so debits <= threshold + credits
        max_debits = total_credits + threshold
        total_debits = data.draw(
            st.decimals(
                min_value=Decimal("0.00"),
                max_value=min(max_debits, Decimal("99999.99")),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )
        assume(total_debits - total_credits <= threshold)

        player, wallet = await _create_player_with_wallet(session)
        now = datetime.now(timezone.utc)

        # Insert bet_debit transaction within 24h window
        if total_debits > Decimal("0.00"):
            await _insert_transaction(
                session, player.id, wallet.id,
                TransactionType.BET_DEBIT, total_debits,
                created_at=now - timedelta(hours=1),
            )

        # Insert payout_credit transaction within 24h window
        if total_credits > Decimal("0.00"):
            await _insert_transaction(
                session, player.id, wallet.id,
                TransactionType.PAYOUT_CREDIT, total_credits,
                created_at=now - timedelta(minutes=30),
            )

        result = await responsible_gambling_service.check_loss_threshold(
            session, player.id, threshold=threshold
        )
        assert result is False
