# Development roadmap

**Status:** Milestone 3 and a Render deployment baseline are available.
Milestone 4 is next.

## At a glance

| Phase | Outcome | Status |
| --- | --- | --- |
| 1. Foundation | Runnable frontend, backend, database, and CI | Complete |
| 2. Market watchlist | Deterministic current data for configured companies | Initial slice complete |
| 3. Research Discovery | Evidence-backed cross-source research leads | Initial slice complete |
| 4. Market context | Explain the broader market environment | Next |
| 5. Authoritative sources | Add filings, company sources, and wider discovery | Planned |
| 6. Deep research | Investigate a user-selected question | Planned |
| 7. Persistent knowledge | Add saved knowledge and RAG | Planned |
| 8. Awareness and personalization | Assess attention, crowdedness, and relevance | Planned |
| 9. Operations | Deploy, schedule, secure, and monitor | In progress |

## Delivery principles

- Build one trustworthy vertical slice at a time.
- Preserve provenance before expanding source breadth.
- Keep the workflow modular and application-owned.
- Use deterministic code for data, calculations, state, and validation.
- Add tests and evaluations with each capability.
- Do not expand the product into a general news, weather, or daily-brief app.

## Available milestones

### 1. Foundation

- React, TypeScript, and Vite frontend
- FastAPI backend
- PostgreSQL with pgvector available for later use
- Docker Compose, migrations, and GitHub Actions
- Environment configuration and health checks

### 2. Market watchlist

- Configurable symbols
- Typed market-provider abstraction
- Deterministic daily and percentage changes
- Market-session status
- Fresh and bounded-stale caching
- Rate-limit and partial-failure behavior

Persisted watchlist management, additional asset types, and a final licensed
provider choice remain future work.

### 3. Research Discovery

- Sources-to-opportunity pipeline with durable stages
- Source snapshots, claims, dependencies, and evidence provenance
- Curated publisher feeds and typed watchlist observations
- Four focused structured-output AI stages
- Independent-source and evidence thresholds
- Citation, identifier, numeric, entity, URL, and trading-directive validation
- Contradiction review, deterministic priority, and confidence
- Long-term research posture with explicit limitations
- Dashboard progress, result, empty, incomplete, and failure states

Current opportunities are marked incomplete when wider evidence collection or
external contradiction search is still required.

## Next milestone: market context

The next goal is to explain the current investing environment with sourced,
deterministic observations.

Planned inputs:

- Broad-market and small-cap benchmarks
- Sector performance and relative strength
- Market breadth and volatility
- Interest rates and Treasury yields
- Relevant commodities and currencies
- Observation time, unit, currency, and freshness metadata

The resulting market-environment state must:

- Distinguish watchlist movement from the broader market.
- Show every input and limitation.
- Keep theme quality, valuation, and portfolio fit separate.
- Never turn an environment label into personalized trade advice.

## Later milestones

### 5. Authoritative research sources

Add typed, read-only tools for:

- General web discovery
- Government and regulatory sources
- SEC and company filings
- Company and investor-relations information
- Forum and community discovery
- Controlled document retrieval

Primary or authoritative evidence should replace weaker discovery leads when
available. Forum signals must never be treated as authoritative facts.

### 6. User-selected deep research

Add an explicit question, bounded research plan, required evidence types,
deterministic calculations, follow-up searches, and complete, incomplete,
failed, and cancelled outcomes.

### 7. Persistent knowledge and RAG

Index saved papers, articles, documentation, notes, and previous research in
PostgreSQL full-text search and pgvector. Historical context must remain
separate from live current evidence.

See [RAG and persistent knowledge](rag.md).

### 8. Market awareness and personalization

Measure reporting breadth, community attention, company mentions, and observed
market reaction. Use these inputs to distinguish an interesting underlying
trend from one that may already be widely known or crowded.

Personalization can later include saved opportunities, feedback, watchlist
relationships, and prior research. It must not become automated portfolio
management.

### 9. Operational hardening

Current:

- Render Blueprint for the static frontend, API, background worker, and
  PostgreSQL
- Automatic cross-service URL and internal database wiring
- Alembic migrations before worker deployment and API database health checks

Planned:

- Scheduled runs and job recovery
- Authentication for the private application
- Provider budgets and rate controls
- Cost, latency, and failure monitoring
- Backups and restore testing
- Production-size Render compute and managed PostgreSQL with backups
- Centralized logs and alerts

See [Deploying to Render](deployment.md) for the current deployment boundary.

## Explicitly deferred

The roadmap does not include:

- Automated trading or brokerage order entry
- Model-generated prices or price targets
- Public publishing or multi-user collaboration
- Mobile applications
- One unconstrained autonomous agent
- Microservices, Redis, Celery, or a separate vector database without measured
  need
