from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.domain.news import (
    NewsArticle,
    NewsCategory,
    NewsQuery,
    NewsSourceMetadata,
)
from app.providers.news.base import NewsProviderError
from app.providers.news.curated_rss import CuratedFeedSource, CuratedRssNewsProvider

RSS_FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test World</title>
    <item>
      <guid>world-one</guid>
      <title>First &amp; verified story</title>
      <link>https://news.test/articles/one?from=feed#details</link>
      <pubDate>Wed, 19 Aug 2026 12:00:00 GMT</pubDate>
      <description><![CDATA[
        <p>A publisher-provided description with <strong>context</strong>.</p>
        <script>ignore this</script>
      ]]></description>
    </item>
    <item>
      <guid>world-duplicate</guid>
      <title>Duplicate link</title>
      <link>https://news.test/articles/one?from=feed</link>
      <pubDate>Wed, 19 Aug 2026 11:00:00 GMT</pubDate>
      <description>Duplicate should be removed.</description>
    </item>
  </channel>
</rss>
"""

ATOM_FEED = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Test Engineering</title>
  <entry>
    <id>engineering-one</id>
    <title>How the system was built</title>
    <link href="https://engineering.test/posts/system" />
    <updated>2026-08-19T13:00:00Z</updated>
    <summary type="html">A detailed engineering write-up.</summary>
  </entry>
</feed>
"""


def source(
    *,
    source_id: str = "test-world",
    publisher: str = "Test News",
    feed_url: str = "https://feeds.test/world.xml",
    category: NewsCategory = "world",
    allowed_host: str = "news.test",
) -> CuratedFeedSource:
    return CuratedFeedSource(
        source_id=source_id,
        publisher=publisher,
        homepage_url=f"https://{allowed_host}/",
        feed_url=feed_url,
        category=category,
        source_type="news_organization",
        quality_tier="high_quality_journalism",
        allowed_article_hosts=(allowed_host,),
    )


def test_curated_rss_maps_rss_and_atom_metadata() -> None:
    sources = (
        source(),
        source(
            source_id="test-engineering",
            publisher="Test Engineering",
            feed_url="https://feeds.test/engineering.atom",
            category="software_engineering",
            allowed_host="engineering.test",
        ),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(".atom"):
            return httpx.Response(
                200,
                content=ATOM_FEED,
                headers={"Content-Type": "application/atom+xml"},
            )
        return httpx.Response(
            200,
            content=RSS_FEED,
            headers={"Content-Type": "application/rss+xml"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = CuratedRssNewsProvider(
        client=client,
        sources=sources,
        now=lambda: datetime(2026, 8, 19, 14, tzinfo=timezone.utc),
    )

    snapshot = provider.fetch(
        NewsQuery(
            categories=("world", "software_engineering"),
            articles_per_category=5,
        )
    )

    assert [article.category for article in snapshot.articles] == [
        "software_engineering",
        "world",
    ]
    world_article = snapshot.articles[1]
    assert world_article.title == "First & verified story"
    assert world_article.description == "A publisher-provided description with context."
    assert world_article.url == ("https://news.test/articles/one?from=feed#details")
    assert world_article.published_at == datetime(
        2026,
        8,
        19,
        12,
        tzinfo=timezone.utc,
    )
    assert world_article.source.source_id == "test-world"
    assert world_article.source.quality_tier == "high_quality_journalism"
    assert len(snapshot.articles) == 2
    assert snapshot.unavailable_sources == ()

    client.close()


def test_curated_rss_returns_partial_result_when_one_feed_fails() -> None:
    sources = (
        source(),
        source(
            source_id="failed-source",
            publisher="Failed Publisher",
            feed_url="https://feeds.test/failed.xml",
        ),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("failed.xml"):
            return httpx.Response(503)
        return httpx.Response(
            200,
            content=RSS_FEED,
            headers={"Content-Type": "text/xml"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = CuratedRssNewsProvider(client=client, sources=sources)

    snapshot = provider.fetch(NewsQuery(categories=("world",), articles_per_category=5))

    assert len(snapshot.articles) == 1
    assert snapshot.unavailable_sources == ("Failed Publisher",)
    client.close()


def test_curated_rss_rejects_articles_outside_source_allowlist() -> None:
    unsafe_feed = RSS_FEED.replace(b"https://news.test", b"https://evil.test")

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            content=unsafe_feed,
            headers={"Content-Type": "application/rss+xml"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = CuratedRssNewsProvider(client=client, sources=(source(),))

    with pytest.raises(NewsProviderError):
        provider.fetch(NewsQuery(categories=("world",), articles_per_category=5))

    client.close()


def test_curated_rss_rejects_oversized_feed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            content=RSS_FEED,
            headers={"Content-Type": "application/rss+xml"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = CuratedRssNewsProvider(
        client=client,
        sources=(source(),),
        maximum_feed_bytes=50,
    )

    with pytest.raises(NewsProviderError):
        provider.fetch(NewsQuery(categories=("world",), articles_per_category=5))

    client.close()


def test_curated_rss_truncates_publisher_description_without_summarizing() -> None:
    long_description = "word " * 100
    original_description = (
        b"<p>A publisher-provided description with "
        b"<strong>context</strong>.</p>\n        "
        b"<script>ignore this</script>"
    )
    feed = RSS_FEED.replace(
        original_description,
        long_description.encode(),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            content=feed,
            headers={"Content-Type": "text/xml"},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = CuratedRssNewsProvider(
        client=client,
        sources=(source(),),
        maximum_description_characters=60,
    )

    snapshot = provider.fetch(NewsQuery(categories=("world",), articles_per_category=1))

    assert len(snapshot.articles[0].description) <= 61
    assert snapshot.articles[0].description.endswith("…")
    client.close()


def test_news_selection_preserves_source_diversity_then_fills_capacity() -> None:
    published_at = datetime(2026, 8, 19, 20, tzinfo=timezone.utc)

    def article(source_id: str, age_hours: int) -> NewsArticle:
        return NewsArticle(
            article_id=f"{source_id}-{age_hours}",
            title=f"Story {source_id} {age_hours}",
            publisher=source_id,
            url=f"https://{source_id}.test/{age_hours}",
            published_at=published_at - timedelta(hours=age_hours),
            category="ai",
            description="Publisher description.",
            source=NewsSourceMetadata(
                source_id=source_id,
                homepage_url=f"https://{source_id}.test/",
                source_type="specialist_publication",
                quality_tier="specialist",
            ),
        )

    articles = [article("active-source", age) for age in range(5)]
    articles.append(article("second-source", 10))

    selected = CuratedRssNewsProvider._deduplicate_and_limit(articles, 4)

    assert len(selected) == 4
    assert {item.source.source_id for item in selected} == {
        "active-source",
        "second-source",
    }
    assert list(selected) == sorted(
        selected,
        key=lambda item: item.published_at,
        reverse=True,
    )
