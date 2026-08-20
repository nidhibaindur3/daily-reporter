# Research system

**Status:** Closed-source Research Discovery MVP is implemented

## Purpose

The research system looks for current patterns that may have durable industry
or company implications. Its output is an evidence-backed hypothesis and a set
of questions to investigate, not a prediction or trading instruction.

The guiding question is:

> What is happening beneath the surface that I should investigate?

## Key concepts

| Concept | Meaning |
| --- | --- |
| Source | A canonical publisher, provider, filing, page, or document |
| Source snapshot | The exact version and metadata observed during one run |
| Claim | One atomic statement classified as fact, signal, inference, or research hypothesis |
| Signal | A timely observation or convergence detected across claims |
| Theme | A possible pattern connecting multiple signals |
| Evidence | A source passage or structured field related to a claim |
| Research thesis | A preliminary explanation of the theme and its mechanism |
| Research opportunity | The validated, user-facing research document |

Evidence can **support**, **contradict**, or **contextualize** a claim.

## Current source boundary

The MVP uses:

- Approved publisher-operated RSS or Atom feeds
- Typed market observations for the configured watchlist

Publisher content is limited to metadata and bounded publisher-provided
excerpts. Full-page retrieval, general web search, forums, SEC filings, and
investor-relations search are not implemented yet.

This boundary matters: the current system can find useful leads, but it cannot
claim that it completed broad due diligence. Published opportunities therefore
remain visibly incomplete when wider or contradictory evidence is needed.

## Implemented pipeline

    Sources -> Claims -> Signals -> Themes -> Evidence
            -> Contradiction review -> Research Thesis
            -> Research Opportunity

| Stage | What happens | Owner |
| --- | --- | --- |
| Start | Create the discovery run and durable job atomically | Deterministic |
| Sources | Collect, normalize, hash, deduplicate, and persist snapshots | Deterministic |
| Claims | Extract atomic statements tied to known snapshots | AI, then deterministic validation |
| Signals | Form source observations and convergence signals | Deterministic |
| Themes | Connect signals into a small set of candidate patterns | AI, then deterministic thresholds |
| Evidence | Verify evidence coverage and source relationships | Deterministic |
| Contradictions | Challenge the theme within the closed evidence packet | Separate AI call |
| Thesis | Form cited implications, mechanisms, and research posture | AI, then deterministic validation |
| Opportunity | Materialize provenance, scores, limitations, and read model | Deterministic |
| Publish | Mark the run complete, incomplete, empty, failed, or cancelled | Deterministic |

The worker persists each stage. Attempts, leases, retries, and stable error codes
allow interrupted work to recover without turning the entire worker into one
autonomous agent.

## Pattern threshold

A theme should represent convergence, not a rewritten story. Application code
checks:

- The referenced signals and claims exist.
- Independent sources are actually independent.
- Evidence covers the important factual premises.
- Companies and industries can be traced to cited entities or mechanisms.
- Numeric statements exist in provider data or cited claims.
- The output does not contain generated URLs or trading directives.

If no theme meets the threshold, the correct result is an empty run with a clear
explanation. The system should not lower the evidence bar merely to fill the
dashboard.

## Provenance model

Every important conclusion becomes a claim. AI conclusions depend on premise
claims through explicit claim-dependency records.

    Source -> Source snapshot -> Evidence -> Claim
                                 |           |
                                 |           v
                                 |       Claim dependency -> Premise claim
                                 v
                     supports, contradicts, or contextualizes

An evidence record keeps:

- Claim and source-snapshot identifiers
- Relationship to the claim
- Relevant passage or structured field
- Location within the source
- Extraction method and verification state

The opportunity document is optimized for display. The provenance endpoint
returns the normalized graph for inspection.

## Claim types

- **Fact** — a directly verifiable statement from a source or typed observation.
- **Signal** — an observed change, cluster, or convergence worth attention.
- **Inference** — an interpretation grounded in cited premise claims.
- **Research hypothesis** — a testable possibility that needs more evidence.

The type controls how the UI labels a statement and how strongly it may be
presented. An inference or hypothesis must never be disguised as a fact.

## Source quality

Source authority is claim-specific, but the default preference is:

1. Primary sources
2. Government and regulatory sources
3. Company filings and investor relations
4. High-quality journalism
5. Academic and research sources
6. Specialist publications

Discovery sources, aggregators, forums, social posts, and unsourced commentary
may identify a lead. They should not be the only evidence for an important
factual claim.

Authority and independence are different:

- Investor relations is primary for what a company said, but is not independent
  confirmation that the claim is true.
- A regulatory filing is authoritative about what was filed, but not whether
  management assumptions will succeed.
- Syndicated copies of one report do not count as independent sources.
- A market provider is appropriate for a timestamped quote; an old article is
  not.

Application code assigns and records source-quality defaults. Any manual
override must be auditable.

## Research opportunity

The user-facing document includes:

- Theme, summary, and why now
- Detected signals
- Affected industries and companies
- Direct and second-order impact paths
- Research thesis and mechanism
- Bull and bear cases
- Contradictory evidence
- Risks and invalidation conditions
- Research questions
- Source-quality summary and source links
- Priority, confidence, and limitations
- Market-awareness state
- Long-term investment lens

Important statements carry claim identifiers that resolve through the
provenance graph.

Industry selection is explicitly an inference. An industry name does not need
to appear verbatim in a source when the model can explain a plausible direct or
second-order mechanism from cited claims. The UI labels the rationale as an
inference. Company names remain stricter and must be present in cited claim
entities.

## Long-term investment lens

The lens asks whether the detected change could alter durable demand, cost
structure, competition, regulation, or company economics.

It provides:

- Long-term relevance
- Research posture
- Rationale for that posture
- Evidence or conditions to watch next

Research posture can be **research now**, **watch for confirmation**, or
**insufficient evidence**. It is not a buy or sell signal.

Capital-deployment timing remains **insufficient data** until the system has
deterministic broad-market, valuation, crowdedness, and relevant user-controlled
portfolio inputs.

## Priority and confidence

The application computes final scores with versioned rules. Inputs can include:

- Source authority and relevance
- Independent-source breadth
- Evidence coverage
- Signal strength, freshness, and novelty
- Contradiction severity
- Known data and workflow limitations

The component breakdown remains visible. A high aggregate score must not hide a
low-confidence material premise.

Market awareness is separate from theme quality. Until reporting breadth,
community attention, and observed market reaction are available, awareness and
pricing states remain **not assessed** or **insufficient data**.

## Run outcomes

| Outcome | Meaning |
| --- | --- |
| Complete | All required checks for the configured source scope passed |
| Incomplete | Useful evidence exists, but material questions or source gaps remain |
| Empty | No candidate met the evidence and independence threshold |
| Failed | No trustworthy result could be produced |
| Cancelled | Work was stopped by the user or system |

The UI should show the outcome, as-of time, limitations, unanswered questions,
and source retrieval times.

## Planned deep-research extension

The future deep-research workflow will extend, not replace, the current
pipeline:

1. Record the user's question, entities, versions, and budgets.
2. Produce a bounded plan with required evidence types.
3. Search approved web, regulatory, filing, company, and community tools.
4. Collect exact documents through controlled fetchers.
5. Add claims and evidence to the same ledger.
6. Review gaps and contradictions and allow limited follow-up cycles.
7. Run approved calculations with typed inputs and recorded formulas.
8. Synthesize, validate, and publish a complete or incomplete report.

Search snippets and forum posts remain discovery signals until stronger evidence
is collected. Every tool will be typed, read-only, bounded, and audited.

## Failure handling

- Missing primary source: use the best available source and disclose the gap.
- Conflicting sources: preserve both rather than averaging away disagreement.
- Paywalled source: keep accessible metadata; do not claim unseen content.
- Ambiguous entity: stop rather than merge different companies or assets.
- Stale previous research: treat it as historical context and refresh current
  claims.
- Prompt injection in a source: ignore the instruction and keep the text as
  untrusted data.
- Budget exhausted: publish incomplete with the open questions.

The run record preserves stages, sources, evidence, model and prompt versions,
validator outcomes, and final status for debugging and reproducibility. Secrets,
sensitive content, and hidden model reasoning do not belong in the audit log.
