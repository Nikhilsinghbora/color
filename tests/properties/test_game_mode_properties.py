"""Property-based tests for game mode configuration.

Uses Hypothesis to generate random game mode configurations and verify
that all configured values are stored and retrieved exactly.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import game_mode_service


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

st_mode_type = st.sampled_from(["classic", "timed_challenge", "tournament"])

# Generate a color as a short alphabetic string (1-10 chars)
st_color = st.text(
    alphabet=st.characters(whitelist_categories=("Ll",)),
    min_size=1,
    max_size=10,
)

# Generate a list of 2-10 unique color strings
st_color_options = st.lists(
    st_color,
    min_size=2,
    max_size=10,
    unique=True,
)

st_round_duration = st.integers(min_value=5, max_value=300)


@st.composite
def st_game_mode_config(draw):
    """Generate a complete, valid game mode configuration."""
    color_options = draw(st_color_options)

    # Generate odds for each color: float between 1.01 and 100.00
    odds = {}
    for color in color_options:
        raw = draw(
            st.decimals(
                min_value=Decimal("1.01"),
                max_value=Decimal("100.00"),
                places=2,
                allow_nan=False,
                allow_infinity=False,
            )
        )
        odds[color] = float(raw)

    min_bet = draw(
        st.decimals(
            min_value=Decimal("0.01"),
            max_value=Decimal("999.99"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        )
    )

    max_bet = draw(
        st.decimals(
            min_value=min_bet,
            max_value=Decimal("99999.99"),
            places=2,
            allow_nan=False,
            allow_infinity=False,
        )
    )

    round_duration_seconds = draw(st_round_duration)
    mode_type = draw(st_mode_type)

    return {
        "color_options": color_options,
        "odds": odds,
        "min_bet": min_bet,
        "max_bet": max_bet,
        "round_duration_seconds": round_duration_seconds,
        "mode_type": mode_type,
    }


# ---------------------------------------------------------------------------
# Property 17: Game mode configuration display
# Response contains all configured values (color_options, odds, min_bet,
# max_bet, round_duration_seconds) matching stored config exactly.
# Validates: Requirements 7.4
# ---------------------------------------------------------------------------


class TestProperty17GameModeConfigDisplay:
    """**Validates: Requirements 7.4**"""

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    )
    @given(config=st_game_mode_config())
    async def test_game_mode_config_round_trip(self, session: AsyncSession, config):
        """For any valid game mode configuration, creating and then
        retrieving the game mode returns all configured values exactly."""
        name = f"mode-{uuid4().hex[:12]}"

        created = await game_mode_service.create_game_mode(
            session,
            name=name,
            mode_type=config["mode_type"],
            color_options=config["color_options"],
            odds=config["odds"],
            min_bet=config["min_bet"],
            max_bet=config["max_bet"],
            round_duration_seconds=config["round_duration_seconds"],
        )

        retrieved = await game_mode_service.get_game_mode(session, created.id)

        # color_options must match exactly
        assert retrieved.color_options == config["color_options"]

        # odds must match exactly (stored as JSON dict)
        assert retrieved.odds == config["odds"]

        # min_bet and max_bet must match (Decimal comparison)
        assert Decimal(str(retrieved.min_bet)) == config["min_bet"]
        assert Decimal(str(retrieved.max_bet)) == config["max_bet"]

        # round_duration_seconds must match exactly
        assert retrieved.round_duration_seconds == config["round_duration_seconds"]

        # mode_type must match exactly
        assert retrieved.mode_type == config["mode_type"]
