# RAG and persistent knowledge

**Status:** Planned; no embeddings or knowledge retrieval are used today

## Goal

Retrieval-augmented generation (RAG) will let Daily Digest reuse the user's
durable knowledge:

- Saved articles
- Papers and technical documentation
- Personal notes
- Previous research opportunities and reports

RAG provides memory and historical context. It is not a source of truth for
current prices, breaking events, company conditions, regulations, or other
time-sensitive facts.

## Hard boundary

| Use RAG for | Use a current provider or research tool for |
| --- | --- |
| Find a saved note or paper | Current market prices |
| Recall a previous hypothesis | Breaking news |
| Connect an event to prior research | A current filing or company statement |
| Identify unanswered historical questions | Current laws, leadership, or product state |
| Avoid duplicating earlier work | Any fact with a newer freshness requirement |

A historical result may suggest what to verify. It cannot make a current claim
current again.

## Proposed architecture

RAG will stay inside the existing modular monolith and PostgreSQL database:

    Saved document or note
              |
              v
    durable ingestion job
              |
    validate -> extract -> deduplicate -> chunk
              |
              +-- PostgreSQL full-text index
              +-- pgvector embeddings

No separate vector database or ingestion service is needed for the initial
personal corpus.

## Proposed data model

| Record | Purpose |
| --- | --- |
| Knowledge document | Canonical source, ownership, dates, metadata, and retention policy |
| Document version | Exact content hash and extraction result |
| Chunk | Stable text location, heading path, page, and inherited metadata |
| Embedding | Vector, model, dimensions, normalization, and version |
| Ingestion job | Durable state, attempts, errors, and re-index status |
| Retrieval use | Which report used which chunk and when |

Changing the embedding model or dimensions creates a re-indexing job. The
system must not silently mix incompatible vector versions.

## Ingestion flow

### 1. Validate

Accept only supported types and bounded sizes. Remote retrieval must enforce
timeouts, safe redirects, private-network protection, content-type checks, and
licensing or retention rules.

### 2. Extract

Preserve:

- Title, author, and publisher
- Canonical URL when available
- Document type and language
- Publication and retrieval dates
- Section and page structure
- User tags and notes
- Extraction method and version

Store full text only when permitted. Otherwise retain metadata,
user-authored notes, and allowed excerpts.

### 3. Deduplicate

Use canonical identifiers and content hashes for exact duplicates. Preserve
meaningful versions instead of silently overwriting them. Previous research
keeps both its generation date and the dates of its evidence.

### 4. Chunk

Prefer document structure such as headings, paragraphs, sections, and pages over
arbitrary fixed-size splits.

Each chunk retains a stable identifier, document version, order, heading path,
page or source location, text hash, token count, and inherited metadata.

Chunk size and overlap are evaluation choices, not permanent architecture
constants.

### 5. Index

Store lexical search data and embeddings in PostgreSQL. Exact vector search is
likely sufficient for the first personal corpus. Add an approximate index only
after corpus size and measured latency justify it.

## Retrieval flow

The first retrieval implementation should use hybrid search:

1. Parse the task query and apply ownership and metadata filters.
2. Run PostgreSQL full-text search.
3. Run pgvector semantic search.
4. Merge results with a deterministic rank-fusion rule.
5. Apply diversity and per-document limits.
6. Return a bounded context with stable chunk identifiers.

Each retrieval result includes:

- Chunk and document identifiers
- Permitted text or excerpt
- Heading, page, or source location
- Title, author, publisher, and document type
- Publication and ingestion dates
- Lexical and semantic ranking signals
- Tags and freshness or historical-context warnings

The model cites result identifiers. Application code resolves them into
user-facing references.

## Integration with research

Research can use RAG to:

- Find a previous hypothesis and its open questions.
- Retrieve durable background on a technology or industry.
- Detect that a topic was already investigated.
- Compare a current pattern with historical notes.

RAG material enters the same claim and evidence ledger as other content. Its
source type and dates remain visible. A previous AI-generated report is not
promoted to a primary source; important current claims should be refreshed from
the underlying source or a new authoritative source.

## Security and lifecycle

Knowledge content is untrusted, including content the user saved.

- Ignore instructions embedded in documents.
- Keep retrieved passages separate from system and tool instructions.
- Apply ownership filters to every retrieval query.
- Sanitize markup and filenames.
- Bound uploads and extraction work.
- Exclude secrets and unrelated private notes from prompts and logs.

The user should be able to inspect ingestion status, re-index a document, delete
it and its chunks and vectors, and see which research used it.

Multi-user sharing is deferred. Before any multi-user release, repository-level
tenant filtering and cross-user leakage tests are required.

## Evaluation gates

Before RAG is connected to research, measure:

- Relevant-document and relevant-chunk recall
- Precision and diversity of selected context
- Citation resolvability
- Metadata and ownership-filter correctness
- Freshness labeling
- Resistance to prompt injection
- Faithfulness to retrieved material
- Latency and context size

Start with a small manually labeled query set. Tune chunking, fusion, reranking,
and indexes from measured results.

See [Testing and evaluation](evaluation.md) for the shared release process.

## Deferred complexity

The first implementation will not need a knowledge graph, separate vector
database, complex multi-stage rerankers, automatic ingestion of every visited
page, or automated ontology construction.
