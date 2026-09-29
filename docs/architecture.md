# System architecture

**Status:** Implemented modular-monolith architecture

## Overview

Daily Digest uses a small number of deployable parts:

- A React and TypeScript frontend
- A FastAPI API
- A background worker that imports the same backend package
- A PostgreSQL database

PostgreSQL includes pgvector for a future persistent-knowledge milestone. The
current research pipeline does not use embeddings.

This modular monolith keeps local development and operations simple while
preserving clear boundaries between the UI, application logic, providers, AI,
and persistence.

## Deployment topology

**Current:** The repository includes a Render Blueprint that maps each runtime
part to a native Render resource:

| Application part | Render resource |
| --- | --- |
| React frontend | Static site |
| FastAPI API | Web service |
| Research worker | Background worker |
| PostgreSQL | Render Postgres 16 |

The API and worker receive Render's internal PostgreSQL connection string. The
frontend and API receive each other's generated public URL for API requests and
the exact CORS allowlist. Alembic migrations run as the paid worker's pre-deploy
command because Render does not support pre-deploy commands on free web
services.

This preserves the same process and dependency boundaries used locally; Render
does not introduce another queue, cache, or service. See
[Deploying to Render](deployment.md) for setup and current limits.

## Runtime view

    Browser
       |
       | REST
       v
    React dashboard
       |
       v
    FastAPI API ---------------------------- PostgreSQL
       |                                         ^
       | create durable job                      | persist state and results
       v                                         |
    Background worker ---------------------------+
       |
       +-- approved publisher feeds
       +-- market-data provider
       +-- OpenAI structured outputs

The browser talks only to FastAPI. Third-party requests and credentials remain
on the backend.

## Request paths

### Fast read path

Health and watchlist requests run through the API:

    Browser -> API -> service -> provider or database -> validated response

The API can use bounded caches for external observations. One failed symbol
does not hide otherwise valid market data.

### Research path

Research runs asynchronously:

1. The browser asks the API to start a discovery run.
2. The API creates the run and job in one database transaction.
3. A worker claims the job and advances one persisted stage at a time.
4. The browser polls the run and reads published opportunities.

Long provider or model work never runs as a FastAPI in-process background task.
If a worker restarts, the lease and stored stage allow the job to continue or
retry safely.

## Component responsibilities

| Component | Owns | Does not own |
| --- | --- | --- |
| Frontend | Rendering, user actions, loading and failure states | Provider calls, secrets, calculations, orchestration |
| API routes | HTTP validation, commands, read models | Business rules or long-running work |
| Services | Use-case orchestration and domain policy | HTTP or provider-specific payloads |
| Worker | Job claiming, stage execution, retries | Unbounded autonomous decisions |
| Providers | External requests and payload normalization | Product policy or persistence |
| Repositories | Transactions and database records | Provider access or model reasoning |
| AI adapter | Versioned structured reasoning calls | Workflow state or direct table writes |
| Domain models | Provider-independent records and rules | Framework-specific behavior |

## Research pipeline

The implemented pipeline is:

    Sources -> Claims -> Signals -> Themes -> Evidence
            -> Research Thesis -> Research Opportunity

Contradiction review occurs after evidence validation and before thesis
synthesis. Application code owns the sequence and validation. AI is used only
in the stages that require language interpretation.

See [Research system](research-system.md) for stage-level ownership and
[AI architecture](ai-architecture.md) for model-call contracts.

## Data model

| Area | Main records | Purpose |
| --- | --- | --- |
| Operations | discovery run, job | Stage, status, attempts, leases, and errors |
| Sources | source, source snapshot | Canonical resource and exact observed version |
| Claims | claim, claim dependency | Atomic assertion and its premises |
| Evidence | evidence | Source relationship to a claim |
| Discovery | signal, signal claim, theme, theme signal | Cross-source pattern detection |
| Research | thesis, opportunity | Versioned synthesis and dashboard document |
| Markets | quote, market status | Typed current observations |

Time-sensitive records use UTC and keep both observation and retrieval times.
Financial values retain their currency, unit, provider, and freshness metadata.

### Provenance graph

Provenance is normalized rather than embedded only in generated prose:

    Source -> Source snapshot -> Evidence -> Claim
                                      ^         |
                                      |         v
                                relationship  Claim dependency

Evidence relationships are:

- **supports**
- **contradicts**
- **contextualizes**

AI-generated conclusions become claims with dependencies on premise claims. The
API can therefore return both a convenient rendering document and the
underlying graph.

## API surface

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | /api/health | Check API and database health |
| GET | /api/markets/watchlist | Read configured market observations |
| POST | /api/v1/market-intelligence/runs | Start a durable discovery run |
| GET | /api/v1/market-intelligence/runs/{run_id} | Read run status |
| GET | /api/v1/market-intelligence/opportunities | List opportunities |
| GET | /api/v1/market-intelligence/opportunities/{id} | Read one opportunity |
| GET | /api/v1/market-intelligence/opportunities/{id}/provenance | Read its evidence graph |

Publisher-feed ingestion is internal and has no public route.

## Reliability

- Provider calls have timeouts, size limits, and bounded caches.
- Partial provider failure remains visible without discarding valid results.
- Jobs have attempts, leases, retry delays, and stable terminal error codes.
- Only schema-valid and provenance-valid model output may be persisted.
- Completed stages preserve useful evidence even if a later stage fails.

## Security

- Credentials remain in backend environment configuration and never enter the
  frontend bundle.
- Retrieved text and provider payloads are always treated as untrusted data.
- Source fetchers restrict hosts, redirects, content types, and response sizes.
- Model calls receive no arbitrary network, database, filesystem, shell, or
  trading access.
- Prompts, source packets, conclusions, and secrets are excluded from normal
  application logs.

## Deliberate constraints

The current architecture does not need microservices, Redis, Celery, a separate
vector database, or a general workflow framework. Add infrastructure only after
a measured need appears.

The system is research software. No component may execute a trade or promote an
AI research posture into a buy or sell instruction.
