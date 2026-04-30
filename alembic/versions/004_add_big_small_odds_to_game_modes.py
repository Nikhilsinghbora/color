"""add_big_small_odds_to_game_modes

Data migration to add "big" and "small" odds to existing game modes.
Extends the odds JSON column to include big/small betting odds (default 2.0x).

Revision ID: 004_add_big_small_odds_to_game_modes
Revises: 003_add_period_number_and_mode_prefix
Create Date: 2026-04-29 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '004_add_big_small_odds_to_game_modes'
down_revision: Union[str, None] = '003_add_period_number_and_mode_prefix'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use a raw SQL approach to update the odds JSON for all existing game modes.
    # This adds "big": "2.0" and "small": "2.0" to the odds JSON object
    # for any game mode that doesn't already have them.
    #
    # Works with PostgreSQL jsonb concatenation operator (||).
    # The || operator merges the two JSON objects, adding new keys
    # without overwriting existing ones if they already exist.
    op.execute(
        sa.text(
            """
            UPDATE game_modes
            SET odds = odds || '{"big": "2.0", "small": "2.0"}'::jsonb
            WHERE NOT (odds ? 'big' AND odds ? 'small')
            """
        )
    )


def downgrade() -> None:
    # Remove "big" and "small" keys from the odds JSON for all game modes.
    op.execute(
        sa.text(
            """
            UPDATE game_modes
            SET odds = odds - 'big' - 'small'
            """
        )
    )
