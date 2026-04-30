"""Create an admin user for accessing the admin dashboard.

Usage:
    python -m scripts.create_admin --email admin@example.com --username admin --password yourpassword

Or use environment variables:
    ADMIN_EMAIL=admin@example.com ADMIN_USERNAME=admin ADMIN_PASSWORD=yourpassword python -m scripts.create_admin
"""

import asyncio
import argparse
import os
from uuid import uuid4
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.base import async_session_factory
from app.models.player import Player, Wallet
from app.services.auth_service import _hash_password


async def create_admin_user(email: str, username: str, password: str):
    """Create an admin user with is_admin=True."""
    async with async_session_factory() as session:
        # Check if user already exists
        result = await session.execute(
            select(Player).where((Player.email == email) | (Player.username == username))
        )
        existing = result.scalar_one_or_none()

        if existing:
            if existing.is_admin:
                print(f"[OK] Admin user already exists: {existing.email}")
                return
            else:
                # Upgrade existing user to admin
                existing.is_admin = True
                await session.commit()
                print(f"[OK] Upgraded existing user to admin: {existing.email}")
                return

        # Create new admin user
        player_id = uuid4()
        hashed_password = _hash_password(password)

        player = Player(
            id=player_id,
            email=email,
            username=username,
            password_hash=hashed_password,
            is_admin=True,
        )
        session.add(player)

        # Create wallet for admin
        wallet = Wallet(
            id=uuid4(),
            player_id=player_id,
            balance=Decimal("10000.00"),  # Give admin starting balance
        )
        session.add(wallet)

        try:
            await session.commit()
            print(f"[OK] Created admin user:")
            print(f"  Email: {email}")
            print(f"  Username: {username}")
            print(f"  Password: {password}")
            print(f"  Wallet Balance: $10,000.00")
            print(f"\nAccess admin dashboard at: http://localhost:3000/admin")
        except IntegrityError as e:
            await session.rollback()
            print(f"[ERROR] Failed to create admin user: {e}")


def main():
    parser = argparse.ArgumentParser(description="Create an admin user")
    parser.add_argument(
        "--email",
        type=str,
        default=os.getenv("ADMIN_EMAIL", "admin@example.com"),
        help="Admin email (default: admin@example.com or $ADMIN_EMAIL)",
    )
    parser.add_argument(
        "--username",
        type=str,
        default=os.getenv("ADMIN_USERNAME", "admin"),
        help="Admin username (default: admin or $ADMIN_USERNAME)",
    )
    parser.add_argument(
        "--password",
        type=str,
        default=os.getenv("ADMIN_PASSWORD", "admin123"),
        help="Admin password (default: admin123 or $ADMIN_PASSWORD)",
    )

    args = parser.parse_args()

    print(f"Creating admin user...")
    asyncio.run(create_admin_user(args.email, args.username, args.password))


if __name__ == "__main__":
    main()
