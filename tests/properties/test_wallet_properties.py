"""Property-based tests for wallet operations.

Uses Hypothesis to generate random test data for verifying wallet invariants.
"""

from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import InsufficientBalanceError
from app.models.player import Player, Transaction, TransactionType, Wallet
from app.services import wallet_service


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

st_amount = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("99999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

st_small_amount = st.decimals(
    min_value=Decimal("0.01"),
    max_value=Decimal("9999.99"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

st_operation_type = st.sampled_from(["credit", "debit"])


# ---------------------------------------------------------------------------
# Fixtures — disable Redis for all tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _no_redis(monkeypatch):
    """Disable Redis in all wallet property tests."""
    monkeypatch.setattr(wallet_service, "_get_redis", AsyncMock(return_value=None))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_player_with_wallet(
    session: AsyncSession,
    balance: Decimal = Decimal("0.00"),
) -> tuple[Player, Wallet]:
    """Create a fresh player and wallet for each Hypothesis iteration."""
    player = Player(
        id=uuid4(),
        email=f"{uuid4().hex[:8]}@test.com",
        username=f"user-{uuid4().hex[:8]}",
        password_hash="hashed",
    )
    session.add(player)
    await session.flush()

    wallet = Wallet(
        id=uuid4(),
        player_id=player.id,
        balance=balance,
        version=0,
    )
    session.add(wallet)
    await session.flush()
    return player, wallet


# ---------------------------------------------------------------------------
# Property 4: Withdrawal balance guard
# Withdrawal > balance rejected; 0 < withdrawal ≤ balance accepted with
# correct resulting balance.
# Validates: Requirements 2.3, 2.4
# ---------------------------------------------------------------------------


class TestProperty4WithdrawalBalanceGuard:
    """**Validates: Requirements 2.3, 2.4**"""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(data=st.data())
    async def test_withdrawal_exceeding_balance_rejected(self, session, data):
        """For any wallet with balance B and withdrawal A > B, the withdrawal
        SHALL be rejected with InsufficientBalanceError."""
        balance = data.draw(st_small_amount)
        player, wallet = await _create_player_with_wallet(session, balance=balance)

        # Withdrawal must exceed balance
        withdrawal = data.draw(
            st.decimals(
                min_value=balance + Decimal("0.01"),
                max_value=Decimal("99999.99"),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )
        assume(withdrawal > balance)

        with pytest.raises(InsufficientBalanceError) as exc_info:
            await wallet_service.withdraw(session, player.id, withdrawal)

        assert exc_info.value.balance == balance
        assert exc_info.value.requested == withdrawal

        # Balance unchanged
        await session.refresh(wallet)
        assert wallet.balance == balance

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(data=st.data())
    async def test_valid_withdrawal_accepted_with_correct_balance(self, session, data):
        """For any wallet with balance B and withdrawal A where 0 < A ≤ B,
        the withdrawal SHALL succeed and resulting balance = B - A."""
        balance = data.draw(
            st.decimals(
                min_value=Decimal("0.01"),
                max_value=Decimal("99999.99"),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )
        player, wallet = await _create_player_with_wallet(session, balance=balance)

        withdrawal = data.draw(
            st.decimals(
                min_value=Decimal("0.01"),
                max_value=balance,
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )

        txn = await wallet_service.withdraw(session, player.id, withdrawal)

        assert txn.balance_after == balance - withdrawal
        await session.refresh(wallet)
        assert wallet.balance == balance - withdrawal


# ---------------------------------------------------------------------------
# Property 5: Transaction record completeness
# Every wallet operation produces a Transaction with non-null ID, timestamp,
# amount, type, and correct balance_after.
# Validates: Requirements 2.5
# ---------------------------------------------------------------------------


class TestProperty5TransactionRecordCompleteness:
    """**Validates: Requirements 2.5**"""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(amount=st_small_amount)
    async def test_withdraw_produces_complete_transaction(self, session, amount):
        """Withdrawal produces a Transaction with all required fields."""
        balance = amount + Decimal("100.00")  # ensure sufficient balance
        player, wallet = await _create_player_with_wallet(session, balance=balance)

        txn = await wallet_service.withdraw(session, player.id, amount)

        assert txn.id is not None
        assert txn.created_at is not None
        assert txn.amount == amount
        assert txn.type == TransactionType.WITHDRAWAL
        assert txn.balance_after == balance - amount

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(amount=st_small_amount)
    async def test_debit_produces_complete_transaction(self, session, amount):
        """Debit produces a Transaction with all required fields."""
        balance = amount + Decimal("100.00")
        player, wallet = await _create_player_with_wallet(session, balance=balance)
        round_id = uuid4()

        txn = await wallet_service.debit(session, player.id, amount, round_id)
        await session.flush()

        assert txn.id is not None
        assert txn.created_at is not None
        assert txn.amount == amount
        assert txn.type == TransactionType.BET_DEBIT
        assert txn.balance_after == balance - amount
        assert txn.reference_id == round_id

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(amount=st_small_amount)
    async def test_credit_produces_complete_transaction(self, session, amount):
        """Credit produces a Transaction with all required fields."""
        balance = Decimal("100.00")
        player, wallet = await _create_player_with_wallet(session, balance=balance)
        round_id = uuid4()

        txn = await wallet_service.credit(session, player.id, amount, round_id)
        await session.flush()

        assert txn.id is not None
        assert txn.created_at is not None
        assert txn.amount == amount
        assert txn.type == TransactionType.PAYOUT_CREDIT
        assert txn.balance_after == balance + amount
        assert txn.reference_id == round_id


# ---------------------------------------------------------------------------
# Property 6: Transaction history ordering
# Paginated history returns transactions sorted by created_at descending,
# each page ≤ page_size entries.
# Validates: Requirements 2.6
# ---------------------------------------------------------------------------


class TestProperty6TransactionHistoryOrdering:
    """**Validates: Requirements 2.6**"""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
    @given(
        num_txns=st.integers(min_value=1, max_value=15),
        page_size=st.integers(min_value=1, max_value=10),
    )
    async def test_history_sorted_descending_and_page_size_respected(
        self, session, num_txns, page_size
    ):
        """For any set of transactions, paginated history is sorted by
        created_at descending and each page has at most page_size entries."""
        balance = Decimal("0.01") * num_txns + Decimal("100.00")
        player, wallet = await _create_player_with_wallet(session, balance=balance)

        round_id = uuid4()
        for _ in range(num_txns):
            await wallet_service.debit(session, player.id, Decimal("0.01"), round_id)
        await session.flush()

        # Check every page
        total_seen = 0
        page = 1
        prev_created_at = None
        while True:
            result = await wallet_service.get_transactions(
                session, player.id, page=page, page_size=page_size
            )
            txns = result["transactions"]

            # Page size constraint
            assert len(txns) <= page_size

            # Ordering constraint: each transaction's created_at ≤ previous
            for txn in txns:
                if prev_created_at is not None:
                    assert txn.created_at <= prev_created_at
                prev_created_at = txn.created_at

            total_seen += len(txns)
            if len(txns) < page_size:
                break
            page += 1

        assert total_seen == num_txns


# ---------------------------------------------------------------------------
# Property 7: Wallet balance consistency
# For any sequence of operations from balance 0, final balance =
# sum(credits) - sum(debits), never negative at any step.
# Validates: Requirements 2.7
# ---------------------------------------------------------------------------


class TestProperty7WalletBalanceConsistency:
    """**Validates: Requirements 2.7**"""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        ops=st.lists(
            st.tuples(
                st_operation_type,
                st.decimals(
                    min_value=Decimal("0.01"),
                    max_value=Decimal("500.00"),
                    places=2,
                    allow_nan=False,
                    allow_infinity=False,
                ),
            ),
            min_size=1,
            max_size=10,
        )
    )
    async def test_balance_equals_credits_minus_debits_never_negative(
        self, session, ops
    ):
        """For any sequence of credit/debit operations starting from balance 0,
        the final balance equals sum(credits) - sum(debits) and the balance
        is never negative at any intermediate step."""
        player, wallet = await _create_player_with_wallet(
            session, balance=Decimal("0.00")
        )

        running_balance = Decimal("0.00")
        total_credits = Decimal("0.00")
        total_debits = Decimal("0.00")
        round_id = uuid4()

        for op_type, amount in ops:
            if op_type == "credit":
                txn = await wallet_service.credit(
                    session, player.id, amount, round_id
                )
                running_balance += amount
                total_credits += amount
                assert txn.balance_after == running_balance
            else:
                # debit — skip if would go negative
                if amount > running_balance:
                    with pytest.raises(InsufficientBalanceError):
                        await wallet_service.debit(
                            session, player.id, amount, round_id
                        )
                    # Balance unchanged
                    continue
                txn = await wallet_service.debit(
                    session, player.id, amount, round_id
                )
                running_balance -= amount
                total_debits += amount
                assert txn.balance_after == running_balance

            # Balance never negative
            assert running_balance >= Decimal("0.00")

        # Final balance check
        await session.flush()
        await session.refresh(wallet)
        assert wallet.balance == running_balance
        assert wallet.balance == total_credits - total_debits


# ---------------------------------------------------------------------------
# Property 11: Wallet debit equals bet amount
# For valid bet amount A with balance B ≥ A, resulting balance = B - A exactly.
# Validates: Requirements 4.4
# ---------------------------------------------------------------------------


class TestProperty11WalletDebitEqualsBetAmount:
    """**Validates: Requirements 4.4**"""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(data=st.data())
    async def test_debit_results_in_exact_balance(self, session, data):
        """For any valid bet amount A with balance B ≥ A, the resulting
        wallet balance SHALL equal B - A exactly."""
        balance = data.draw(
            st.decimals(
                min_value=Decimal("0.01"),
                max_value=Decimal("99999.99"),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )
        player, wallet = await _create_player_with_wallet(session, balance=balance)

        bet_amount = data.draw(
            st.decimals(
                min_value=Decimal("0.01"),
                max_value=balance,
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )

        round_id = uuid4()
        txn = await wallet_service.debit(session, player.id, bet_amount, round_id)
        await session.flush()

        expected_balance = balance - bet_amount
        assert txn.balance_after == expected_balance

        await session.refresh(wallet)
        assert wallet.balance == expected_balance
