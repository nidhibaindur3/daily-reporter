from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal, Optional

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.domain.market import (
    MarketQuery,
    MarketQuote,
    MarketSession,
    MarketSnapshot,
    MarketStatus,
)
from app.providers.market.base import (
    MarketProviderError,
    MarketProviderRateLimitError,
)


class FinnhubQuoteResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False)

    current_price: Decimal = Field(alias="c", gt=0)
    previous_close: Decimal = Field(alias="pc", gt=0)
    timestamp: int = Field(alias="t", ge=1)


class FinnhubMarketStatusResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    exchange: str
    holiday: Optional[str] = None
    is_open: bool = Field(alias="isOpen")
    session: Optional[Literal["pre-market", "regular", "post-market"]] = None
    timestamp: int = Field(alias="t", ge=1)
    timezone: str


class FinnhubMarketProvider:
    provider_name = "Finnhub"

    def __init__(
        self,
        client: httpx.Client,
        base_url: str,
        api_key: Optional[str],
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._now = now

    def fetch(self, query: MarketQuery) -> MarketSnapshot:
        if not self._api_key:
            raise MarketProviderError("Finnhub API key is not configured")

        quotes: list[MarketQuote] = []
        unavailable_symbols: list[str] = []
        for symbol in query.symbols:
            try:
                quotes.append(self._fetch_quote(symbol))
            except MarketProviderRateLimitError:
                raise
            except MarketProviderError:
                unavailable_symbols.append(symbol)

        if not quotes:
            raise MarketProviderError("Finnhub returned no usable watchlist quotes")

        try:
            market_status = self._fetch_market_status(query.exchange)
        except MarketProviderError:
            market_status = MarketStatus(
                exchange=query.exchange,
                session="unknown",
                label="Status unavailable",
                timezone=None,
                holiday=None,
                observed_at=None,
            )

        return MarketSnapshot(
            quotes=tuple(quotes),
            market_status=market_status,
            unavailable_symbols=tuple(unavailable_symbols),
            provider=self.provider_name,
            retrieved_at=self._now(),
        )

    def _fetch_quote(self, symbol: str) -> MarketQuote:
        try:
            payload = FinnhubQuoteResponse.model_validate(
                self._request_json("/quote", params={"symbol": symbol})
            )
            daily_change = payload.current_price - payload.previous_close
            percentage_change = daily_change / payload.previous_close * Decimal("100")
            observed_at = datetime.fromtimestamp(
                payload.timestamp,
                tz=timezone.utc,
            )
        except MarketProviderRateLimitError:
            raise
        except (ArithmeticError, OSError, TypeError, ValueError) as exc:
            raise MarketProviderError(
                f"Finnhub returned an invalid quote for {symbol}"
            ) from exc

        return MarketQuote(
            symbol=symbol,
            current_price=payload.current_price,
            daily_change=daily_change,
            percentage_change=percentage_change,
            previous_close=payload.previous_close,
            currency="USD",
            observed_at=observed_at,
        )

    def _fetch_market_status(self, exchange: str) -> MarketStatus:
        try:
            payload = FinnhubMarketStatusResponse.model_validate(
                self._request_json(
                    "/stock/market-status",
                    params={"exchange": exchange},
                )
            )
            observed_at = datetime.fromtimestamp(
                payload.timestamp,
                tz=timezone.utc,
            )
        except MarketProviderRateLimitError:
            raise
        except (OSError, TypeError, ValueError) as exc:
            raise MarketProviderError("Finnhub returned invalid market status") from exc

        session, label = self._normalize_session(payload.session, payload.is_open)
        return MarketStatus(
            exchange=payload.exchange,
            session=session,
            label=label,
            timezone=payload.timezone,
            holiday=payload.holiday,
            observed_at=observed_at,
        )

    def _request_json(self, path: str, params: dict[str, Any]) -> object:
        try:
            response = self._client.get(
                self._base_url + path,
                params=params,
                headers={"X-Finnhub-Token": self._api_key or ""},
            )
        except httpx.HTTPError as exc:
            raise MarketProviderError("Finnhub request failed") from exc

        if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
            raise MarketProviderRateLimitError(
                "Finnhub rate limit exceeded",
                retry_after_seconds=self._retry_after_seconds(response),
            )

        try:
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            raise MarketProviderError("Finnhub returned an invalid response") from exc

    @staticmethod
    def _normalize_session(
        session: Optional[str],
        is_open: bool,
    ) -> tuple[MarketSession, str]:
        if session == "pre-market":
            return "pre_market", "Pre-market"
        if session == "post-market":
            return "after_hours", "After-hours"
        if session == "regular" and is_open:
            return "open", "Market open"
        return "closed", "Market closed"

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> Optional[int]:
        value = response.headers.get("Retry-After")
        if value is None or not value.isdigit():
            return None
        return int(value)
