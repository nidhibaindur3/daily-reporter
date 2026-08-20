from functools import lru_cache
from pathlib import Path
from typing import Literal, Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    app_env: Literal["development", "test", "production"] = "development"
    frontend_origin: str = "http://localhost:5173"
    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    market_watchlist: str = "AAPL,MSFT,NVDA,GOOGL,AMZN"
    market_exchange: Literal["US"] = "US"
    market_api_base_url: str = "https://finnhub.io/api/v1"
    finnhub_api_key: Optional[SecretStr] = None
    market_request_timeout_seconds: float = Field(default=5, gt=0, le=30)
    market_cache_ttl_seconds: int = Field(default=300, ge=30, le=3600)
    market_stale_ttl_seconds: int = Field(default=1800, ge=60, le=86400)
    news_articles_per_category: int = Field(default=6, ge=1, le=12)
    news_request_timeout_seconds: float = Field(default=8, gt=0, le=30)
    news_maximum_feed_bytes: int = Field(
        default=1_000_000,
        ge=65_536,
        le=5_000_000,
    )
    news_cache_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    news_stale_ttl_seconds: int = Field(default=10_800, ge=300, le=86400)
    openai_api_key: Optional[SecretStr] = None
    openai_model: str = Field(default="gpt-5-mini", min_length=1, max_length=100)
    openai_request_timeout_seconds: float = Field(default=60, gt=0, le=120)
    openai_reasoning_effort: Literal["minimal", "low", "medium", "high"] = "minimal"
    openai_verbosity: Literal["low", "medium", "high"] = "low"
    market_intelligence_source_limit: int = Field(default=24, ge=6, le=50)
    market_intelligence_maximum_themes: int = Field(default=3, ge=1, le=5)
    market_intelligence_max_output_tokens: int = Field(default=4500, ge=1000, le=12000)
    market_intelligence_worker_poll_seconds: float = Field(default=5, ge=0.25, le=60)
    market_intelligence_job_lease_seconds: int = Field(default=600, ge=60, le=3600)
    market_intelligence_job_retry_seconds: int = Field(default=30, ge=1, le=600)

    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> URL:
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
