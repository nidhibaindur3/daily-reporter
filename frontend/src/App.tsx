import { useEffect, useState } from 'react'

import { fetchHealth } from './api/health'
import { MarketCard } from './features/market/MarketCard'
import { MarketIntelligenceSection } from './features/marketIntelligence/MarketIntelligenceSection'

type BackendState = 'checking' | 'ok' | 'unavailable'

function App() {
  const [backendState, setBackendState] =
    useState<BackendState>('checking')

  useEffect(() => {
    const controller = new AbortController()

    void fetchHealth(controller.signal)
      .then((health) => setBackendState(health.status))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
        setBackendState('unavailable')
      })

    return () => controller.abort()
  }, [])

  return (
    <main className="page">
      <header className="app-header">
        <div>
          <p className="eyebrow">Daily Digest</p>
          <h1>Hey Nidhi</h1>
        </div>
        <div className="backend-status" aria-live="polite">
          <span>Backend</span>
          <span className={'status status--' + backendState}>
            {backendState}
          </span>
        </div>
      </header>

      <section className="dashboard-grid">
        <MarketIntelligenceSection />
        <MarketCard />
      </section>

      {backendState === 'unavailable' && (
        <section className="service-notice" role="status">
          <h2>Backend service unavailable</h2>
          <p className="description">
            Check that FastAPI and PostgreSQL are running, then reload this page.
          </p>
        </section>
      )}
    </main>
  )
}

export default App
