from datetime import datetime, timezone

import pytest

from app.domain.news import (
    NewsArticle,
    NewsQuery,
    NewsSnapshot,
    NewsSourceMetadata,
)
from app.providers.news.base import NewsProviderError
from app.services.news import NewsService, NewsUnavailableError


def news_snapshot() -> NewsSnapshot:
    timestamp = datetime(2026, 8, 19, 19, tzinfo=timezone.utc)
    return NewsSnapshot(
        articles=(
            NewsArticle(
                article_id="article-1",
                title="A sourced story",
                publisher="Test News",
                url="https://news.test/story",
                published_at=timestamp,
                category="world",
                description="A publisher-provided description.",
                source=NewsSourceMetadata(
                    source_id="test-news",
                    homepage_url="https://news.test/",
                    source_type="news_organization",
                    quality_tier="high_quality_journalism",
                ),
            ),
        ),
        unavailable_sources=(),
        provider="Mock News",
        retrieved_at=timestamp,
    )


class FakeNewsProvider:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls = 0

    def fetch(self, query: NewsQuery) -> NewsSnapshot:
        del query
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, NewsProviderError):
            raise response
        assert isinstance(response, NewsSnapshot)
        return response


def news_service(provider: FakeNewsProvider, clock: list[float]) -> NewsService:
    return NewsService(
        provider=provider,
        query=NewsQuery(categories=("world",), articles_per_category=5),
        cache_ttl_seconds=900,
        stale_ttl_seconds=10800,
        clock=lambda: clock[0],
    )


def test_news_service_caches_fresh_response() -> None:
    clock = [100.0]
    provider = FakeNewsProvider([news_snapshot()])
    service = news_service(provider, clock)

    live = service.get_latest()
    cached = service.get_latest()

    assert live.cache_status == "live"
    assert cached.cache_status == "cached"
    assert provider.calls == 1


def test_news_service_returns_stale_news_when_refresh_fails() -> None:
    clock = [100.0]
    provider = FakeNewsProvider([news_snapshot(), NewsProviderError("provider failed")])
    service = news_service(provider, clock)
    service.get_latest()

    clock[0] = 1001.0
    stale = service.get_latest()

    assert stale.cache_status == "stale"
    assert provider.calls == 2


def test_news_service_raises_without_usable_cache() -> None:
    provider = FakeNewsProvider([NewsProviderError("provider failed")])
    service = news_service(provider, [100.0])

    with pytest.raises(NewsUnavailableError):
        service.get_latest()


def test_news_service_does_not_return_expired_stale_cache() -> None:
    clock = [100.0]
    provider = FakeNewsProvider([news_snapshot(), NewsProviderError("provider failed")])
    service = news_service(provider, clock)
    service.get_latest()
    clock[0] = 10901.0

    with pytest.raises(NewsUnavailableError):
        service.get_latest()
