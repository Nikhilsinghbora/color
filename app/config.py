"""Application configuration using Pydantic Settings."""

from decimal import Decimal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/color_prediction"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Game
    reserve_threshold: Decimal = Decimal("100000.00")

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # Email
    email_provider: str = "sendgrid"
    email_api_key: str = ""
    email_from: str = "noreply@colorprediction.local"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = {"env_prefix": "APP_", "env_file": ".env", "extra": "ignore"}

    @property
    def cors_allowed_origins(self) -> list[str]:
        """Return CORS allowed origins (backward-compatible alias)."""
        return self.cors_origins


settings = Settings()
