from typing import Optional, Protocol

from app.domain.market import MarketQuery, MarketSnapshot


class MarketProviderError(RuntimeError):
    """Raised when a market-data provider cannot return usable data."""


class MarketProviderRateLimitError(MarketProviderError):
    """Raised when a market-data provider rejects a request for rate limiting."""

    def __init__(
        self,
        message: str,
        retry_after_seconds: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class MarketProvider(Protocol):
    def fetch(self, query: MarketQuery) -> MarketSnapshot:
        """Retrieve normalized quotes and the relevant exchange status."""
        ...
