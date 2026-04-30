"""add_profit_management_system

Revision ID: 940e259016b0
Revises: 002_add_winning_number
Create Date: 2026-04-28 22:43:23.538540

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '940e259016b0'
down_revision: Union[str, None] = '002_add_winning_number'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create profit_settings table
    op.create_table(
        'profit_settings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('house_profit_percentage', sa.Numeric(5, 2), nullable=False),
        sa.Column('winners_pool_percentage', sa.Numeric(5, 2), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint('house_profit_percentage >= 0 AND house_profit_percentage <= 100', name='valid_house_percentage'),
        sa.CheckConstraint('winners_pool_percentage >= 0 AND winners_pool_percentage <= 100', name='valid_winners_percentage'),
        sa.CheckConstraint('house_profit_percentage + winners_pool_percentage = 100', name='total_percentage_is_100')
    )

    # Add new columns to game_rounds table
    op.add_column('game_rounds', sa.Column('total_payout_pool', sa.Numeric(14, 2), nullable=True))
    op.add_column('game_rounds', sa.Column('house_profit', sa.Numeric(14, 2), nullable=True))
    op.add_column('game_rounds', sa.Column('total_calculated_payouts', sa.Numeric(14, 2), nullable=True))
    op.add_column('game_rounds', sa.Column('payout_reduced', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('game_rounds', sa.Column('applied_house_percentage', sa.Numeric(5, 2), nullable=True))
    op.add_column('game_rounds', sa.Column('applied_winners_percentage', sa.Numeric(5, 2), nullable=True))


def downgrade() -> None:
    # Remove columns from game_rounds
    op.drop_column('game_rounds', 'applied_winners_percentage')
    op.drop_column('game_rounds', 'applied_house_percentage')
    op.drop_column('game_rounds', 'payout_reduced')
    op.drop_column('game_rounds', 'total_calculated_payouts')
    op.drop_column('game_rounds', 'house_profit')
    op.drop_column('game_rounds', 'total_payout_pool')

    # Drop profit_settings table
    op.drop_table('profit_settings')
