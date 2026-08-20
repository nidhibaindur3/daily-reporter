# Testing and evaluation

**Status:** Deterministic test suite is implemented; the research evaluation set
expands with each milestone

## Quality model

Daily Digest uses two complementary quality systems:

- **Software tests** verify deterministic behavior such as schemas,
  calculations, state transitions, and constraints.
- **Research evaluations** measure whether a result is useful, grounded,
  source-aware, skeptical, and appropriately uncertain.

Exact prose is not a contract. Evidence relationships, identifiers, financial
values, schemas, and safety behavior are.

## Run the checks

Backend:

    cd backend
    ../.venv/bin/ruff check .
    ../.venv/bin/ruff format --check .
    RUN_DATABASE_TESTS=1 ../.venv/bin/python -m pytest
    ../.venv/bin/alembic check

Frontend:

    cd frontend
    npm run lint
    npm run typecheck
    npm run build

CI uses mocked or recorded provider responses. It must not call live
publishers, market providers, or OpenAI.

## Test layers

| Layer | Main coverage |
| --- | --- |
| Unit | Calculations, freshness, hashing, deduplication, source independence, scores, validators, retry rules |
| Provider contract | Authentication, normalization, timestamps, rate limits, malformed data, partial failure, cache behavior |
| AI boundary | Pydantic schemas, closed identifiers, tool limits, storage settings, safe telemetry |
| Database integration | Migrations, provenance constraints, transactions, jobs, leases, retries, cascades |
| API | Validation, HTTP status, stable errors, run state, opportunity and provenance scope |
| Frontend | Loading, running, empty, incomplete, complete, and failure states; accessibility and source navigation |

Database integration tests use PostgreSQL rather than an in-memory substitute
when database behavior is part of the contract.

## Release-blocking invariants

The following must remain true:

- Structured AI output validity after retries: 100 percent for published work
- Resolvable citation identifiers: 100 percent
- Evidence coverage for important factual claims: 100 percent
- Unsupported authoritative numeric claims: zero
- Invented affected companies: zero
- Trading or order-entry calls: zero
- Calls outside explicit provider or tool allowlists: zero
- Current claims sourced only from model memory or RAG: zero

The current suite also verifies that:

- A theme requires independent source groups.
- Unrelated topics can connect only when the claims support a real pattern.
- Unknown identifiers, generated URLs, and trading directives fail validation.
- AI conclusions become claims with premise dependencies.
- Specific industry categories may be inferred only from cited premise claims;
  affected company names must be present in the evidence packet.
- Empty contradiction findings retain the closed-source limitation.
- Market awareness stays unassessed without supporting inputs.
- Long-term relevance and research posture cite known premise claims.
- Capital-deployment timing stays insufficient without market, valuation, and
  investor-context inputs.

## Research evaluation set

Maintain frozen cases that exercise both good synthesis and correct abstention:

1. A company event with an authoritative filing.
2. A primary company claim without independent confirmation.
3. Conflicting reputable reporting.
4. Two different events with a valid second-order connection.
5. A plausible but unsupported pattern that should be rejected.
6. A numerical comparison requiring deterministic calculation.
7. A forum discovery lead that needs authoritative confirmation.
8. A source containing prompt injection.
9. Ambiguous company or asset names.
10. Insufficient evidence where no opportunity should be published.

Each case records expected evidence types, material claims, contradictions,
required calculations, likely traps, acceptable unknowns, and human-scoring
guidance.

## Evaluation metrics

Measure:

- Theme usefulness, timeliness, and novelty
- Factual precision and material-claim coverage
- Source authority, relevance, and independence
- Citation correctness at the passage level
- Contradiction recall
- Second-order reasoning quality
- Long-term economic-mechanism quality
- Usefulness of suggested industries, companies, and questions
- Specificity of invalidation conditions
- Appropriate uncertainty and abstention
- Latency, tokens, provider calls, and cost

No single aggregate score should conceal a release-blocking failure.

## Change process

Before changing a model, prompt, output schema, research tool, retrieval policy,
confidence formula, or pipeline stage:

1. Run deterministic tests.
2. Run the frozen evaluation set against the baseline and candidate.
3. Compare hard invariants, quality, latency, and cost.
4. Inspect regressions and representative improvements.
5. Version and record the accepted change.
6. Block release if any hard invariant fails.

When RAG is implemented, add retrieval recall, context precision, metadata
filtering, freshness, ownership isolation, and prompt-injection cases described
in [RAG and persistent knowledge](rag.md).
