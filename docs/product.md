# Product

**Status:** Current product definition

## Product goal

Daily Digest answers one question:

> What is happening beneath the surface that I should investigate?

The app is for a person who wants to understand markets and invest for the long
term but cannot review every relevant source each day. It turns a large stream
of current information into a small set of evidence-backed research leads.

The desired outcome is better investigation, not a prediction:

- Recognize an emerging industry or company development.
- Understand the possible economic mechanism.
- See both supporting and contradictory evidence.
- Decide what to research or monitor next.

## Product promise

Daily Digest should help the user move from:

> Many disconnected market and company updates

to:

> A few traceable hypotheses about durable changes worth investigating

Every important conclusion should answer three questions:

1. **Why now?** What changed or converged recently?
2. **Why might it matter?** What industry or company economics could change?
3. **What should I verify?** Which evidence would strengthen or invalidate the
   hypothesis?

## Current experience

The dashboard provides:

### Market watchlist

A configured list of companies with provider-supplied prices and deterministic
daily changes. It helps the user see current movement, but it does not explain
the whole market environment.

### Research Discovery

An on-demand background run that:

1. Collects approved current sources and watchlist observations.
2. Extracts source-bound claims.
3. Detects signals and patterns that span independent sources.
4. Challenges candidate themes with contradictory evidence.
5. Publishes traceable research opportunities.

### Research opportunity

Each opportunity can include:

- Theme, summary, and why now
- Detected signals
- Potentially affected industries and companies
- Bull case and bear case
- Contradictory evidence and risks
- Invalidation conditions and research questions
- Source-quality breakdown and citations
- Research priority, confidence, and known limitations
- A long-term research posture and evidence to watch next

Facts, signals, interpretations, and hypotheses remain visibly distinct.

## Investment lens

The product uses a long-horizon, accumulation-oriented lens. It asks whether a
development may change durable industry structure, demand, costs, competition,
or company economics.

The current product may label a theme:

- **research now**
- **watch for confirmation**
- **insufficient evidence**

This is a research posture, not an instruction to deploy capital. A responsible
buying-day assessment also needs broad-market conditions, valuation,
crowdedness, risk tolerance, liquidity needs, and portfolio context. Those
inputs are not all available yet, so the app explicitly reports insufficient
data instead of guessing.

## Product principles

### Evidence before narrative

Important factual claims must resolve to stored evidence. Contradictions and
unknowns stay visible.

### Changes before generic knowledge

Research should explain what changed recently and why the pattern is timely.
Generic investment commentary is not a useful result.

### Patterns before story summaries

The key capability is connecting signals across sources. The product should not
become a list of rewritten headlines.

### Deterministic facts, AI interpretation

Providers and application code own current data, calculations, provenance, and
workflow state. AI handles bounded interpretation and synthesis.

### Skepticism by design

The system actively looks for contradictory evidence and specific invalidation
conditions. Confidence cannot hide important evidence gaps.

## Scope

| Available now | Next | Planned later |
| --- | --- | --- |
| Configurable watchlist | Broad-market context | SEC and regulatory search |
| Curated research feeds | Sector and breadth data | Investor-relations search |
| Durable discovery jobs | Rates and volatility | Wider web and forum discovery |
| Evidence provenance | Explicit market-environment state | User-selected deep research |
| Structured research opportunities | Better valuation inputs | Persistent knowledge and RAG |

The [roadmap](roadmap.md) defines the implementation order.

## Non-goals

Daily Digest does not:

- Recommend a specific buy, sell, position size, or price target.
- Execute trades or connect the model to order-entry tools.
- Present model-generated prices, financial values, or current events as facts.
- Treat forum sentiment as authoritative evidence.
- Claim that today is a favorable buying day without the necessary data.
- Provide a standalone news feed, weather page, or general daily brief.
- Replace professional financial, legal, tax, or investment advice.

For evidence rules and pipeline details, see the
[research system](research-system.md).
