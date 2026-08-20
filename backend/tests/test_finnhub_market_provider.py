from datetime import datetime, timezone
from decimal import Decimal

import httpx
import pytest

from app.domain.market import MarketQuery, parse_watchlist
from app.providers.market.base import (
    MarketProviderError,
    MarketProviderRateLimitError,
)
from app.providers.market.finnhub import FinnhubMarketProvider


def market_query(*symbols: str) -> MarketQuery:
    return MarketQuery(symbols=symbols, exchange="US")


def test_finnhub_maps_mocked_quotes_and_calculates_changes() -> None:
    quote_payloads = {
        "AAPL": {"c": 190.25, "pc": 188, "d": 999, "dp": 999, "t": 1787140800},
        "MSFT": {"c": 510, "pc": 515, "d": 999, "dp": 999, "t": 1787140800},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Finnhub-Token"] == "test-key"
        if request.url.path.endswith("/quote"):
            symbol = request.url.params["symbol"]
            return httpx.Response(200, json=quote_payloads[symbol])
        assert request.url.path.endswith("/stock/market-status")
        assert request.url.params["exchange"] == "US"
        return httpx.Response(
            200,
            json={
                "exchange": "US",
                "holiday": None,
                "isOpen": False,
                "session": "pre-market",
                "t": 1787140800,
                "timezone": "America/New_York",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = FinnhubMarketProvider(
        client=client,
        base_url="https://market.test/api/v1/",
        api_key="test-key",
        now=lambda: datetime(2026, 8, 19, 12, 5, tzinfo=timezone.utc),
    )

    snapshot = provider.fetch(market_query("AAPL", "MSFT"))

    assert snapshot.quotes[0].current_price == Decimal("190.25")
    assert snapshot.quotes[0].previous_close == Decimal("188")
    assert snapshot.quotes[0].daily_change == Decimal("2.25")
    assert snapshot.quotes[0].percentage_change == (
        Decimal("2.25") / Decimal("188") * Decimal("100")
    )
    assert snapshot.quotes[1].daily_change == Decimal("-5")
    assert snapshot.market_status.session == "pre_market"
    assert snapshot.market_status.label == "Pre-market"
    assert snapshot.unavailable_symbols == ()
    assert snapshot.provider == "Finnhub"

    client.close()


def test_finnhub_keeps_valid_quotes_when_one_symbol_is_invalid() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/quote"):
            if request.url.params["symbol"] == "MSFT":
                return httpx.Response(200, json={"c": 0, "pc": 0, "t": 0})
            return httpx.Response(200, json={"c": 190, "pc": 188, "t": 1787140800})
        return httpx.Response(503)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = FinnhubMarketProvider(
        client=client,
        base_url="https://market.test/api/v1",
        api_key="test-key",
    )

    snapshot = provider.fetch(market_query("AAPL", "MSFT"))

    assert [quote.symbol for quote in snapshot.quotes] == ["AAPL"]
    assert snapshot.unavailable_symbols == ("MSFT",)
    assert snapshot.market_status.session == "unknown"

    client.close()


def test_finnhub_converts_rate_limit_response_to_typed_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(429, headers={"Retry-After": "42"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = FinnhubMarketProvider(
        client=client,
        base_url="https://market.test/api/v1",
        api_key="test-key",
    )

    with pytest.raises(MarketProviderRateLimitError) as error:
        provider.fetch(market_query("AAPL"))

    assert error.value.retry_after_seconds == 42
    client.close()


def test_finnhub_fails_without_backend_api_key() -> None:
    provider = FinnhubMarketProvider(
        client=httpx.Client(),
        base_url="https://market.test/api/v1",
        api_key=None,
    )

    with pytest.raises(MarketProviderError):
        provider.fetch(market_query("AAPL"))


def test_parse_watchlist_normalizes_and_deduplicates_symbols() -> None:
    assert parse_watchlist(" aapl, MSFT, aapl , BRK.B ") == (
        "AAPL",
        "MSFT",
        "BRK.B",
    )


@pytest.mark.parametrize("value", ["", "AAPL,$BAD"])
def test_parse_watchlist_rejects_invalid_configuration(value: str) -> None:
    with pytest.raises(ValueError):
        parse_watchlist(value)
