from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

from app.domain.market import MarketSnapshot


class MarketQuoteResponse(BaseModel):
    symbol: str
    current_price: float
    daily_change: float
    percentage_change: float
    previous_close: float
    currency: str
    observed_at: datetime


class MarketStatusResponse(BaseModel):
    exchange: str
    session: Literal[
        "pre_market",
        "open",
        "after_hours",
        "closed",
        "unknown",
    ]
    label: str
    timezone: Optional[str]
    holiday: Optional[str]
    observed_at: Optional[datetime]


class MarketWatchlistResponse(BaseModel):
    quotes: list[MarketQuoteResponse]
    market_status: MarketStatusResponse
    unavailable_symbols: list[str]
    provider: str
    retrieved_at: datetime
    cache_status: Literal["live", "cached", "stale"]

    @classmethod
    def from_snapshot(cls, snapshot: MarketSnapshot) -> "MarketWatchlistResponse":
        return cls(
            quotes=[
                MarketQuoteResponse(
                    symbol=quote.symbol,
                    current_price=float(quote.current_price),
                    daily_change=float(quote.daily_change),
                    percentage_change=float(quote.percentage_change),
                    previous_close=float(quote.previous_close),
                    currency=quote.currency,
                    observed_at=quote.observed_at,
                )
                for quote in snapshot.quotes
            ],
            market_status=MarketStatusResponse(
                exchange=snapshot.market_status.exchange,
                session=snapshot.market_status.session,
                label=snapshot.market_status.label,
                timezone=snapshot.market_status.timezone,
                holiday=snapshot.market_status.holiday,
                observed_at=snapshot.market_status.observed_at,
            ),
            unavailable_symbols=list(snapshot.unavailable_symbols),
            provider=snapshot.provider,
            retrieved_at=snapshot.retrieved_at,
            cache_status=snapshot.cache_status,
        )
