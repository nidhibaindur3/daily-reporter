from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.repositories.market_intelligence import MarketIntelligenceRepository
from app.services.market import MarketService
from app.services.market_intelligence import MarketIntelligenceService


def get_market_service(request: Request) -> MarketService:
    service: MarketService = request.app.state.market_service
    return service


def get_market_intelligence_service(
    db: Annotated[Session, Depends(get_db)],
) -> MarketIntelligenceService:
    settings = get_settings()
    api_key = (
        settings.openai_api_key.get_secret_value().strip()
        if settings.openai_api_key is not None
        else ""
    )
    return MarketIntelligenceService(
        repository=MarketIntelligenceRepository(db),
        enabled=bool(api_key),
        maximum_themes_limit=settings.market_intelligence_maximum_themes,
    )
