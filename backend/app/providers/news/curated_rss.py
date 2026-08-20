import calendar
import hashlib
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit

import feedparser
import httpx

from app.domain.news import (
    NewsArticle,
    NewsCategory,
    NewsQualityTier,
    NewsQuery,
    NewsSnapshot,
    NewsSourceMetadata,
    NewsSourceType,
)
from app.providers.news.base import NewsProviderError

_ALLOWED_FEED_CONTENT_TYPES = {
    "application/atom+xml",
    "application/rss+xml",
    "application/xml",
    "text/xml",
}


@dataclass(frozen=True)
class CuratedFeedSource:
    source_id: str
    publisher: str
    homepage_url: str
    feed_url: str
    category: NewsCategory
    source_type: NewsSourceType
    quality_tier: NewsQualityTier
    allowed_article_hosts: tuple[str, ...]

    @property
    def metadata(self) -> NewsSourceMetadata:
        return NewsSourceMetadata(
            source_id=self.source_id,
            homepage_url=self.homepage_url,
            source_type=self.source_type,
            quality_tier=self.quality_tier,
        )


DEFAULT_NEWS_SOURCES: tuple[CuratedFeedSource, ...] = (
    CuratedFeedSource(
        source_id="bbc-world",
        publisher="BBC News",
        homepage_url="https://www.bbc.com/news/world",
        feed_url="https://feeds.bbci.co.uk/news/world/rss.xml",
        category="world",
        source_type="news_organization",
        quality_tier="high_quality_journalism",
        allowed_article_hosts=("bbc.com", "bbc.co.uk"),
    ),
    CuratedFeedSource(
        source_id="npr-world",
        publisher="NPR",
        homepage_url="https://www.npr.org/sections/world/",
        feed_url="https://feeds.npr.org/1004/rss.xml",
        category="world",
        source_type="news_organization",
        quality_tier="high_quality_journalism",
        allowed_article_hosts=("npr.org",),
    ),
    CuratedFeedSource(
        source_id="bbc-technology",
        publisher="BBC News",
        homepage_url="https://www.bbc.com/news/technology",
        feed_url="https://feeds.bbci.co.uk/news/technology/rss.xml",
        category="technology",
        source_type="news_organization",
        quality_tier="high_quality_journalism",
        allowed_article_hosts=("bbc.com", "bbc.co.uk"),
    ),
    CuratedFeedSource(
        source_id="ars-technica",
        publisher="Ars Technica",
        homepage_url="https://arstechnica.com/",
        feed_url="https://feeds.arstechnica.com/arstechnica/index",
        category="technology",
        source_type="specialist_publication",
        quality_tier="specialist",
        allowed_article_hosts=("arstechnica.com",),
    ),
    CuratedFeedSource(
        source_id="openai-news",
        publisher="OpenAI",
        homepage_url="https://openai.com/news/",
        feed_url="https://openai.com/news/rss.xml",
        category="ai",
        source_type="company_newsroom",
        quality_tier="primary",
        allowed_article_hosts=("openai.com",),
    ),
    CuratedFeedSource(
        source_id="google-deepmind",
        publisher="Google DeepMind",
        homepage_url="https://deepmind.google/blog/",
        feed_url="https://deepmind.google/blog/rss.xml",
        category="ai",
        source_type="company_newsroom",
        quality_tier="primary",
        allowed_article_hosts=("deepmind.google",),
    ),
    CuratedFeedSource(
        source_id="mit-technology-review-ai",
        publisher="MIT Technology Review",
        homepage_url=(
            "https://www.technologyreview.com/topic/artificial-intelligence/"
        ),
        feed_url=(
            "https://www.technologyreview.com/topic/artificial-intelligence/feed"
        ),
        category="ai",
        source_type="specialist_publication",
        quality_tier="specialist",
        allowed_article_hosts=("technologyreview.com",),
    ),
    CuratedFeedSource(
        source_id="github-engineering",
        publisher="GitHub Engineering",
        homepage_url="https://github.blog/engineering/",
        feed_url="https://github.blog/engineering/feed/",
        category="software_engineering",
        source_type="engineering_blog",
        quality_tier="primary",
        allowed_article_hosts=("github.blog",),
    ),
    CuratedFeedSource(
        source_id="martin-fowler",
        publisher="Martin Fowler",
        homepage_url="https://martinfowler.com/",
        feed_url="https://martinfowler.com/feed.atom",
        category="software_engineering",
        source_type="expert_publication",
        quality_tier="specialist",
        allowed_article_hosts=("martinfowler.com",),
    ),
)


class _PlainTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, Optional[str]]],
    ) -> None:
        del attrs
        if tag.lower() in {"script", "style"}:
            self._ignored_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._ignored_depth > 0:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._ignored_depth == 0:
            self.parts.append(data)


class CuratedRssNewsProvider:
    provider_name = "Curated publisher feeds"

    def __init__(
        self,
        client: httpx.Client,
        sources: tuple[CuratedFeedSource, ...] = DEFAULT_NEWS_SOURCES,
        maximum_feed_bytes: int = 1_000_000,
        maximum_description_characters: int = 320,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._client = client
        self._sources = sources
        self._maximum_feed_bytes = maximum_feed_bytes
        self._maximum_description_characters = maximum_description_characters
        self._now = now
        self._validate_catalog()

    def fetch(self, query: NewsQuery) -> NewsSnapshot:
        requested_categories = set(query.categories)
        articles: list[NewsArticle] = []
        unavailable_sources: list[str] = []

        for source in self._sources:
            if source.category not in requested_categories:
                continue
            try:
                articles.extend(self._fetch_source(source))
            except NewsProviderError:
                unavailable_sources.append(source.publisher)

        selected_articles = self._deduplicate_and_limit(
            articles,
            query.articles_per_category,
        )
        if not selected_articles:
            raise NewsProviderError("curated feeds returned no usable articles")

        return NewsSnapshot(
            articles=selected_articles,
            unavailable_sources=tuple(dict.fromkeys(unavailable_sources)),
            provider=self.provider_name,
            retrieved_at=self._now(),
        )

    def _fetch_source(self, source: CuratedFeedSource) -> tuple[NewsArticle, ...]:
        content = self._download_feed(source.feed_url)
        parsed = feedparser.parse(content)
        entries: list[Mapping[str, Any]] = list(parsed.entries)
        if parsed.bozo and not entries:
            raise NewsProviderError(f"{source.source_id} returned malformed XML")

        articles = tuple(
            article
            for entry in entries
            if (article := self._parse_entry(entry, source)) is not None
        )
        if not articles:
            raise NewsProviderError(f"{source.source_id} returned no valid entries")
        return articles

    def _download_feed(self, url: str) -> bytes:
        try:
            with self._client.stream("GET", url) as response:
                response.raise_for_status()
                content_type = response.headers.get("Content-Type", "")
                media_type = content_type.split(";", maxsplit=1)[0].lower().strip()
                if media_type not in _ALLOWED_FEED_CONTENT_TYPES:
                    raise NewsProviderError("feed has an unsupported content type")

                declared_length = response.headers.get("Content-Length")
                if (
                    declared_length is not None
                    and declared_length.isdigit()
                    and int(declared_length) > self._maximum_feed_bytes
                ):
                    raise NewsProviderError("feed exceeds the configured size limit")

                chunks: list[bytes] = []
                total_bytes = 0
                for chunk in response.iter_bytes():
                    total_bytes += len(chunk)
                    if total_bytes > self._maximum_feed_bytes:
                        raise NewsProviderError(
                            "feed exceeds the configured size limit"
                        )
                    chunks.append(chunk)
        except NewsProviderError:
            raise
        except httpx.HTTPError as exc:
            raise NewsProviderError("feed request failed") from exc

        return b"".join(chunks)

    def _parse_entry(
        self,
        entry: Mapping[str, Any],
        source: CuratedFeedSource,
    ) -> Optional[NewsArticle]:
        title = self._plain_text(str(entry.get("title", "")))
        description = self._entry_description(entry)
        url = str(entry.get("link", "")).strip()
        published_at = self._entry_publication_time(entry)
        if (
            not title
            or not description
            or published_at is None
            or not self._is_allowed_article_url(url, source.allowed_article_hosts)
        ):
            return None

        article_key = f"{source.source_id}\0{url}".encode()
        article_id = hashlib.sha256(article_key).hexdigest()[:24]
        return NewsArticle(
            article_id=article_id,
            title=title,
            publisher=source.publisher,
            url=url,
            published_at=published_at,
            category=source.category,
            description=self._truncate(
                description,
                self._maximum_description_characters,
            ),
            source=source.metadata,
        )

    def _entry_description(self, entry: Mapping[str, Any]) -> str:
        raw_description = entry.get("summary") or entry.get("description")
        if not raw_description:
            content = entry.get("content")
            if isinstance(content, list) and content:
                first = content[0]
                if isinstance(first, Mapping):
                    raw_description = first.get("value")
        return self._plain_text(str(raw_description or ""))

    @staticmethod
    def _entry_publication_time(
        entry: Mapping[str, Any],
    ) -> Optional[datetime]:
        parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
        if not isinstance(parsed_time, tuple) or len(parsed_time) < 6:
            return None
        try:
            timestamp = calendar.timegm(parsed_time)
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (OSError, OverflowError, TypeError, ValueError):
            return None

    @staticmethod
    def _plain_text(value: str) -> str:
        parser = _PlainTextExtractor()
        try:
            parser.feed(value)
            parser.close()
        except (AssertionError, ValueError):
            return ""
        text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
        return re.sub(r"\s+([,.;:!?])", r"\1", text)

    @staticmethod
    def _truncate(value: str, maximum_characters: int) -> str:
        if len(value) <= maximum_characters:
            return value
        shortened = value[: maximum_characters + 1].rsplit(" ", maxsplit=1)[0]
        if not shortened:
            shortened = value[:maximum_characters]
        return shortened.rstrip(" ,.;:-") + "…"

    @staticmethod
    def _is_allowed_article_url(
        value: str,
        allowed_hosts: tuple[str, ...],
    ) -> bool:
        try:
            parsed = urlsplit(value)
        except ValueError:
            return False
        if parsed.scheme != "https" or parsed.hostname is None:
            return False
        hostname = parsed.hostname.lower().rstrip(".")
        return any(
            hostname == host or hostname.endswith("." + host) for host in allowed_hosts
        )

    @classmethod
    def _deduplicate_and_limit(
        cls,
        articles: list[NewsArticle],
        articles_per_category: int,
    ) -> tuple[NewsArticle, ...]:
        deduplicated: list[NewsArticle] = []
        seen_urls: set[str] = set()
        for article in sorted(
            articles,
            key=lambda item: item.published_at,
            reverse=True,
        ):
            canonical_url = cls._canonical_url(article.url)
            if canonical_url in seen_urls:
                continue
            deduplicated.append(article)
            seen_urls.add(canonical_url)

        selected: list[NewsArticle] = []
        per_source_soft_cap = max(1, (articles_per_category + 1) // 2)
        categories = tuple(dict.fromkeys(article.category for article in deduplicated))
        for category in categories:
            category_articles = [
                article for article in deduplicated if article.category == category
            ]
            preferred: list[NewsArticle] = []
            deferred: list[NewsArticle] = []
            source_counts: dict[str, int] = {}
            for article in category_articles:
                count = source_counts.get(article.source.source_id, 0)
                if count < per_source_soft_cap:
                    preferred.append(article)
                    source_counts[article.source.source_id] = count + 1
                else:
                    deferred.append(article)

            category_selection = preferred[:articles_per_category]
            if len(category_selection) < articles_per_category:
                remaining = articles_per_category - len(category_selection)
                category_selection.extend(deferred[:remaining])
            selected.extend(category_selection)

        return tuple(
            sorted(
                selected,
                key=lambda item: item.published_at,
                reverse=True,
            )
        )

    @staticmethod
    def _canonical_url(value: str) -> str:
        parsed = urlsplit(value)
        return urlunsplit(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                parsed.path,
                parsed.query,
                "",
            )
        )

    def _validate_catalog(self) -> None:
        source_ids = [source.source_id for source in self._sources]
        if not self._sources or len(source_ids) != len(set(source_ids)):
            raise ValueError("news source catalog must contain unique sources")
        for source in self._sources:
            feed_url = urlsplit(source.feed_url)
            homepage_url = urlsplit(source.homepage_url)
            if (
                feed_url.scheme != "https"
                or feed_url.hostname is None
                or homepage_url.scheme != "https"
                or homepage_url.hostname is None
                or not source.allowed_article_hosts
            ):
                raise ValueError("news source catalog contains an unsafe URL")
