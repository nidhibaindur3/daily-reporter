from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.domain.market import (
    MarketQuery,
    MarketQuote,
    MarketSnapshot,
    MarketStatus,
)
from app.providers.market.base import (
    MarketProviderError,
    MarketProviderRateLimitError,
)
from app.services.market import (
    MarketRateLimitedError,
    MarketService,
    MarketUnavailableError,
)


def market_snapshot() -> MarketSnapshot:
    timestamp = datetime(2026, 8, 19, 19, tzinfo=timezone.utc)
    return MarketSnapshot(
        quotes=(
            MarketQuote(
                symbol="AAPL",
                current_price=Decimal("190.25"),
                daily_change=Decimal("2.25"),
                percentage_change=Decimal("1.196808510638297872340425532"),
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
        unavailable_symbols=(),
        provider="Mock Market",
        retrieved_at=timestamp,
    )


class FakeMarketProvider:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls = 0

    def fetch(self, query: MarketQuery) -> MarketSnapshot:
        del query
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, MarketProviderError):
            raise response
        assert isinstance(response, MarketSnapshot)
        return response


def market_service(
    provider: FakeMarketProvider,
    clock: list[float],
) -> MarketService:
    return MarketService(
        provider=provider,
        query=MarketQuery(symbols=("AAPL",), exchange="US"),
        cache_ttl_seconds=300,
        stale_ttl_seconds=1800,
        clock=lambda: clock[0],
    )


def test_market_service_caches_fresh_watchlist() -> None:
    clock = [100.0]
    provider = FakeMarketProvider([market_snapshot()])
    service = market_service(provider, clock)

    live = service.get_watchlist()
    cached = service.get_watchlist()

    assert live.cache_status == "live"
    assert cached.cache_status == "cached"
    assert provider.calls == 1


def test_market_service_returns_stale_data_on_provider_failure() -> None:
    clock = [100.0]
    provider = FakeMarketProvider(
        [market_snapshot(), MarketProviderError("provider failed")]
    )
    service = market_service(provider, clock)
    service.get_watchlist()

    clock[0] = 401.0
    stale = service.get_watchlist()

    assert stale.cache_status == "stale"
    assert provider.calls == 2


def test_market_service_returns_stale_data_when_rate_limited() -> None:
    clock = [100.0]
    provider = FakeMarketProvider(
        [market_snapshot(), MarketProviderRateLimitError("limited", 60)]
    )
    service = market_service(provider, clock)
    service.get_watchlist()

    clock[0] = 401.0

    assert service.get_watchlist().cache_status == "stale"


def test_market_service_surfaces_rate_limit_without_cache() -> None:
    provider = FakeMarketProvider([MarketProviderRateLimitError("limited", 45)])
    service = market_service(provider, [100.0])

    with pytest.raises(MarketRateLimitedError) as error:
        service.get_watchlist()

    assert error.value.retry_after_seconds == 45


def test_market_service_rejects_provider_failure_without_cache() -> None:
    provider = FakeMarketProvider([MarketProviderError("failed")])
    service = market_service(provider, [100.0])

    with pytest.raises(MarketUnavailableError):
        service.get_watchlist()
