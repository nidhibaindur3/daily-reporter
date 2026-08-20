import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

MarketSession = Literal[
    "pre_market",
    "open",
    "after_hours",
    "closed",
    "unknown",
]
MarketCacheStatus = Literal["live", "cached", "stale"]

_SYMBOL_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")


def parse_watchlist(value: str, maximum_symbols: int = 20) -> tuple[str, ...]:
    symbols = tuple(
        dict.fromkeys(part.strip().upper() for part in value.split(",") if part.strip())
    )
    if not symbols:
        raise ValueError("market watchlist must contain at least one symbol")
    if len(symbols) > maximum_symbols:
        raise ValueError(f"market watchlist cannot exceed {maximum_symbols} symbols")
    if any(_SYMBOL_PATTERN.fullmatch(symbol) is None for symbol in symbols):
        raise ValueError("market watchlist contains an invalid symbol")
    return symbols


@dataclass(frozen=True)
class MarketQuery:
    symbols: tuple[str, ...]
    exchange: str


@dataclass(frozen=True)
class MarketStatus:
    exchange: str
    session: MarketSession
    label: str
    timezone: Optional[str]
    holiday: Optional[str]
    observed_at: Optional[datetime]


@dataclass(frozen=True)
class MarketQuote:
    symbol: str
    current_price: Decimal
    daily_change: Decimal
    percentage_change: Decimal
    previous_close: Decimal
    currency: str
    observed_at: datetime


@dataclass(frozen=True)
class MarketSnapshot:
    quotes: tuple[MarketQuote, ...]
    market_status: MarketStatus
    unavailable_symbols: tuple[str, ...]
    provider: str
    retrieved_at: datetime
    cache_status: MarketCacheStatus = "live"
