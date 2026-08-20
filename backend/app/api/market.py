from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_market_service
from app.schemas.market import MarketWatchlistResponse
from app.services.market import (
    MarketRateLimitedError,
    MarketService,
    MarketUnavailableError,
)

router = APIRouter(tags=["market"])


@router.get("/markets/watchlist", response_model=MarketWatchlistResponse)
def get_market_watchlist(
    service: Annotated[MarketService, Depends(get_market_service)],
) -> MarketWatchlistResponse:
    try:
        snapshot = service.get_watchlist()
    except MarketRateLimitedError as exc:
        headers = None
        if exc.retry_after_seconds is not None:
            headers = {"Retry-After": str(exc.retry_after_seconds)}
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="market data rate limit exceeded",
            headers=headers,
        ) from exc
    except MarketUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="market data service unavailable",
        ) from exc

    return MarketWatchlistResponse.from_snapshot(snapshot)
