from collections.abc import Callable
from dataclasses import dataclass, replace
from threading import Lock
from time import monotonic
from typing import Optional

from app.domain.market import MarketQuery, MarketSnapshot
from app.providers.market.base import (
    MarketProvider,
    MarketProviderError,
    MarketProviderRateLimitError,
)


class MarketUnavailableError(RuntimeError):
    """Raised when neither live nor safely cached market data is available."""


class MarketRateLimitedError(MarketUnavailableError):
    """Raised when live market data is rate limited and no stale cache exists."""

    def __init__(self, retry_after_seconds: Optional[int] = None) -> None:
        super().__init__("market-data provider rate limit exceeded")
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True)
class MarketCacheEntry:
    snapshot: MarketSnapshot
    fresh_until: float
    stale_until: float


class MarketService:
    def __init__(
        self,
        provider: MarketProvider,
        query: MarketQuery,
        cache_ttl_seconds: int,
        stale_ttl_seconds: int,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if stale_ttl_seconds < cache_ttl_seconds:
            raise ValueError("stale TTL must be greater than or equal to cache TTL")

        self._provider = provider
        self._query = query
        self._cache_ttl_seconds = cache_ttl_seconds
        self._stale_ttl_seconds = stale_ttl_seconds
        self._clock = clock
        self._entry: Optional[MarketCacheEntry] = None
        self._lock = Lock()

    def get_watchlist(self) -> MarketSnapshot:
        with self._lock:
            now = self._clock()
            if self._entry is not None and now < self._entry.fresh_until:
                return replace(self._entry.snapshot, cache_status="cached")

            try:
                snapshot = self._provider.fetch(self._query)
            except MarketProviderRateLimitError as exc:
                stale = self._stale_snapshot(now)
                if stale is not None:
                    return stale
                raise MarketRateLimitedError(exc.retry_after_seconds) from exc
            except MarketProviderError as exc:
                stale = self._stale_snapshot(now)
                if stale is not None:
                    return stale
                raise MarketUnavailableError(
                    "market-data provider is unavailable"
                ) from exc

            self._entry = MarketCacheEntry(
                snapshot=snapshot,
                fresh_until=now + self._cache_ttl_seconds,
                stale_until=now + self._stale_ttl_seconds,
            )
            return snapshot

    def _stale_snapshot(self, now: float) -> Optional[MarketSnapshot]:
        if self._entry is None or now >= self._entry.stale_until:
            return None
        return replace(self._entry.snapshot, cache_status="stale")
