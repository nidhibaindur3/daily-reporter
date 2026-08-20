import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Optional

MARKET_INTELLIGENCE_WORKFLOW_VERSION = "market_intelligence.workflow.v2"
RESEARCH_OPPORTUNITY_SCHEMA_VERSION = "research_opportunity.v2"
RESEARCH_THESIS_SCHEMA_VERSION = "research_thesis.v3"

PipelineStage = Literal[
    "sources",
    "claims",
    "signals",
    "themes",
    "evidence",
    "contradictions",
    "theses",
    "opportunities",
    "done",
]
RunStatus = Literal[
    "queued",
    "running",
    "complete",
    "incomplete",
    "failed",
    "cancelled",
]
ClaimType = Literal["fact", "signal", "inference", "research_hypothesis"]
EvidenceRelationship = Literal["supports", "contradicts", "contextualizes"]
SourceClass = Literal["primary_evidence", "reporting", "discovery"]


def stable_record_id(prefix: str, *parts: object) -> str:
    payload = "|".join(str(part) for part in parts).encode()
    digest = hashlib.sha256(payload).hexdigest()[:24]
    return f"{prefix}:{digest}"


@dataclass(frozen=True)
class DiscoveryRun:
    id: str
    status: str
    current_stage: str
    window_hours: int
    maximum_themes: int
    focus_topics: tuple[str, ...]
    workflow_version: str
    error_code: Optional[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]


@dataclass(frozen=True)
class SourceRecord:
    id: str
    publisher: str
    canonical_url: Optional[str]
    source_class: SourceClass
    document_type: str
    authority_tier: str
    independence_group: str
    discovery_only: bool
    created_at: datetime


@dataclass(frozen=True)
class SourceSnapshotRecord:
    id: str
    run_id: str
    source_id: str
    canonical_url: Optional[str]
    title: str
    published_at: datetime
    retrieved_at: datetime
    content_hash: str
    excerpt: str
    structured_data: dict[str, Any]
    extraction_status: str = "ready"


@dataclass(frozen=True)
class SourceSnapshotView:
    snapshot: SourceSnapshotRecord
    source: SourceRecord


@dataclass(frozen=True)
class ClaimRecord:
    id: str
    run_id: str
    statement: str
    claim_type: ClaimType
    effective_at: datetime
    verification_status: str
    created_by: str
    topics: tuple[str, ...]
    entities: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceRecord:
    id: str
    run_id: str
    claim_id: str
    source_snapshot_id: str
    relationship: EvidenceRelationship
    passage: str
    location: str
    extraction_method: str
    verification_status: str


@dataclass(frozen=True)
class ClaimEvidenceView:
    claim: ClaimRecord
    evidence: tuple[EvidenceRecord, ...]
    snapshots: tuple[SourceSnapshotView, ...]


@dataclass(frozen=True)
class SignalRecord:
    id: str
    run_id: str
    signal_type: str
    description: str
    topic: str
    first_observed_at: datetime
    last_observed_at: datetime
    source_count: int
    independent_source_count: int
    novelty_score: float
    strength_score: float
    status: str
    claim_ids: tuple[str, ...]


@dataclass(frozen=True)
class ThemeRecord:
    id: str
    run_id: str
    name: str
    description: str
    why_now: str
    first_detected_at: datetime
    freshness_score: float
    novelty_score: float
    status: str
    signal_ids: tuple[str, ...]
    contradiction_review: dict[str, Any]


@dataclass(frozen=True)
class ThesisRecord:
    id: str
    run_id: str
    theme_id: str
    document: dict[str, Any]
    status: str
    schema_version: str
    created_at: datetime


@dataclass(frozen=True)
class OpportunityRecord:
    id: str
    run_id: str
    theme_id: str
    thesis_id: str
    document: dict[str, Any]
    status: str
    priority_label: str
    priority_score: float
    confidence_label: str
    confidence_score: float
    market_awareness: dict[str, Any]
    as_of: datetime
    schema_version: str
    created_at: datetime


@dataclass(frozen=True)
class OpportunityProvenance:
    opportunity: OpportunityRecord
    sources: tuple[SourceSnapshotView, ...]
    claims: tuple[ClaimRecord, ...]
    evidence: tuple[EvidenceRecord, ...]
    claim_dependencies: tuple[tuple[str, str, str], ...]
    signals: tuple[SignalRecord, ...]
    themes: tuple[ThemeRecord, ...]
    theses: tuple[ThesisRecord, ...]
