"""Property-based tests for authentication schemas and password hashing.

Uses Hypothesis to generate random test data for verifying auth invariants.
"""

import string

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st
from pydantic import ValidationError

from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import _hash_password, _verify_password


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid username: 3-50 chars, only [a-zA-Z0-9_-]
_USERNAME_ALPHABET = string.ascii_letters + string.digits + "_-"
st_valid_username = st.text(
    alphabet=_USERNAME_ALPHABET, min_size=3, max_size=50
)

# Valid password: 8-128 chars, must contain uppercase, lowercase, digit, special
_SPECIAL_CHARS = "!@#$%^&*(),.?\":{}|<>"


@st.composite
def st_valid_password(draw):
    """Generate a password that satisfies all complexity rules."""
    upper = draw(st.text(alphabet=string.ascii_uppercase, min_size=1, max_size=10))
    lower = draw(st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=10))
    digit = draw(st.text(alphabet=string.digits, min_size=1, max_size=10))
    special = draw(st.text(alphabet=_SPECIAL_CHARS, min_size=1, max_size=10))
    # Combine and pad to at least 8 chars
    base = upper + lower + digit + special
    if len(base) < 8:
        extra = draw(st.text(alphabet=string.ascii_letters + string.digits, min_size=8 - len(base), max_size=8 - len(base)))
        base += extra
    # Truncate to 128 max
    return base[:128]


# Valid email: simple pattern user@domain.tld
@st.composite
def st_valid_email(draw):
    local = draw(st.text(alphabet=string.ascii_lowercase + string.digits, min_size=1, max_size=20))
    domain = draw(st.text(alphabet=string.ascii_lowercase, min_size=1, max_size=10))
    tld = draw(st.sampled_from(["com", "org", "net", "io"]))
    return f"{local}@{domain}.{tld}"



# ---------------------------------------------------------------------------
# Property 1: Registration input validation
# For any registration payload, invalid email/username/password is rejected;
# valid payloads succeed.
# Validates: Requirements 1.1
# ---------------------------------------------------------------------------


class TestProperty1RegistrationInputValidation:
    """**Validates: Requirements 1.1**"""

    @settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
    @given(email=st_valid_email(), username=st_valid_username, password=st_valid_password())
    def test_valid_payloads_accepted(self, email, username, password):
        """Valid email, username, and password should pass validation."""
        req = RegisterRequest(email=email, username=username, password=password)
        assert req.email == email
        assert req.username == username
        assert req.password == password

    @settings(max_examples=100)
    @given(
        bad_email=st.text(alphabet=string.ascii_letters + string.digits, min_size=1, max_size=30).filter(lambda s: "@" not in s),
        username=st_valid_username,
        password=st_valid_password(),
    )
    def test_invalid_email_rejected(self, bad_email, username, password):
        """Emails without valid format should be rejected."""
        with pytest.raises(ValidationError):
            RegisterRequest(email=bad_email, username=username, password=password)

    @settings(max_examples=100)
    @given(
        email=st_valid_email(),
        short_username=st.text(alphabet=_USERNAME_ALPHABET, min_size=0, max_size=2),
        password=st_valid_password(),
    )
    def test_username_too_short_rejected(self, email, short_username, password):
        """Usernames shorter than 3 characters should be rejected."""
        with pytest.raises(ValidationError):
            RegisterRequest(email=email, username=short_username, password=password)

    @settings(max_examples=100)
    @given(
        email=st_valid_email(),
        long_username=st.text(alphabet=_USERNAME_ALPHABET, min_size=51, max_size=80),
        password=st_valid_password(),
    )
    def test_username_too_long_rejected(self, email, long_username, password):
        """Usernames longer than 50 characters should be rejected."""
        with pytest.raises(ValidationError):
            RegisterRequest(email=email, username=long_username, password=password)

    @settings(max_examples=100)
    @given(
        email=st_valid_email(),
        bad_username=st.text(min_size=3, max_size=50).filter(
            lambda s: not all(c in _USERNAME_ALPHABET for c in s)
        ),
        password=st_valid_password(),
    )
    def test_username_invalid_chars_rejected(self, email, bad_username, password):
        """Usernames with characters outside [a-zA-Z0-9_-] should be rejected."""
        with pytest.raises(ValidationError):
            RegisterRequest(email=email, username=bad_username, password=password)

    @settings(max_examples=100)
    @given(
        email=st_valid_email(),
        username=st_valid_username,
        short_password=st.text(min_size=1, max_size=7),
    )
    def test_password_too_short_rejected(self, email, username, short_password):
        """Passwords shorter than 8 characters should be rejected."""
        with pytest.raises(ValidationError):
            RegisterRequest(email=email, username=username, password=short_password)

    @settings(max_examples=100)
    @given(
        email=st_valid_email(),
        username=st_valid_username,
    )
    def test_password_missing_uppercase_rejected(self, email, username):
        """Passwords without uppercase letters should be rejected."""
        # lowercase + digit + special, no uppercase
        password = "abcdef1!"
        with pytest.raises(ValidationError):
            RegisterRequest(email=email, username=username, password=password)

    @settings(max_examples=100)
    @given(
        email=st_valid_email(),
        username=st_valid_username,
    )
    def test_password_missing_lowercase_rejected(self, email, username):
        """Passwords without lowercase letters should be rejected."""
        password = "ABCDEF1!"
        with pytest.raises(ValidationError):
            RegisterRequest(email=email, username=username, password=password)

    @settings(max_examples=100)
    @given(
        email=st_valid_email(),
        username=st_valid_username,
    )
    def test_password_missing_digit_rejected(self, email, username):
        """Passwords without digits should be rejected."""
        password = "Abcdefgh!"
        with pytest.raises(ValidationError):
            RegisterRequest(email=email, username=username, password=password)

    @settings(max_examples=100)
    @given(
        email=st_valid_email(),
        username=st_valid_username,
    )
    def test_password_missing_special_rejected(self, email, username):
        """Passwords without special characters should be rejected."""
        password = "Abcdefg1"
        with pytest.raises(ValidationError):
            RegisterRequest(email=email, username=username, password=password)


# ---------------------------------------------------------------------------
# Property 2: Password hash round-trip
# For any password, bcrypt hash + verify returns True;
# different password returns False.
# Validates: Requirements 1.2, 1.5
# ---------------------------------------------------------------------------


class TestProperty2PasswordHashRoundTrip:
    """**Validates: Requirements 1.2, 1.5**"""

    @settings(max_examples=100, deadline=None)
    @given(password=st.text(min_size=1, max_size=72))
    def test_hash_then_verify_returns_true(self, password):
        """Hashing a password and verifying with the same password returns True."""
        # bcrypt enforces a 72-byte limit on the encoded password
        assume(len(password.encode("utf-8")) <= 72)
        hashed = _hash_password(password)
        assert _verify_password(password, hashed) is True

    @settings(max_examples=100, deadline=None)
    @given(
        password=st.text(min_size=1, max_size=72),
        other_password=st.text(min_size=1, max_size=72),
    )
    def test_verify_different_password_returns_false(self, password, other_password):
        """Verifying a different password against a hash returns False."""
        assume(password != other_password)
        # bcrypt enforces a 72-byte limit on the encoded password
        assume(len(password.encode("utf-8")) <= 72)
        assume(len(other_password.encode("utf-8")) <= 72)
        hashed = _hash_password(password)
        assert _verify_password(other_password, hashed) is False


# ---------------------------------------------------------------------------
# Property 3: Input validation rejects malicious payloads
# SQL injection, XSS, malformed payloads rejected by Pydantic.
# Validates: Requirements 1.7, 12.6
# ---------------------------------------------------------------------------


class TestProperty3MaliciousPayloadRejection:
    """**Validates: Requirements 1.7, 12.6**"""

    @settings(max_examples=100)
    @given(
        sql_payload=st.sampled_from([
            "'; DROP TABLE players--",
            "' OR '1'='1",
            "admin'--",
            "1; DELETE FROM wallets",
            "' UNION SELECT * FROM players--",
        ]),
    )
    def test_sql_injection_in_email_rejected(self, sql_payload):
        """SQL injection patterns in the email field should be rejected."""
        with pytest.raises(ValidationError):
            RegisterRequest(
                email=sql_payload,
                username="validuser",
                password="ValidPass1!",
            )

    @settings(max_examples=100)
    @given(
        xss_payload=st.sampled_from([
            "<script>alert(1)</script>",
            "<img onerror=alert(1) src=x>",
            "<svg/onload=alert(1)>",
            "user<script>document.cookie</script>",
            "<iframe src='evil.com'>",
        ]),
    )
    def test_xss_in_username_rejected(self, xss_payload):
        """XSS script tags in the username field should be rejected
        because they contain characters outside [a-zA-Z0-9_-]."""
        with pytest.raises(ValidationError):
            RegisterRequest(
                email="test@example.com",
                username=xss_payload,
                password="ValidPass1!",
            )

    @settings(max_examples=100)
    @given(data=st.data())
    def test_missing_required_fields_rejected(self, data):
        """Payloads with missing required fields should be rejected."""
        # Pick which fields to include (at least one missing)
        include_email = data.draw(st.booleans())
        include_username = data.draw(st.booleans())
        include_password = data.draw(st.booleans())
        assume(not (include_email and include_username and include_password))

        kwargs = {}
        if include_email:
            kwargs["email"] = "test@example.com"
        if include_username:
            kwargs["username"] = "validuser"
        if include_password:
            kwargs["password"] = "ValidPass1!"

        with pytest.raises(ValidationError):
            RegisterRequest(**kwargs)

    @settings(max_examples=100)
    @given(
        wrong_type=st.sampled_from([123, True, None, [], {}]),
    )
    def test_wrong_types_for_fields_rejected_register(self, wrong_type):
        """Wrong types for RegisterRequest fields should be rejected."""
        with pytest.raises(ValidationError):
            RegisterRequest(
                email=wrong_type,
                username="validuser",
                password="ValidPass1!",
            )

    @settings(max_examples=100)
    @given(
        sql_payload=st.sampled_from([
            "'; DROP TABLE players--",
            "' OR '1'='1",
            "admin'--",
        ]),
    )
    def test_sql_injection_in_login_email_rejected(self, sql_payload):
        """SQL injection patterns in LoginRequest email should be rejected."""
        with pytest.raises(ValidationError):
            LoginRequest(
                email=sql_payload,
                password="ValidPass1!",
            )
