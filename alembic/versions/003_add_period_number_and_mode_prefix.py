"""add_period_number_and_mode_prefix

Revision ID: 003_add_period_number_and_mode_prefix
Revises: 940e259016b0
Create Date: 2026-04-29 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_period_number_and_mode_prefix'
down_revision: Union[str, None] = '940e259016b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add period_number column to game_rounds
    op.add_column(
        'game_rounds',
        sa.Column('period_number', sa.String(20), nullable=True),
    )
    op.create_unique_constraint('uq_game_rounds_period_number', 'game_rounds', ['period_number'])
    op.create_index('ix_game_rounds_period_number', 'game_rounds', ['period_number'])

    # Add mode_prefix column to game_modes
    op.add_column(
        'game_modes',
        sa.Column('mode_prefix', sa.String(3), nullable=False, server_default='100'),
    )

    # Create period_sequences table
    op.create_table(
        'period_sequences',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('game_mode_id', sa.Uuid(), nullable=False),
        sa.Column('date_str', sa.String(8), nullable=False),
        sa.Column('last_sequence', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['game_mode_id'], ['game_modes.id']),
        sa.UniqueConstraint('game_mode_id', 'date_str', name='uq_period_sequences_mode_date'),
    )


def downgrade() -> None:
    # Drop period_sequences table
    op.drop_table('period_sequences')

    # Remove mode_prefix from game_modes
    op.drop_column('game_modes', 'mode_prefix')

    # Remove period_number from game_rounds
    op.drop_index('ix_game_rounds_period_number', table_name='game_rounds')
    op.drop_constraint('uq_game_rounds_period_number', 'game_rounds', type_='unique')
    op.drop_column('game_rounds', 'period_number')
