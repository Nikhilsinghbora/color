"""initial_schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enum types
transactiontype_enum = postgresql.ENUM(
    "deposit", "withdrawal", "bet_debit", "payout_credit",
    name="transactiontype", create_type=False,
)
roundphase_enum = postgresql.ENUM(
    "betting", "resolution", "result",
    name="roundphase", create_type=False,
)
limitperiod_enum = postgresql.ENUM(
    "daily", "weekly", "monthly",
    name="limitperiod", create_type=False,
)
auditeventtype_enum = postgresql.ENUM(
    "auth_login", "auth_logout", "auth_failed",
    "wallet_deposit", "wallet_withdrawal",
    "admin_config_change", "admin_player_action",
    "responsible_gambling",
    name="auditeventtype", create_type=False,
)


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE transactiontype AS ENUM ('deposit', 'withdrawal', 'bet_debit', 'payout_credit')")
    op.execute("CREATE TYPE roundphase AS ENUM ('betting', 'resolution', 'result')")
    op.execute("CREATE TYPE limitperiod AS ENUM ('daily', 'weekly', 'monthly')")
    op.execute(
        "CREATE TYPE auditeventtype AS ENUM ("
        "'auth_login', 'auth_logout', 'auth_failed', "
        "'wallet_deposit', 'wallet_withdrawal', "
        "'admin_config_change', 'admin_player_action', "
        "'responsible_gambling')"
    )

    # --- players ---
    op.create_table(
        "players",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(50), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_players_email", "players", ["email"])
    op.create_index("ix_players_username", "players", ["username"])

    # --- wallets ---
    op.create_table(
        "wallets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("balance", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.UniqueConstraint("player_id"),
        sa.CheckConstraint("balance >= 0", name="wallet_non_negative_balance"),
    )

    # --- transactions ---
    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("wallet_id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("type", transactiontype_enum, nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("balance_after", sa.Numeric(12, 2), nullable=False),
        sa.Column("reference_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"]),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
    )
    op.create_index("ix_transactions_wallet_id", "transactions", ["wallet_id"])
    op.create_index("ix_transactions_player_id", "transactions", ["player_id"])
    op.create_index("ix_transactions_created_at", "transactions", ["created_at"])

    # --- game_modes ---
    op.create_table(
        "game_modes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("mode_type", sa.String(20), nullable=False),
        sa.Column("color_options", sa.JSON(), nullable=False),
        sa.Column("odds", sa.JSON(), nullable=False),
        sa.Column("min_bet", sa.Numeric(12, 2), nullable=False),
        sa.Column("max_bet", sa.Numeric(12, 2), nullable=False),
        sa.Column("round_duration_seconds", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # --- game_rounds ---
    op.create_table(
        "game_rounds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("game_mode_id", sa.Uuid(), nullable=False),
        sa.Column("phase", roundphase_enum, nullable=False, server_default=sa.text("'betting'")),
        sa.Column("winning_color", sa.String(20), nullable=True),
        sa.Column("total_bets", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("total_payouts", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("flagged_for_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("betting_ends_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["game_mode_id"], ["game_modes.id"]),
    )
    op.create_index("ix_game_rounds_game_mode_id", "game_rounds", ["game_mode_id"])

    # --- bets ---
    op.create_table(
        "bets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("round_id", sa.Uuid(), nullable=False),
        sa.Column("color", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("odds_at_placement", sa.Numeric(6, 2), nullable=False),
        sa.Column("is_winner", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.ForeignKeyConstraint(["round_id"], ["game_rounds.id"]),
        sa.CheckConstraint("amount > 0", name="bet_positive_amount"),
    )
    op.create_index("ix_bets_player_id", "bets", ["player_id"])
    op.create_index("ix_bets_round_id", "bets", ["round_id"])

    # --- payouts ---
    op.create_table(
        "payouts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bet_id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("round_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("credited", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["bet_id"], ["bets.id"]),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.ForeignKeyConstraint(["round_id"], ["game_rounds.id"]),
        sa.UniqueConstraint("bet_id"),
    )
    op.create_index("ix_payouts_player_id", "payouts", ["player_id"])
    op.create_index("ix_payouts_round_id", "payouts", ["round_id"])

    # --- rng_audit_logs ---
    op.create_table(
        "rng_audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("round_id", sa.Uuid(), nullable=False),
        sa.Column("algorithm", sa.String(50), nullable=False, server_default=sa.text("'secrets.randbelow'")),
        sa.Column("raw_value", sa.Integer(), nullable=False),
        sa.Column("num_options", sa.Integer(), nullable=False),
        sa.Column("selected_color", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["round_id"], ["game_rounds.id"]),
        sa.UniqueConstraint("round_id"),
    )

    # --- deposit_limits ---
    op.create_table(
        "deposit_limits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("period", limitperiod_enum, nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("current_usage", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("resets_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.UniqueConstraint("player_id", "period", name="uq_player_deposit_limit_period"),
    )
    op.create_index("ix_deposit_limits_player_id", "deposit_limits", ["player_id"])

    # --- self_exclusions ---
    op.create_table(
        "self_exclusions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("duration", sa.String(20), nullable=False),
        sa.Column("starts_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
    )
    op.create_index("ix_self_exclusions_player_id", "self_exclusions", ["player_id"])

    # --- session_limits ---
    op.create_table(
        "session_limits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
    )
    op.create_index("ix_session_limits_player_id", "session_limits", ["player_id"])

    # --- audit_trail ---
    op.create_table(
        "audit_trail",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", auditeventtype_enum, nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["actor_id"], ["players.id"]),
    )
    op.create_index("ix_audit_trail_event_type", "audit_trail", ["event_type"])
    op.create_index("ix_audit_trail_actor_id", "audit_trail", ["actor_id"])
    op.create_index("ix_audit_trail_created_at", "audit_trail", ["created_at"])

    # --- friend_links ---
    op.create_table(
        "friend_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("friend_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
        sa.ForeignKeyConstraint(["friend_id"], ["players.id"]),
        sa.UniqueConstraint("player_id", "friend_id", name="uq_friend_link"),
    )
    op.create_index("ix_friend_links_player_id", "friend_links", ["player_id"])
    op.create_index("ix_friend_links_friend_id", "friend_links", ["friend_id"])


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("friend_links")
    op.drop_table("audit_trail")
    op.drop_table("session_limits")
    op.drop_table("self_exclusions")
    op.drop_table("deposit_limits")
    op.drop_table("rng_audit_logs")
    op.drop_table("payouts")
    op.drop_table("bets")
    op.drop_table("game_rounds")
    op.drop_table("game_modes")
    op.drop_table("transactions")
    op.drop_table("wallets")
    op.drop_table("players")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS auditeventtype")
    op.execute("DROP TYPE IF EXISTS limitperiod")
    op.execute("DROP TYPE IF EXISTS roundphase")
    op.execute("DROP TYPE IF EXISTS transactiontype")
