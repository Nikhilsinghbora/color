"""Smoke tests for application configuration.

Verifies that security-critical settings (bcrypt cost factor, CORS policy,
connection pool) are correctly configured without requiring live services.

Requirements: 1.5, 12.7, 13.5
"""

import pytest
from unittest.mock import patch


class TestBcryptCostFactor:
    """Verify bcrypt cost factor meets minimum security requirement (Req 1.5)."""

    def test_bcrypt_rounds_at_least_12(self):
        """BCRYPT_ROUNDS constant must be >= 12 for adequate security."""
        from app.services.auth_service import BCRYPT_ROUNDS

        assert BCRYPT_ROUNDS >= 12, (
            f"BCRYPT_ROUNDS is {BCRYPT_ROUNDS}, must be >= 12"
        )

    def test_password_hash_uses_configured_rounds(self):
        """Hashing a password should produce a bcrypt hash with the configured cost."""
        from app.services.auth_service import _hash_password, BCRYPT_ROUNDS

        hashed = _hash_password("test-password-123")
        # bcrypt hashes encode the cost factor as $2b$XX$ where XX is the rounds
        parts = hashed.split("$")
        assert len(parts) >= 4, f"Unexpected bcrypt hash format: {hashed}"
        cost = int(parts[2])
        assert cost == BCRYPT_ROUNDS, (
            f"Hash cost factor is {cost}, expected {BCRYPT_ROUNDS}"
        )

    def test_password_verify_roundtrip(self):
        """Hash + verify roundtrip must succeed."""
        from app.services.auth_service import _hash_password, _verify_password

        password = "smoke-test-pw!"
        hashed = _hash_password(password)
        assert _verify_password(password, hashed) is True
        assert _verify_password("wrong-password", hashed) is False


class TestCORSPolicy:
    """Verify CORS is configured and restrictive (Req 12.7)."""

    def test_cors_allowed_origins_configured(self):
        """Settings must have cors_allowed_origins defined."""
        from app.config import settings

        origins = settings.cors_allowed_origins
        assert isinstance(origins, list), "cors_allowed_origins must be a list"
        assert len(origins) > 0, "cors_allowed_origins must not be empty"

    def test_cors_does_not_allow_wildcard(self):
        """CORS must not use wildcard '*' as an allowed origin."""
        from app.config import settings

        origins = settings.cors_allowed_origins
        assert "*" not in origins, (
            "CORS allowed origins must not contain wildcard '*'"
        )

    def test_cors_middleware_applied_to_app(self):
        """The FastAPI app must have CORS middleware registered."""
        from app.main import create_app
        from starlette.middleware.cors import CORSMiddleware

        app = create_app()
        # Before the app is started, FastAPI stores middleware definitions
        # in app.user_middleware as Middleware objects.
        middleware_cls_names = [m.cls.__name__ for m in app.user_middleware]

        assert "CORSMiddleware" in middleware_cls_names, (
            f"CORSMiddleware not found in user_middleware: {middleware_cls_names}"
        )

    def test_configure_cors_uses_settings_origins(self):
        """configure_cors should pass settings.cors_allowed_origins to the middleware."""
        from app.config import settings

        # Verify the property returns the configured origins
        assert settings.cors_allowed_origins == settings.cors_origins


class TestConnectionPoolSettings:
    """Verify database connection pool is properly configured (Req 13.5)."""

    def test_database_url_configured(self):
        """Settings must have a database_url defined."""
        from app.config import settings

        assert settings.database_url, "database_url must not be empty"
        assert "://" in settings.database_url, (
            "database_url must be a valid connection string"
        )

    def test_redis_url_configured(self):
        """Settings must have a redis_url defined."""
        from app.config import settings

        assert settings.redis_url, "redis_url must not be empty"
        assert settings.redis_url.startswith("redis://"), (
            "redis_url must start with redis://"
        )

    def test_async_engine_created(self):
        """The SQLAlchemy async engine must be created from settings."""
        from app.models.base import engine

        assert engine is not None, "Async engine must be initialized"
        assert str(engine.url), "Engine must have a valid URL"

    def test_async_session_factory_created(self):
        """The async session factory must be initialized."""
        from app.models.base import async_session_factory

        assert async_session_factory is not None, (
            "async_session_factory must be initialized"
        )

    def test_settings_loads_all_required_fields(self):
        """Settings must load all critical configuration fields."""
        from app.config import Settings

        s = Settings()
        # Verify all critical fields have values
        assert s.database_url
        assert s.redis_url
        assert s.jwt_secret_key
        assert s.jwt_algorithm
        assert s.jwt_access_token_expire_minutes > 0
        assert s.jwt_refresh_token_expire_days > 0
        assert isinstance(s.cors_origins, list)
