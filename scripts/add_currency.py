"""Add currency to all user wallets.

Usage:
    # Add 1,000,000 to all users
    python -m scripts.add_currency --amount 1000000

    # Add custom amount to all users
    python -m scripts.add_currency --amount 500

    # Add to specific user by email
    python -m scripts.add_currency --amount 1000000 --email user@example.com

    # Add to specific user by username
    python -m scripts.add_currency --amount 1000000 --username boranikhilsingh
"""

import asyncio
import argparse
from decimal import Decimal
from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import async_session_factory
from app.models.player import Player, Wallet, Transaction, TransactionType


async def add_currency_to_users(
    amount: Decimal,
    email: str | None = None,
    username: str | None = None,
):
    """Add currency to user wallet(s)."""
    async with async_session_factory() as session:
        # Build query based on filters
        if email:
            query = select(Player).where(Player.email == email)
        elif username:
            query = select(Player).where(Player.username == username)
        else:
            query = select(Player)

        result = await session.execute(query)
        players = result.scalars().all()

        if not players:
            print("[ERROR] No users found matching the criteria")
            return

        updated_count = 0
        total_added = Decimal("0")

        for player in players:
            # Get player's wallet
            wallet_result = await session.execute(
                select(Wallet).where(Wallet.player_id == player.id)
            )
            wallet = wallet_result.scalar_one_or_none()

            if not wallet:
                # Create wallet if it doesn't exist
                wallet = Wallet(
                    id=uuid4(),
                    player_id=player.id,
                    balance=Decimal("0"),
                )
                session.add(wallet)

            old_balance = wallet.balance
            wallet.balance += amount

            # Create transaction record for audit trail
            transaction = Transaction(
                id=uuid4(),
                wallet_id=wallet.id,
                player_id=player.id,
                type=TransactionType.DEPOSIT,
                amount=amount,
                balance_after=wallet.balance,
                reference_id=None,
                description=f"Admin credit: Added {amount} to wallet",
            )
            session.add(transaction)

            updated_count += 1
            total_added += amount

            print(f"[OK] {player.username} ({player.email})")
            print(f"     Old Balance: ${old_balance:,.2f}")
            print(f"     Added: ${amount:,.2f}")
            print(f"     New Balance: ${wallet.balance:,.2f}")

        await session.commit()

        print(f"\n[SUCCESS] Updated {updated_count} user(s)")
        print(f"Total currency added: ${total_added:,.2f}")


def main():
    parser = argparse.ArgumentParser(description="Add currency to user wallets")
    parser.add_argument(
        "--amount",
        type=str,
        required=True,
        help="Amount to add to each user's wallet",
    )
    parser.add_argument(
        "--email",
        type=str,
        default=None,
        help="Add to specific user by email (optional)",
    )
    parser.add_argument(
        "--username",
        type=str,
        default=None,
        help="Add to specific user by username (optional)",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Skip confirmation prompt",
    )

    args = parser.parse_args()

    try:
        amount = Decimal(args.amount)
    except Exception:
        print(f"[ERROR] Invalid amount: {args.amount}")
        return

    if amount <= 0:
        print("[ERROR] Amount must be greater than 0")
        return

    # Show what will happen
    if args.email:
        target = f"user with email: {args.email}"
    elif args.username:
        target = f"user with username: {args.username}"
    else:
        target = "ALL users"

    print(f"\nThis will add ${amount:,.2f} to {target}")

    if not args.confirm:
        confirm = input("\nAre you sure you want to proceed? (yes/no): ")
        if confirm.lower() not in ["yes", "y"]:
            print("[CANCELLED] Operation cancelled")
            return

    print("\nAdding currency...")
    asyncio.run(add_currency_to_users(amount, args.email, args.username))


if __name__ == "__main__":
    main()
