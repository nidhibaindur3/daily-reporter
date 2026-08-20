from collections.abc import Callable
from dataclasses import dataclass, replace
from threading import Lock
from time import monotonic
from typing import Optional

from app.domain.news import NewsQuery, NewsSnapshot
from app.providers.news.base import NewsProvider, NewsProviderError


class NewsUnavailableError(RuntimeError):
    """Raised when neither live nor safely cached news is available."""


@dataclass(frozen=True)
class NewsCacheEntry:
    snapshot: NewsSnapshot
    fresh_until: float
    stale_until: float


class NewsService:
    def __init__(
        self,
        provider: NewsProvider,
        query: NewsQuery,
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
        self._entry: Optional[NewsCacheEntry] = None
        self._lock = Lock()

    def get_latest(self) -> NewsSnapshot:
        with self._lock:
            now = self._clock()
            if self._entry is not None and now < self._entry.fresh_until:
                return replace(self._entry.snapshot, cache_status="cached")

            try:
                snapshot = self._provider.fetch(self._query)
            except NewsProviderError as exc:
                if self._entry is not None and now < self._entry.stale_until:
                    return replace(self._entry.snapshot, cache_status="stale")
                raise NewsUnavailableError("news provider is unavailable") from exc

            self._entry = NewsCacheEntry(
                snapshot=snapshot,
                fresh_until=now + self._cache_ttl_seconds,
                stale_until=now + self._stale_ttl_seconds,
            )
            return snapshot
