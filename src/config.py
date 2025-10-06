"""
Configuration management using Pydantic Settings.
Loads from environment variables and .env file.
"""

from typing import Literal, Optional

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ========================================================================
    # Database
    # ========================================================================
    database_url: PostgresDsn = Field(
        default="postgresql://postgres:postgres@localhost:5432/vc_agents",
        description="PostgreSQL connection string",
    )

    # ========================================================================
    # LLM API Keys
    # ========================================================================
    openai_api_key: Optional[str] = Field(
        default=None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(
        default=None, description="Anthropic API key")

    # ========================================================================
    # External APIs
    # ========================================================================
    neynar_api_key: Optional[str] = Field(
        default=None, description="Neynar (Farcaster) API key")
    twitter_api_key: Optional[str] = Field(default=None)
    twitter_api_secret: Optional[str] = Field(default=None)
    twitter_bearer_token: Optional[str] = Field(default=None)
    defillama_api_key: Optional[str] = Field(default=None)

    # ========================================================================
    # Redis (Optional)
    # ========================================================================
    redis_url: Optional[RedisDsn] = Field(
        default=None,
        description="Redis URL for caching and rate limiting",
    )

    # ========================================================================
    # Application Settings
    # ========================================================================
    environment: Literal["development", "staging", "production"] = Field(
        default="development"
    )

    # Rate limiting
    rate_limit_enabled: bool = Field(default=True)
    max_requests_per_hour: int = Field(default=100)

    # Crawler settings
    crawler_user_agent: str = Field(
        default="VC-Agents-Bot/1.0 (+https://example.com/bot)"
    )
    crawler_respect_robots_txt: bool = Field(default=True)
    crawler_max_concurrent: int = Field(default=5, ge=1, le=20)
    crawler_request_delay_ms: int = Field(default=1000, ge=100)

    # Screenshot storage
    screenshot_storage: Literal["local", "s3", "gcs"] = Field(default="local")
    screenshot_path: str = Field(default="./data/screenshots")

    # S3 Configuration
    aws_access_key_id: Optional[str] = Field(default=None)
    aws_secret_access_key: Optional[str] = Field(default=None)
    aws_s3_bucket: Optional[str] = Field(default=None)
    aws_region: str = Field(default="us-east-1")

    # ========================================================================
    # Monitoring & Logging
    # ========================================================================
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO"
    )
    sentry_dsn: Optional[str] = Field(default=None)

    # ========================================================================
    # Agent Configuration
    # ========================================================================
    deals_lookback_days: int = Field(default=90, ge=1, le=365)
    enrichment_min_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    recrawl_after_days: int = Field(default=30, ge=1)

    # ========================================================================
    # LangGraph Settings
    # ========================================================================
    langgraph_checkpointer: Literal["postgres", "memory", "redis"] = Field(
        default="postgres"
    )
    langgraph_max_iterations: int = Field(default=10, ge=1, le=100)
    langgraph_timeout_seconds: int = Field(default=300, ge=30)

    # ========================================================================
    # Validators
    # ========================================================================
    @field_validator("database_url", mode="before")
    @classmethod
    def validate_database_url(cls, v):
        if isinstance(v, str):
            return v
        return str(v)

    @field_validator("redis_url", mode="before")
    @classmethod
    def validate_redis_url(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, str):
            return v
        return str(v)

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"

    @property
    def has_twitter_api(self) -> bool:
        """Check if Twitter API credentials are available."""
        return bool(self.twitter_bearer_token or (self.twitter_api_key and self.twitter_api_secret))

    @property
    def has_farcaster_api(self) -> bool:
        """Check if Farcaster API credentials are available."""
        return bool(self.neynar_api_key)


# Global settings instance
settings = Settings()


# Convenience function for accessing settings
def get_settings() -> Settings:
    """Get application settings."""
    return settings
