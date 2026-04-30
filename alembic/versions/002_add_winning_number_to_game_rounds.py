"""add winning_number to game_rounds

Revision ID: 002_add_winning_number
Revises: 001_initial_schema
Create Date: 2024-01-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002_add_winning_number"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "game_rounds",
        sa.Column("winning_number", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "chk_winning_number",
        "game_rounds",
        "winning_number IS NULL OR (winning_number >= 0 AND winning_number <= 9)",
    )


def downgrade() -> None:
    op.drop_constraint("chk_winning_number", "game_rounds", type_="check")
    op.drop_column("game_rounds", "winning_number")
