# AI architecture

**Status:** Four bounded reasoning stages are implemented

## Role of AI

AI connects, challenges, and explains evidence. It is not the source of truth
for current facts, financial data, calculations, permissions, persistence, or
workflow state.

Application services call task-specific AI interfaces. They do not import the
OpenAI SDK throughout the codebase. Model selection, credentials, timeouts, and
reasoning settings are centralized in backend configuration.

## Current model calls

The worker makes four structured-output calls:

| Stage | Receives | Produces |
| --- | --- | --- |
| Claim extraction | Identified source excerpts | Atomic claims tied to source-snapshot IDs |
| Theme formation | Validated signals and their claims | A small set of cross-source candidate themes |
| Contradiction review | One theme and a closed claim ledger | Challenges, limitations, and research questions |
| Thesis synthesis | Validated theme, signals, claims, and review | Cited preliminary thesis and long-term research posture |

These calls are modules inside an application-owned pipeline. The model cannot
skip stages, expand the source packet, or choose its own workflow state.

## Structured-output contract

Every call uses:

- A versioned instruction set
- A strict Pydantic response schema
- A closed packet with application-owned identifiers
- Bounded output tokens and request time
- Centralized model settings
- Provider-side storage disabled
- No tools in the current MVP

Schema parsing is only the first gate. Deterministic validation also rejects:

- Unknown source, claim, signal, or theme identifiers
- Numeric statements absent from cited premise claims
- Companies absent from cited claim entities
- Industry suggestions without cited premise claims or a specific mechanism
- Model-generated source URLs
- Direct trading instructions
- Themes without independent-source breadth

Invalid output is never written to core research tables.

## Provenance

The model cites claim identifiers, not free-form URLs. Application code then:

1. Creates a claim for each important AI conclusion.
2. Links the conclusion to its premise claims.
3. Carries premise evidence into the conclusion as contextual evidence.
4. Resolves exact source snapshots into user-facing citations.
5. Exposes the normalized graph through the provenance API.

This makes an inference inspectable even when its prose changes.

## Deterministic ownership

Application code, not the model, owns:

- Provider retrieval and payload parsing
- Current prices, timestamps, currencies, and calculations
- Hashing, deduplication, and source independence
- Pipeline order, transactions, retries, and terminal states
- Final confidence, priority, and market-awareness components
- Citation, entity, numeric, URL, and policy validation

The model may classify a research posture as **research now**, **watch for
confirmation**, or **insufficient evidence**. It may not decide whether the user
should invest today.

## Prompt and tool security

Source excerpts and future retrieved documents are untrusted data. Text inside a
source cannot change system instructions, grant a tool, expose credentials, or
expand the job's scope.

Future tools must be:

- Narrow and typed
- Read-only
- Time- and size-bounded
- Restricted to approved providers and operations
- Audited by the application

The model must never receive arbitrary network, database, filesystem, shell, or
trading access.

## Failure behavior

Provider errors and invalid model output use the worker's bounded retry policy.
Exhausted work ends in an explicit failed or incomplete state. Evidence from
completed stages remains available for debugging and audit.

The system should abstain when it cannot meet an evidence threshold. A fluent
answer is not a successful result if its claims are not grounded.

## Observability

Log:

- Model and stage
- Prompt and schema version
- Latency
- Token usage
- Safe outcome or error code

Do not log credentials, source packets, prompts, generated conclusions, or
sensitive user content.

## Planned capabilities

Later milestones may add approved research-tool selection, bounded follow-up
searches, user-selected research planning, and RAG retrieval. These capabilities
must preserve the same structured contracts, provenance rules, and
application-owned workflow.

Fine-tuning, multiple cooperating agents, and autonomous open-ended research
are not required for the current product.
