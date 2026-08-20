from dataclasses import dataclass
from typing import Optional

import httpx
from openai import OpenAI

from app.ai.market_intelligence_contracts import MarketIntelligenceModel
from app.ai.openai_market_intelligence import (
    OpenAIMarketIntelligenceModel,
    UnconfiguredMarketIntelligenceModel,
)
from app.core.config import Settings
from app.domain.market import MarketQuery, parse_watchlist
from app.domain.news import NEWS_CATEGORIES, NewsQuery
from app.providers.market.finnhub import FinnhubMarketProvider
from app.providers.news.curated_rss import CuratedRssNewsProvider
from app.services.market import MarketService
from app.services.news import NewsService


@dataclass
class ApplicationRuntime:
    market_service: MarketService
    news_service: NewsService
    market_intelligence_model: MarketIntelligenceModel
    _http_clients: tuple[httpx.Client, ...]
    _openai_client: Optional[OpenAI]

    def close(self) -> None:
        for client in self._http_clients:
            client.close()
        if self._openai_client is not None:
            self._openai_client.close()


def build_runtime(settings: Settings) -> ApplicationRuntime:
    market_http_client = httpx.Client(
        timeout=settings.market_request_timeout_seconds,
        follow_redirects=False,
    )
    news_http_client = httpx.Client(
        timeout=settings.news_request_timeout_seconds,
        follow_redirects=False,
        headers={"User-Agent": "DailyDigest/0.1 research-source-reader"},
    )

    market_api_key = (
        settings.finnhub_api_key.get_secret_value()
        if settings.finnhub_api_key is not None
        else None
    )
    market_service = MarketService(
        provider=FinnhubMarketProvider(
            client=market_http_client,
            base_url=settings.market_api_base_url,
            api_key=market_api_key,
        ),
        query=MarketQuery(
            symbols=parse_watchlist(settings.market_watchlist),
            exchange=settings.market_exchange,
        ),
        cache_ttl_seconds=settings.market_cache_ttl_seconds,
        stale_ttl_seconds=settings.market_stale_ttl_seconds,
    )

    news_service = NewsService(
        provider=CuratedRssNewsProvider(
            client=news_http_client,
            maximum_feed_bytes=settings.news_maximum_feed_bytes,
        ),
        query=NewsQuery(
            categories=NEWS_CATEGORIES,
            articles_per_category=settings.news_articles_per_category,
        ),
        cache_ttl_seconds=settings.news_cache_ttl_seconds,
        stale_ttl_seconds=settings.news_stale_ttl_seconds,
    )

    openai_api_key = (
        settings.openai_api_key.get_secret_value().strip()
        if settings.openai_api_key is not None
        else ""
    )
    openai_client: Optional[OpenAI] = None
    if openai_api_key:
        openai_client = OpenAI(
            api_key=openai_api_key,
            timeout=settings.openai_request_timeout_seconds,
            max_retries=0,
        )
        market_intelligence_model: MarketIntelligenceModel = (
            OpenAIMarketIntelligenceModel(
                client=openai_client,
                model=settings.openai_model,
                max_output_tokens=settings.market_intelligence_max_output_tokens,
                reasoning_effort=settings.openai_reasoning_effort,
                verbosity=settings.openai_verbosity,
            )
        )
    else:
        market_intelligence_model = UnconfiguredMarketIntelligenceModel()

    return ApplicationRuntime(
        market_service=market_service,
        news_service=news_service,
        market_intelligence_model=market_intelligence_model,
        _http_clients=(market_http_client, news_http_client),
        _openai_client=openai_client,
    )
