from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from app.api.dependencies import get_market_service
from app.domain.market import (
    MarketQuote,
    MarketSnapshot,
    MarketStatus,
)
from app.main import app
from app.services.market import MarketRateLimitedError, MarketUnavailableError


def market_snapshot() -> MarketSnapshot:
    timestamp = datetime(2026, 8, 19, 19, tzinfo=timezone.utc)
    return MarketSnapshot(
        quotes=(
            MarketQuote(
                symbol="AAPL",
                current_price=Decimal("190.25"),
                daily_change=Decimal("2.25"),
                percentage_change=Decimal("1.1968"),
                previous_close=Decimal("188"),
                currency="USD",
                observed_at=timestamp,
            ),
        ),
        market_status=MarketStatus(
            exchange="US",
            session="open",
            label="Market open",
            timezone="America/New_York",
            holiday=None,
            observed_at=timestamp,
        ),
        unavailable_symbols=("MSFT",),
        provider="Mock Market",
        retrieved_at=timestamp,
    )


class SuccessfulMarketService:
    def get_watchlist(self) -> MarketSnapshot:
        return market_snapshot()


class FailedMarketService:
    def get_watchlist(self) -> MarketSnapshot:
        raise MarketUnavailableError("provider failed")


class RateLimitedMarketService:
    def get_watchlist(self) -> MarketSnapshot:
        raise MarketRateLimitedError(45)


def test_market_endpoint_returns_structured_watchlist() -> None:
    app.dependency_overrides[get_market_service] = SuccessfulMarketService

    try:
        response = TestClient(app).get("/api/markets/watchlist")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["quotes"][0] == {
        "symbol": "AAPL",
        "current_price": 190.25,
        "daily_change": 2.25,
        "percentage_change": 1.1968,
        "previous_close": 188.0,
        "currency": "USD",
        "observed_at": "2026-08-19T19:00:00Z",
    }
    assert payload["market_status"]["session"] == "open"
    assert payload["unavailable_symbols"] == ["MSFT"]
    assert payload["cache_status"] == "live"


def test_market_endpoint_handles_provider_failure() -> None:
    app.dependency_overrides[get_market_service] = FailedMarketService

    try:
        response = TestClient(app).get("/api/markets/watchlist")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "market data service unavailable"}


def test_market_endpoint_handles_rate_limit() -> None:
    app.dependency_overrides[get_market_service] = RateLimitedMarketService

    try:
        response = TestClient(app).get("/api/markets/watchlist")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "45"
    assert response.json() == {"detail": "market data rate limit exceeded"}
