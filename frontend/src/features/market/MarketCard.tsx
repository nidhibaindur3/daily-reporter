import { useEffect, useState } from 'react'

import {
  fetchMarketWatchlist,
  type MarketQuote,
  type MarketWatchlistResponse,
} from '../../api/market'

type MarketState =
  | { status: 'loading' }
  | { status: 'ready'; watchlist: MarketWatchlistResponse }
  | { status: 'error' }

function money(value: number, currency: string): string {
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

function signedMoney(value: number, currency: string): string {
  const sign = value > 0 ? '+' : ''
  return sign + money(value, currency)
}

function signedPercent(value: number): string {
  const sign = value > 0 ? '+' : ''
  return sign + value.toFixed(2) + '%'
}

function changeDirection(value: number): 'up' | 'down' | 'flat' {
  if (value > 0) return 'up'
  if (value < 0) return 'down'
  return 'flat'
}

function retrievedTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(value))
}

function QuoteRow({ quote }: { quote: MarketQuote }) {
  const direction = changeDirection(quote.daily_change)

  return (
    <tr>
      <th scope="row">{quote.symbol}</th>
      <td>{money(quote.current_price, quote.currency)}</td>
      <td className={'market-change market-change--' + direction}>
        {signedMoney(quote.daily_change, quote.currency)}
      </td>
      <td className={'market-change market-change--' + direction}>
        {signedPercent(quote.percentage_change)}
      </td>
      <td>{money(quote.previous_close, quote.currency)}</td>
    </tr>
  )
}

export function MarketCard() {
  const [state, setState] = useState<MarketState>({ status: 'loading' })
  const [requestNumber, setRequestNumber] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setState({ status: 'loading' })

    void fetchMarketWatchlist(controller.signal)
      .then((watchlist) => setState({ status: 'ready', watchlist }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
        setState({ status: 'error' })
      })

    return () => controller.abort()
  }, [requestNumber])

  if (state.status === 'loading') {
    return (
      <section className="market-card" aria-busy="true">
        <p className="eyebrow">Markets</p>
        <p className="market-message">Loading watchlist…</p>
      </section>
    )
  }

  if (state.status === 'error') {
    return (
      <section className="market-card" role="status">
        <p className="eyebrow">Markets</p>
        <h2>Market data is temporarily unavailable</h2>
        <p className="market-message">
          Check the backend market-data configuration or try again shortly.
          Other sections are still available.
        </p>
        <button
          className="retry-button"
          type="button"
          onClick={() => setRequestNumber((value) => value + 1)}
        >
          Try again
        </button>
      </section>
    )
  }

  const { watchlist } = state
  const cacheLabel =
    watchlist.cache_status === 'stale'
      ? 'Stale prices'
      : watchlist.cache_status === 'cached'
        ? 'Cached briefly'
        : null

  return (
    <section className="market-card">
      <div className="market-card__header">
        <div>
          <p className="eyebrow">Markets</p>
          <h2>Personal watchlist</h2>
        </div>
        <div className="market-badges">
          <span
            className={
              'market-session market-session--' +
              watchlist.market_status.session
            }
          >
            {watchlist.market_status.label}
          </span>
          {cacheLabel !== null && (
            <span className="stale-badge">{cacheLabel}</span>
          )}
        </div>
      </div>

      {watchlist.market_status.holiday !== null && (
        <p className="market-holiday">{watchlist.market_status.holiday}</p>
      )}

      <div className="market-table-wrapper">
        <table className="market-table">
          <caption className="visually-hidden">
            Current prices and daily changes for configured watchlist symbols
          </caption>
          <thead>
            <tr>
              <th scope="col">Symbol</th>
              <th scope="col">Price</th>
              <th scope="col">Change</th>
              <th scope="col">Change %</th>
              <th scope="col">Previous close</th>
            </tr>
          </thead>
          <tbody>
            {watchlist.quotes.map((quote) => (
              <QuoteRow key={quote.symbol} quote={quote} />
            ))}
          </tbody>
        </table>
      </div>

      {watchlist.unavailable_symbols.length > 0 && (
        <p className="market-warning">
          Temporarily unavailable:{' '}
          {watchlist.unavailable_symbols.join(', ')}
        </p>
      )}

      <p className="market-source">
        Data by {watchlist.provider}
        {' · '}
        Retrieved {retrievedTime(watchlist.retrieved_at)}
      </p>
    </section>
  )
}
