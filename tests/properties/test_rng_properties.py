"""Property-based tests for the RNG engine.

Uses Hypothesis to verify:
- Property 7: RNG winning number uniform distribution (casino-ui-redesign)
- Property 12: Uniform distribution (chi-squared test at 99% confidence)
- Property 13: Audit log completeness
- Property 14: Outcome independence (serial correlation)
"""

from collections import Counter
from uuid import uuid4

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from scipy import stats as scipy_stats
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rng import RNGAuditLog
from app.services.rng_engine import RNGResult, generate_outcome, create_audit_entry


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

st_color_list = st.lists(
    st.text(
        alphabet=st.characters(whitelist_categories=("L",)),
        min_size=1,
        max_size=10,
    ),
    min_size=2,
    max_size=10,
    unique=True,
)


# ---------------------------------------------------------------------------
# Property 12: RNG uniform distribution
# Over 10,000+ outcomes, frequency of each color does not deviate beyond
# chi-squared test at 99% confidence.
# Validates: Requirements 5.2
# ---------------------------------------------------------------------------


class TestProperty12RNGUniformDistribution:
    """**Validates: Requirements 5.2**"""

    @settings(
        max_examples=5,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    )
    @given(
        colors=st.lists(
            st.sampled_from(["red", "green", "blue", "yellow", "purple", "orange"]),
            min_size=2,
            max_size=6,
            unique=True,
        ),
    )
    def test_distribution_passes_chi_squared(self, colors):
        """Over 100,000 outcomes the frequency of each color SHALL not deviate
        from the expected frequency beyond what a chi-squared test at 99%
        confidence allows.

        We use 100,000 samples to reduce variance and max_examples=5 with
        Bonferroni-corrected threshold (0.01/5 = 0.002) to control the
        family-wise error rate across multiple Hypothesis examples.
        """
        num_samples = 100_000
        counts = Counter()

        for _ in range(num_samples):
            result = generate_outcome(colors)
            counts[result.selected_color] += 1

        n = len(colors)
        expected_freq = num_samples / n

        observed = [counts.get(c, 0) for c in colors]
        expected = [expected_freq] * n

        chi2, p_value = scipy_stats.chisquare(observed, f_exp=expected)

        # Bonferroni-corrected threshold: 0.01 / 5 examples = 0.002
        # We use 0.001 for extra margin against flakiness
        assert p_value > 0.001, (
            f"Chi-squared test failed: chi2={chi2:.2f}, p={p_value:.4f}, "
            f"observed={dict(counts)}, expected_each={expected_freq:.1f}"
        )


# ---------------------------------------------------------------------------
# Property 13: RNG audit log completeness
# Every resolved round has audit entry with algorithm="secrets.randbelow",
# raw_value, num_options, and selected_color = color_options[raw_value].
# Validates: Requirements 5.3
# ---------------------------------------------------------------------------


class TestProperty13RNGAuditLogCompleteness:
    """**Validates: Requirements 5.3**"""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    @given(colors=st_color_list)
    async def test_audit_entry_contains_all_required_fields(self, session, colors):
        """Every audit entry SHALL contain algorithm='secrets.randbelow',
        raw_value, num_options, and selected_color = color_options[raw_value]."""
        result = generate_outcome(colors)
        round_id = uuid4()

        entry = await create_audit_entry(session, round_id, result)
        await session.flush()

        # Verify all required fields
        assert entry.algorithm == "secrets.randbelow"
        assert entry.round_id == round_id
        assert 0 <= entry.raw_value < len(colors)
        assert entry.num_options == len(colors)
        assert entry.selected_color == colors[entry.raw_value]

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    @given(colors=st_color_list)
    async def test_audit_entry_persisted_to_database(self, session, colors):
        """The audit entry SHALL be persisted in the rng_audit_logs table."""
        result = generate_outcome(colors)
        round_id = uuid4()

        await create_audit_entry(session, round_id, result)
        await session.flush()

        # Query back from DB
        row = await session.execute(
            select(RNGAuditLog).where(RNGAuditLog.round_id == round_id)
        )
        entry = row.scalar_one()

        assert entry.algorithm == "secrets.randbelow"
        assert entry.raw_value == result.raw_value
        assert entry.num_options == result.num_options
        assert entry.selected_color == result.selected_color

    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow])
    @given(colors=st_color_list)
    async def test_result_selected_color_matches_index(self, session, colors):
        """The selected_color in the RNGResult SHALL equal
        color_options[raw_value]."""
        result = generate_outcome(colors)

        assert result.selected_color == colors[result.raw_value]
        assert result.algorithm == "secrets.randbelow"
        assert result.num_options == len(colors)


# ---------------------------------------------------------------------------
# Property 14: RNG outcome independence
# Serial correlation coefficient between consecutive outcomes is not
# statistically significant (p > 0.01).
# Validates: Requirements 5.4
# ---------------------------------------------------------------------------


class TestProperty14RNGOutcomeIndependence:
    """**Validates: Requirements 5.4**"""

    @settings(
        max_examples=5,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    )
    @given(
        colors=st.lists(
            st.sampled_from(["red", "green", "blue", "yellow", "purple", "orange"]),
            min_size=2,
            max_size=6,
            unique=True,
        ),
    )
    def test_serial_correlation_not_significant(self, colors):
        """The serial correlation coefficient between consecutive outcomes
        SHALL not be statistically significant (p > 0.01).

        We use 100,000 samples and max_examples=5 with Bonferroni-corrected
        threshold to avoid spurious failures from multiple statistical tests.
        """
        num_samples = 100_000
        raw_values = []

        for _ in range(num_samples):
            result = generate_outcome(colors)
            raw_values.append(result.raw_value)

        # Compute serial correlation: correlation between x[i] and x[i+1]
        series_a = raw_values[:-1]
        series_b = raw_values[1:]

        # Pearson correlation test
        corr, p_value = scipy_stats.pearsonr(series_a, series_b)

        # Bonferroni-corrected threshold: 0.01 / 5 = 0.002, use 0.001 for margin
        assert p_value > 0.001, (
            f"Serial correlation is significant: r={corr:.4f}, p={p_value:.4f}. "
            f"Outcomes may not be independent."
        )


# ---------------------------------------------------------------------------
# Feature: casino-ui-redesign, Property 7: RNG winning number uniform distribution
# For any sufficiently large sample of RNG outcomes (N >= 1000), the
# distribution of winning numbers 0-9 SHALL not deviate significantly from
# uniform, as validated by a chi-squared goodness-of-fit test with p > 0.01.
# Validates: Requirements 8.5
# ---------------------------------------------------------------------------


class TestProperty7RNGWinningNumberUniformDistribution:
    """**Validates: Requirements 8.5**"""

    @settings(
        max_examples=5,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    )
    @given(
        sample_size=st.integers(min_value=1000, max_value=5000),
    )
    def test_winning_number_uniform_distribution(self, sample_size):
        """Over 1000+ outcomes the frequency of each winning number (0-9)
        SHALL not deviate from the expected uniform frequency beyond what a
        chi-squared goodness-of-fit test at 99% confidence allows.

        We use Bonferroni-corrected threshold (0.01/5 = 0.002) to control
        the family-wise error rate across multiple Hypothesis examples.
        """
        counts = Counter()

        for _ in range(sample_size):
            result = generate_outcome()
            assert 0 <= result.selected_number <= 9, (
                f"selected_number {result.selected_number} out of range 0-9"
            )
            counts[result.selected_number] += 1

        expected_freq = sample_size / 10
        observed = [counts.get(n, 0) for n in range(10)]
        expected = [expected_freq] * 10

        chi2, p_value = scipy_stats.chisquare(observed, f_exp=expected)

        # Bonferroni-corrected threshold: 0.01 / 5 examples = 0.002
        assert p_value > 0.002, (
            f"Chi-squared test failed for winning numbers: chi2={chi2:.2f}, "
            f"p={p_value:.4f}, observed={dict(counts)}, "
            f"expected_each={expected_freq:.1f}"
        )


# ---------------------------------------------------------------------------
# Feature: casino-ui-redesign, Property 1: Number-to-Color mapping consistency (backend portion)
# For all numbers 0-9, verify NUMBER_COLOR_MAP[n] returns one of
# "green", "red", or "violet".
# Validates: Requirements 2.2, 5.2, 8.3, 8.5
# ---------------------------------------------------------------------------

from app.services.rng_engine import (
    NUMBER_COLOR_MAP,
    GREEN_WINNING_NUMBERS,
    RED_WINNING_NUMBERS,
    VIOLET_WINNING_NUMBERS,
)


class TestProperty1NumberToColorMappingConsistencyBackend:
    """**Validates: Requirements 2.2, 5.2, 8.3, 8.5**"""

    VALID_COLORS = {"green", "red", "violet"}

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(n=st.integers(min_value=0, max_value=9))
    def test_number_color_map_returns_valid_color(self, n):
        """For any number n in 0-9, NUMBER_COLOR_MAP[n] SHALL be one of
        'green', 'red', or 'violet'."""
        color = NUMBER_COLOR_MAP[n]
        assert color in self.VALID_COLORS, (
            f"NUMBER_COLOR_MAP[{n}] = {color!r}, expected one of {self.VALID_COLORS}"
        )

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(n=st.integers(min_value=0, max_value=9))
    def test_number_color_map_covers_all_digits(self, n):
        """NUMBER_COLOR_MAP SHALL have an entry for every number 0-9."""
        assert n in NUMBER_COLOR_MAP, (
            f"NUMBER_COLOR_MAP is missing key {n}"
        )

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(n=st.integers(min_value=0, max_value=9))
    def test_winning_number_sets_consistent_with_map(self, n):
        """For any number n in 0-9, the color from NUMBER_COLOR_MAP[n] SHALL
        be consistent with the GREEN/RED/VIOLET_WINNING_NUMBERS sets:
        - If n in GREEN_WINNING_NUMBERS, color is 'green' or 'violet' (dual-color 0,5)
        - If n in RED_WINNING_NUMBERS, color is 'red'
        - If n in VIOLET_WINNING_NUMBERS, color is 'violet'
        """
        color = NUMBER_COLOR_MAP[n]

        if n in RED_WINNING_NUMBERS:
            assert color == "red", (
                f"Number {n} is in RED_WINNING_NUMBERS but maps to {color!r}"
            )
        if n in VIOLET_WINNING_NUMBERS:
            assert color == "violet", (
                f"Number {n} is in VIOLET_WINNING_NUMBERS but maps to {color!r}"
            )
        if n in GREEN_WINNING_NUMBERS and n not in VIOLET_WINNING_NUMBERS:
            assert color == "green", (
                f"Number {n} is in GREEN_WINNING_NUMBERS (non-violet) but maps to {color!r}"
            )

    @settings(
        max_examples=100,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(n=st.integers(min_value=0, max_value=9))
    def test_every_number_in_at_least_one_winning_set(self, n):
        """Every number 0-9 SHALL appear in at least one of the winning
        number sets (GREEN, RED, or VIOLET)."""
        in_any = (
            n in GREEN_WINNING_NUMBERS
            or n in RED_WINNING_NUMBERS
            or n in VIOLET_WINNING_NUMBERS
        )
        assert in_any, (
            f"Number {n} is not in any winning number set"
        )
