from dataclasses import dataclass
from datetime import datetime
from typing import Literal

NewsCategory = Literal["world", "technology", "ai", "software_engineering"]
NewsSourceType = Literal[
    "news_organization",
    "specialist_publication",
    "company_newsroom",
    "engineering_blog",
    "expert_publication",
]
NewsQualityTier = Literal["primary", "high_quality_journalism", "specialist"]
NewsCacheStatus = Literal["live", "cached", "stale"]

NEWS_CATEGORIES: tuple[NewsCategory, ...] = (
    "world",
    "technology",
    "ai",
    "software_engineering",
)


@dataclass(frozen=True)
class NewsQuery:
    categories: tuple[NewsCategory, ...]
    articles_per_category: int


@dataclass(frozen=True)
class NewsSourceMetadata:
    source_id: str
    homepage_url: str
    source_type: NewsSourceType
    quality_tier: NewsQualityTier


@dataclass(frozen=True)
class NewsArticle:
    article_id: str
    title: str
    publisher: str
    url: str
    published_at: datetime
    category: NewsCategory
    description: str
    source: NewsSourceMetadata


@dataclass(frozen=True)
class NewsSnapshot:
    articles: tuple[NewsArticle, ...]
    unavailable_sources: tuple[str, ...]
    provider: str
    retrieved_at: datetime
    cache_status: NewsCacheStatus = "live"
