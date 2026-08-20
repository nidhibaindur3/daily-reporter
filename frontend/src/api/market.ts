import { getJson } from './client'

export type MarketSession =
  | 'pre_market'
  | 'open'
  | 'after_hours'
  | 'closed'
  | 'unknown'

export type MarketCacheStatus = 'live' | 'cached' | 'stale'

export type MarketQuote = {
  symbol: string
  current_price: number
  daily_change: number
  percentage_change: number
  previous_close: number
  currency: string
  observed_at: string
}

export type MarketStatus = {
  exchange: string
  session: MarketSession
  label: string
  timezone: string | null
  holiday: string | null
  observed_at: string | null
}

export type MarketWatchlistResponse = {
  quotes: MarketQuote[]
  market_status: MarketStatus
  unavailable_symbols: string[]
  provider: string
  retrieved_at: string
  cache_status: MarketCacheStatus
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string'
}

function isMarketSession(value: unknown): value is MarketSession {
  return (
    value === 'pre_market' ||
    value === 'open' ||
    value === 'after_hours' ||
    value === 'closed' ||
    value === 'unknown'
  )
}

function isMarketQuote(value: unknown): value is MarketQuote {
  return (
    isRecord(value) &&
    typeof value.symbol === 'string' &&
    typeof value.current_price === 'number' &&
    typeof value.daily_change === 'number' &&
    typeof value.percentage_change === 'number' &&
    typeof value.previous_close === 'number' &&
    typeof value.currency === 'string' &&
    typeof value.observed_at === 'string'
  )
}

function isMarketStatus(value: unknown): value is MarketStatus {
  return (
    isRecord(value) &&
    typeof value.exchange === 'string' &&
    isMarketSession(value.session) &&
    typeof value.label === 'string' &&
    isNullableString(value.timezone) &&
    isNullableString(value.holiday) &&
    isNullableString(value.observed_at)
  )
}

function isMarketWatchlistResponse(
  value: unknown,
): value is MarketWatchlistResponse {
  return (
    isRecord(value) &&
    Array.isArray(value.quotes) &&
    value.quotes.length > 0 &&
    value.quotes.every(isMarketQuote) &&
    isMarketStatus(value.market_status) &&
    Array.isArray(value.unavailable_symbols) &&
    value.unavailable_symbols.every((symbol) => typeof symbol === 'string') &&
    typeof value.provider === 'string' &&
    typeof value.retrieved_at === 'string' &&
    (value.cache_status === 'live' ||
      value.cache_status === 'cached' ||
      value.cache_status === 'stale')
  )
}

export async function fetchMarketWatchlist(
  signal: AbortSignal,
): Promise<MarketWatchlistResponse> {
  const payload = await getJson('/api/markets/watchlist', signal)
  if (!isMarketWatchlistResponse(payload)) {
    throw new Error('Backend returned an invalid market response')
  }

  return payload
}
