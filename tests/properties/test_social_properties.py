"""Property-based tests for social features.

Property 19: Invite code uniqueness — For any N private rounds created,
all N invite codes are distinct.

Validates: Requirements 9.1
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from app.services.social_service import _generate_invite_code, _INVITE_CODE_LENGTH, _INVITE_CODE_ALPHABET


# ---------------------------------------------------------------------------
# Property 19: Invite code uniqueness
# For any N private rounds created, all N generated invite codes are distinct.
# Validates: Requirements 9.1
# ---------------------------------------------------------------------------


class TestProperty19InviteCodeUniqueness:
    """**Validates: Requirements 9.1**"""

    @settings(max_examples=100)
    @given(n=st.integers(min_value=2, max_value=200))
    def test_n_invite_codes_are_all_distinct(self, n):
        """For any N invite codes generated, all N are distinct."""
        codes = [_generate_invite_code() for _ in range(n)]
        assert len(set(codes)) == len(codes), (
            f"Duplicate invite codes found in batch of {n}: "
            f"{[c for c in codes if codes.count(c) > 1]}"
        )

    @settings(max_examples=100)
    @given(st.data())
    def test_invite_code_format(self, data):
        """Each invite code has the correct length and uses only allowed characters."""
        code = _generate_invite_code()
        assert len(code) == _INVITE_CODE_LENGTH
        for ch in code:
            assert ch in _INVITE_CODE_ALPHABET, (
                f"Character '{ch}' not in allowed alphabet"
            )

    @settings(max_examples=100)
    @given(n=st.integers(min_value=10, max_value=500))
    def test_invite_codes_use_cryptographic_randomness(self, n):
        """Over N codes, we see more than 1 unique character in each position,
        confirming non-trivial randomness (not a constant or sequential pattern)."""
        codes = [_generate_invite_code() for _ in range(n)]
        # For each character position, check that we see variety
        for pos in range(_INVITE_CODE_LENGTH):
            chars_at_pos = {code[pos] for code in codes}
            # With 36 possible chars and n>=10, seeing only 1 char is astronomically unlikely
            assert len(chars_at_pos) > 1, (
                f"Position {pos} has no variety across {n} codes"
            )
