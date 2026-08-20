import { useEffect, useRef, useState } from 'react'

import {
  fetchDiscoveryRun,
  fetchResearchOpportunities,
  startDiscoveryRun,
  type CitedStatement,
  type OpportunitySource,
  type ResearchOpportunity,
} from '../../api/marketIntelligence'

type ViewState =
  | { status: 'loading-latest' }
  | { status: 'idle' }
  | { status: 'running'; stage: string }
  | {
      status: 'ready'
      opportunities: ResearchOpportunity[]
      notice?: string
    }
  | { status: 'error'; message: string }

const stageLabels: Record<string, string> = {
  sources: 'Collecting current sources',
  claims: 'Extracting source-bound claims',
  signals: 'Detecting cross-source signals',
  themes: 'Connecting signals into themes',
  evidence: 'Checking the evidence ledger',
  contradictions: 'Actively looking for contradictions',
  theses: 'Forming research hypotheses',
  opportunities: 'Prioritizing what to investigate',
}

function wait(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timeout = window.setTimeout(resolve, milliseconds)
    signal.addEventListener(
      'abort',
      () => {
        window.clearTimeout(timeout)
        reject(new DOMException('Aborted', 'AbortError'))
      },
      { once: true },
    )
  })
}

function failureGuidance(message: string): string {
  if (message === 'claim_output_invalid') {
    return 'The model response failed source-grounding validation, so no invalid claims were saved. Run discovery again.'
  }
  if (message.includes('model_unavailable')) {
    return 'Check the backend-only model configuration and provider availability, then run discovery again.'
  }
  if (message === 'thesis_output_invalid') {
    return 'The thesis contained a claim that could not be traced to its cited evidence, so no report was saved. Run discovery again.'
  }
  if (message.includes('API request failed')) {
    return 'Check that the backend API is running and reachable from the frontend.'
  }
  if (message.includes('timed out')) {
    return 'The worker is still unavailable or the run exceeded the browser polling window.'
  }
  return 'The run stopped safely without publishing unsupported research. Check the worker logs for the recorded error code.'
}

function failureTitle(message: string): string {
  if (message === 'claim_output_invalid') {
    return 'The research response could not be verified.'
  }
  if (message.includes('model_unavailable')) {
    return 'The research model is unavailable.'
  }
  if (message === 'thesis_output_invalid') {
    return 'The research thesis could not be verified.'
  }
  if (message.includes('API request failed')) {
    return 'Daily Digest could not reach the backend.'
  }
  if (message.includes('timed out')) {
    return 'Research is taking longer than expected.'
  }
  return 'Research discovery could not finish.'
}

function displayLabel(value: string): string {
  return value.replaceAll('_', ' ')
}

function SourceLinks({
  sourceIds,
  sources,
}: {
  sourceIds: string[]
  sources: Map<string, OpportunitySource>
}) {
  const resolvedSources = sourceIds.flatMap((sourceId) => {
    const source = sources.get(sourceId)
    return source ? [{ sourceId, source }] : []
  })
  const articleSources = resolvedSources.filter(
    ({ source }) => source.document_type !== 'market_data',
  )
  const hasMarketData = resolvedSources.some(
    ({ source }) => source.document_type === 'market_data',
  )

  if (articleSources.length === 0 && !hasMarketData) return null

  return (
    <span className="research-citations" aria-label="Evidence sources">
      {articleSources.map(({ sourceId, source }) => {
        return source.url ? (
          <a
            key={sourceId}
            href={source.url}
            target="_blank"
            rel="noreferrer"
            title={`${source.title} · ${source.authority_tier}`}
          >
            {source.publisher}
          </a>
        ) : (
          <span key={sourceId} title={source.title}>
            {source.publisher}
          </span>
        )
      })}
      {hasMarketData && (
        <span
          className="research-citations__market-data"
          title="Deterministic market observation supplied by the backend"
        >
          Market data
        </span>
      )}
    </span>
  )
}

function CitedItem({
  item,
  sources,
}: {
  item: CitedStatement
  sources: Map<string, OpportunitySource>
}) {
  return (
    <div className="research-cited-item">
      <span className={`claim-badge claim-badge--${item.claim_type}`}>
        {item.claim_type.replace('_', ' ')}
      </span>
      <p>{item.text}</p>
      <SourceLinks sourceIds={item.source_ids} sources={sources} />
    </div>
  )
}

function CitedList({
  items,
  sources,
}: {
  items: CitedStatement[]
  sources: Map<string, OpportunitySource>
}) {
  return (
    <div className="research-list">
      {items.map((item, index) => (
        <CitedItem key={`${item.text}-${index}`} item={item} sources={sources} />
      ))}
    </div>
  )
}

function OpportunityCard({ opportunity }: { opportunity: ResearchOpportunity }) {
  const { document } = opportunity
  const investmentLens = document.investment_lens
  const sources = new Map(
    opportunity.sources.map((source) => [source.source_snapshot_id, source]),
  )

  return (
    <article className="research-opportunity">
      <header className="research-opportunity__header">
        <div>
          <p className="eyebrow">Evidence-backed research hypothesis</p>
          <h3>{document.theme.name}</h3>
          <p className="research-theme-description">
            {document.theme.description}
          </p>
        </div>
        <div className="research-scores">
          <span>Priority {document.research_priority.label}</span>
          <span>Confidence {document.confidence.label}</span>
        </div>
      </header>

      <section className="research-lead">
        <h4>What may be happening beneath the surface</h4>
        <CitedItem item={document.summary} sources={sources} />
        <h4>Why now</h4>
        <CitedItem item={document.why_now} sources={sources} />
      </section>

      {investmentLens ? (
        <section className="investment-lens">
          <header className="investment-lens__header">
            <div>
              <p className="eyebrow">Long-term investment lens</p>
              <h4>What deserves deeper investigation?</h4>
            </div>
            <span className="investment-posture">
              {investmentLens.research_posture.replaceAll('_', ' ')}
            </span>
          </header>
          <h5>Long-term relevance</h5>
          <CitedItem
            item={investmentLens.long_term_relevance}
            sources={sources}
          />
          <h5>Why this research posture</h5>
          <CitedItem
            item={investmentLens.posture_rationale}
            sources={sources}
          />
          <h5>What to verify before considering capital deployment</h5>
          <CitedList items={investmentLens.what_to_watch} sources={sources} />
          <div className="capital-context-warning">
            <strong>Buying environment: insufficient data</strong>
            <ul>
              {investmentLens.capital_deployment_limitations.map(
                (limitation) => (
                  <li key={limitation}>{limitation}</li>
                ),
              )}
            </ul>
          </div>
        </section>
      ) : (
        <p className="research-limitation investment-lens-legacy">
          This saved report predates the long-term investment lens. Run a new
          discovery to generate it.
        </p>
      )}

      <details open>
        <summary>Detected signals</summary>
        <div className="research-list">
          {document.detected_signals.map((signal) => (
            <div className="research-cited-item" key={signal.signal_id}>
              <span className="claim-badge claim-badge--signal">signal</span>
              <p>{signal.description}</p>
              <small>
                {signal.independent_source_count} independent sources
              </small>
              <SourceLinks sourceIds={signal.source_ids} sources={sources} />
            </div>
          ))}
        </div>
      </details>

      <div className="research-two-column">
        <details open>
          <summary>Industries to investigate</summary>
          {document.affected_industries.length > 0 ? (
            document.affected_industries.map((area) => (
              <div className="affected-area" key={area.name}>
                <h5>{area.name}</h5>
                <small>{`${displayLabel(area.relationship)} · ${area.direction}`}</small>
                <CitedItem item={area.rationale} sources={sources} />
              </div>
            ))
          ) : (
            <p className="research-limitation">
              This older report did not include an industry suggestion. Run a
              new discovery to generate one.
            </p>
          )}
        </details>
        <details open>
          <summary>Companies to investigate</summary>
          {document.affected_companies.map((area) => (
            <div className="affected-area" key={area.name}>
              <h5>{area.name}</h5>
              <small>{`${displayLabel(area.relationship)} · ${area.direction}`}</small>
              <CitedItem item={area.rationale} sources={sources} />
            </div>
          ))}
        </details>
      </div>

      <details>
        <summary>Preliminary thesis and mechanism</summary>
        <CitedItem item={document.research_thesis} sources={sources} />
        <CitedItem item={document.mechanism} sources={sources} />
      </details>

      <div className="research-two-column">
        <details>
          <summary>Bull case</summary>
          <CitedList items={document.bull_case} sources={sources} />
        </details>
        <details>
          <summary>Bear case</summary>
          <CitedList items={document.bear_case} sources={sources} />
        </details>
      </div>

      <details open>
        <summary>Contradictory evidence</summary>
        {document.contradictory_evidence.length > 0 ? (
          <CitedList
            items={document.contradictory_evidence}
            sources={sources}
          />
        ) : (
          <p className="research-limitation">
            None found in the current closed source set. This is not evidence
            that no contradiction exists; external contradiction search is
            deferred from this MVP.
          </p>
        )}
      </details>

      <div className="research-two-column">
        <details>
          <summary>Risks and invalidation</summary>
          <CitedList items={document.risks} sources={sources} />
          <CitedList
            items={document.invalidation_conditions}
            sources={sources}
          />
        </details>
        <details>
          <summary>Questions worth investigating</summary>
          <CitedList items={document.research_questions} sources={sources} />
        </details>
      </div>

      <footer className="research-opportunity__footer">
        <p>
          {document.source_quality.source_count} sources ·{' '}
          {document.source_quality.independent_source_count} independent ·{' '}
          market awareness{' '}
          {displayLabel(document.market_awareness.awareness_state)} · pricing{' '}
          {displayLabel(document.market_awareness.pricing_state)}
        </p>
        <p>
          Preliminary research only. No buy/sell instruction is generated, and
          crowdedness is not assessed in this MVP.
        </p>
      </footer>
    </article>
  )
}

export function MarketIntelligenceSection() {
  const [state, setState] = useState<ViewState>({ status: 'loading-latest' })
  const controller = useRef<AbortController | null>(null)

  useEffect(() => {
    const initialController = new AbortController()
    controller.current = initialController
    void fetchResearchOpportunities(initialController.signal)
      .then((opportunities) =>
        setState(
          opportunities.length > 0
            ? { status: 'ready', opportunities: opportunities.slice(0, 3) }
            : { status: 'idle' },
        ),
      )
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setState({ status: 'idle' })
      })
    return () => initialController.abort()
  }, [])

  function discover() {
    controller.current?.abort()
    const nextController = new AbortController()
    controller.current = nextController
    setState({ status: 'running', stage: 'sources' })

    void (async () => {
      const started = await startDiscoveryRun(nextController.signal)
      let run = started
      for (let attempt = 0; attempt < 180; attempt += 1) {
        if (run.status === 'complete' || run.status === 'incomplete') {
          const opportunities = await fetchResearchOpportunities(
            nextController.signal,
            run.run_id,
          )
          if (opportunities.length > 0) {
            setState({ status: 'ready', opportunities })
            return
          }
          const previous = await fetchResearchOpportunities(
            nextController.signal,
          )
          setState({
            status: 'ready',
            opportunities: previous.slice(0, 3),
            notice:
              previous.length > 0
                ? 'No new cross-source theme met the evidence threshold in this run. Showing the latest saved research.'
                : 'No cross-source theme met the MVP evidence threshold in this window.',
          })
          return
        }
        if (run.status === 'failed' || run.status === 'cancelled') {
          throw new Error(run.error_code ?? 'Discovery run failed')
        }
        setState({ status: 'running', stage: run.current_stage })
        await wait(2000, nextController.signal)
        run = await fetchDiscoveryRun(run.run_id, nextController.signal)
      }
      throw new Error('Discovery run timed out')
    })().catch((error: unknown) => {
      if (error instanceof DOMException && error.name === 'AbortError') return
      setState({
        status: 'error',
        message: error instanceof Error ? error.message : 'Discovery failed',
      })
    })
  }

  const opportunities = state.status === 'ready' ? state.opportunities : []

  return (
    <section className="market-intelligence">
      <header className="market-intelligence__header">
        <div>
          <h2>What is happening today?</h2>
          <p>
            Looks at recent news and market data to suggest industries and
            companies worth researching.
          </p>
        </div>
        <button
          className="research-button"
          type="button"
          onClick={discover}
          disabled={state.status === 'running'}
        >
          {state.status === 'running' ? 'Discovery running…' : 'Run discovery'}
        </button>
      </header>

      {state.status === 'loading-latest' && (
        <p className="research-status">Loading previous research…</p>
      )}
      {state.status === 'idle' && (
        <p className="research-status">
          Run discovery to look for evidence-backed patterns across the latest
          research sources and market data.
        </p>
      )}
      {state.status === 'running' && (
        <div className="research-progress" aria-live="polite">
          <span className="research-progress__dot" />
          <p>{stageLabels[state.stage] ?? 'Processing the research pipeline'}</p>
        </div>
      )}
      {state.status === 'error' && (
        <div className="research-error" role="status">
          <p>{failureTitle(state.message)}</p>
          <p>{failureGuidance(state.message)}</p>
        </div>
      )}
      {state.status === 'ready' && state.notice && (
        <p className="research-status">{state.notice}</p>
      )}
      <div className="research-opportunity-list">
        {opportunities.map((opportunity) => (
          <OpportunityCard
            key={opportunity.opportunity_id}
            opportunity={opportunity}
          />
        ))}
      </div>
    </section>
  )
}
