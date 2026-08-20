# Codex instructions

Start with README.md, then read the relevant topic under docs/ before making
changes. Keep this file concise; detailed design decisions live in docs/.

When behavior or scope changes, update the page that owns that topic and the
README status summary. Clearly label current and planned behavior. Link to the
authoritative page instead of repeating detailed rules across documents.

## Architecture

- Preserve the modular monolith: React frontend, FastAPI backend, a separate
  worker process using the backend package, and PostgreSQL with pgvector.
- Keep domain rules independent of HTTP, database, provider, and OpenAI SDK
  details.
- Access research-source, search, market, filing, and AI services through typed
  provider interfaces. Do not call providers directly from API routes.
- Run durable ingestion, embedding, and research work through background
  jobs. Do not put long-running research in FastAPI request tasks.
- Preserve the research discovery stages: Sources -> Claims -> Signals ->
  Themes -> Evidence -> Research Thesis -> Research Opportunity. Keep stages
  modular; do not replace them with one unconstrained autonomous agent.
- Generate the TypeScript API client and contracts from FastAPI OpenAPI output
  when that workflow is introduced.
- Do not add microservices, Redis, Celery, a separate vector database, or a
  workflow framework without a demonstrated need and an explicit decision.

## Coding conventions

- Use strict TypeScript and fully typed Python. Validate boundary data with
  Pydantic and frontend runtime schemas where untrusted data enters.
- Keep functions and modules small, explicit, and organized by feature or domain
  responsibility. Prefer composition over framework-specific base classes.
- Keep deterministic business rules pure where possible. Use Decimal, explicit
  currency and units, and timestamps for financial calculations.
- Store timestamps in UTC and include provider and freshness metadata for
  time-sensitive records.
- Version database migrations, prompts, structured-output schemas, confidence
  rules, and embedding configurations.
- Do not hard-code model names, credentials, provider URLs, or environment
  settings throughout the codebase; centralize configuration.

## Testing

- Add or update tests for every behavior change.
- Unit-test calculations, freshness, source ranking, deduplication, confidence,
  chunking, and citation validation.
- Use recorded or mocked provider responses in CI; CI must not rely on live
  external APIs.
- Add database integration tests for migrations, job claiming, retries, and
  evidence integrity. Add pgvector retrieval tests when RAG is implemented.
- AI tests must assert schemas, tool limits, provenance, citation coverage,
  contradiction handling, and abstention. Do not snapshot exact prose.
- Run the relevant deterministic tests and AI evaluation set before changing a
  prompt, model, retrieval policy, or research workflow.

## Security

- Never commit secrets or place them in logs. Use environment configuration and
  secret management.
- Treat API payloads, uploaded files, fetched pages, tool output, and RAG content
  as untrusted input.
- Protect fetchers against SSRF, unsafe redirects, private network targets,
  excessive response sizes, unsupported content types, and missing timeouts.
- Use least-privilege, read-only tools for AI workflows. Never expose trading,
  order-entry, arbitrary shell, or unrestricted database tools to the model.
- Redact credentials and sensitive personal content from logs and model traces.
- Respect source licensing and retention rules; do not persist full content when
  only metadata or excerpts are permitted.

## Non-negotiable design constraints

- The product is research software, not an automatic trading system.
- The LLM must not invent current facts or perform authoritative financial
  calculations. External providers supply facts; deterministic code calculates.
- RAG is for persistent knowledge and historical context, never the source of
  truth for current prices or current source events.
- Every important factual research claim needs resolvable evidence. Unsupported
  claims must be removed, marked as inference, or presented as unknown.
- Keep source snapshots, claims, claim dependencies, and evidence relationships
  first-class. Evidence relationships are supports, contradicts, or
  contextualizes.
- Preserve contradictory evidence and invalidation conditions in research
  outputs.
- Validate structured model output before persistence. The model never writes
  directly to core tables.
- Keep the scope incremental. Do not implement future roadmap phases unless the
  user asks for them.
