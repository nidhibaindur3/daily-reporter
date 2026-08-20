from typing import Protocol

from app.domain.news import NewsQuery, NewsSnapshot


class NewsProviderError(RuntimeError):
    """Raised when a news provider cannot return usable article metadata."""


class NewsProvider(Protocol):
    def fetch(self, query: NewsQuery) -> NewsSnapshot:
        """Retrieve normalized article metadata for the requested categories."""
        ...
