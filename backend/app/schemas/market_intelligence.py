from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.market_intelligence import (
    DiscoveryRun,
    OpportunityProvenance,
    OpportunityRecord,
    SourceSnapshotView,
)


class ApiSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StartDiscoveryRunRequest(ApiSchema):
    window_hours: int = Field(default=48, ge=12, le=168)
    maximum_themes: int = Field(default=3, ge=1, le=3)
    focus_topics: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("focus_topics")
    @classmethod
    def normalize_focus_topics(cls, values: list[str]) -> list[str]:
        normalized = [" ".join(value.lower().split()) for value in values]
        normalized = list(dict.fromkeys(value for value in normalized if value))
        if any(len(value) > 80 for value in normalized):
            raise ValueError("focus topics cannot exceed 80 characters")
        return normalized


class DiscoveryRunResponse(ApiSchema):
    run_id: str
    status: Literal[
        "queued",
        "running",
        "complete",
        "incomplete",
        "failed",
        "cancelled",
    ]
    current_stage: str
    window_hours: int
    maximum_themes: int
    focus_topics: list[str]
    workflow_version: str
    error_code: Optional[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

    @classmethod
    def from_run(cls, run: DiscoveryRun) -> "DiscoveryRunResponse":
        return cls(
            run_id=run.id,
            status=run.status,  # type: ignore[arg-type]
            current_stage=run.current_stage,
            window_hours=run.window_hours,
            maximum_themes=run.maximum_themes,
            focus_topics=list(run.focus_topics),
            workflow_version=run.workflow_version,
            error_code=run.error_code,
            created_at=run.created_at,
            updated_at=run.updated_at,
            completed_at=run.completed_at,
        )


class CitedStatementResponse(ApiSchema):
    text: str
    claim_type: Literal["fact", "signal", "inference", "research_hypothesis"]
    claim_ids: list[str]
    premise_claim_ids: list[str]
    evidence_ids: list[str]
    source_ids: list[str]


class DetectedSignalResponse(ApiSchema):
    signal_id: str
    description: str
    topic: str
    claim_type: Literal["signal"]
    claim_ids: list[str]
    source_ids: list[str]
    independent_source_count: int
    strength_score: float


class AffectedAreaResponse(ApiSchema):
    name: str
    relationship: Literal["direct", "second_order", "third_order"]
    direction: Literal["positive", "negative", "mixed", "unknown"]
    rationale: CitedStatementResponse


class ImpactPathResponse(ApiSchema):
    from_node: str
    to_node: str
    effect_order: Literal["direct", "second_order", "third_order"]
    direction: Literal["positive", "negative", "mixed", "unknown"]
    mechanism: CitedStatementResponse


class ThemeResponse(ApiSchema):
    name: str
    description: str
    signal_ids: list[str]


class SourceQualityResponse(ApiSchema):
    source_count: int
    independent_source_count: int
    authority_counts: dict[str, int]
    discovery_only_count: int


class ScoreResponse(ApiSchema):
    label: Literal["low", "medium", "high"]
    score: float
    method_version: str
    components: dict[str, Any]
    limitations: list[str] = Field(default_factory=list)


class MarketAwarenessResponse(ApiSchema):
    awareness_state: Literal[
        "not_assessed",
        "emerging",
        "gaining_attention",
        "widely_known",
        "potentially_crowded",
        "unknown",
    ]
    pricing_state: Literal[
        "not_assessed",
        "insufficient_data",
        "unclear",
        "possibly_partially_reflected",
        "possibly_widely_reflected",
    ]
    reporting_breadth: int
    community_signal_count: int
    company_mention_count: int
    observed_market_reaction: Optional[dict[str, Any]]
    as_of: datetime
    method_version: str


class InvestmentLensResponse(ApiSchema):
    orientation: Literal["long_term_accumulation"]
    research_posture: Literal[
        "research_now",
        "watch_for_confirmation",
        "insufficient_evidence",
    ]
    long_term_relevance: CitedStatementResponse
    posture_rationale: CitedStatementResponse
    what_to_watch: list[CitedStatementResponse]
    capital_deployment_assessment: Literal["insufficient_data"]
    capital_deployment_limitations: list[str]


class ResearchOpportunityDocumentResponse(ApiSchema):
    theme: ThemeResponse
    summary: CitedStatementResponse
    why_now: CitedStatementResponse
    detected_signals: list[DetectedSignalResponse]
    affected_industries: list[AffectedAreaResponse]
    affected_companies: list[AffectedAreaResponse]
    impact_paths: list[ImpactPathResponse]
    research_thesis: CitedStatementResponse
    mechanism: CitedStatementResponse
    bull_case: list[CitedStatementResponse]
    bear_case: list[CitedStatementResponse]
    contradictory_evidence: list[CitedStatementResponse]
    risks: list[CitedStatementResponse]
    invalidation_conditions: list[CitedStatementResponse]
    research_questions: list[CitedStatementResponse]
    source_quality: SourceQualityResponse
    source_ids: list[str]
    research_priority: ScoreResponse
    confidence: ScoreResponse
    market_awareness: MarketAwarenessResponse
    investment_lens: Optional[InvestmentLensResponse] = None
    scope: Literal["current_source_mvp"]


class OpportunitySourceResponse(ApiSchema):
    source_snapshot_id: str
    source_id: str
    title: str
    publisher: str
    url: Optional[str]
    source_class: Literal["primary_evidence", "reporting", "discovery"]
    document_type: str
    authority_tier: str
    published_at: datetime
    retrieved_at: datetime

    @classmethod
    def from_view(cls, view: SourceSnapshotView) -> "OpportunitySourceResponse":
        return cls(
            source_snapshot_id=view.snapshot.id,
            source_id=view.source.id,
            title=view.snapshot.title,
            publisher=view.source.publisher,
            url=view.snapshot.canonical_url,
            source_class=view.source.source_class,
            document_type=view.source.document_type,
            authority_tier=view.source.authority_tier,
            published_at=view.snapshot.published_at,
            retrieved_at=view.snapshot.retrieved_at,
        )


class ResearchOpportunityResponse(ApiSchema):
    opportunity_id: str
    run_id: str
    status: Literal["complete", "incomplete"]
    document: ResearchOpportunityDocumentResponse
    sources: list[OpportunitySourceResponse]
    as_of: datetime
    schema_version: Literal["research_opportunity.v1", "research_opportunity.v2"]
    created_at: datetime

    @classmethod
    def from_record(
        cls,
        record: OpportunityRecord,
        sources: tuple[SourceSnapshotView, ...],
    ) -> "ResearchOpportunityResponse":
        return cls(
            opportunity_id=record.id,
            run_id=record.run_id,
            status=record.status,  # type: ignore[arg-type]
            document=ResearchOpportunityDocumentResponse.model_validate(
                record.document
            ),
            sources=[OpportunitySourceResponse.from_view(source) for source in sources],
            as_of=record.as_of,
            schema_version=record.schema_version,  # type: ignore[arg-type]
            created_at=record.created_at,
        )


class ResearchOpportunityListResponse(ApiSchema):
    opportunities: list[ResearchOpportunityResponse]


class ProvenanceClaimResponse(ApiSchema):
    claim_id: str
    statement: str
    claim_type: str
    verification_status: str
    created_by: str
    topics: list[str]
    entities: list[str]
    effective_at: datetime


class ProvenanceEvidenceResponse(ApiSchema):
    evidence_id: str
    claim_id: str
    source_snapshot_id: str
    relationship: Literal["supports", "contradicts", "contextualizes"]
    passage: str
    location: str
    extraction_method: str
    verification_status: str


class ClaimDependencyResponse(ApiSchema):
    parent_claim_id: str
    dependent_claim_id: str
    relationship: str


class OpportunityProvenanceResponse(ApiSchema):
    opportunity_id: str
    sources: list[OpportunitySourceResponse]
    claims: list[ProvenanceClaimResponse]
    evidence: list[ProvenanceEvidenceResponse]
    claim_dependencies: list[ClaimDependencyResponse]
    signals: list[dict[str, Any]]
    themes: list[dict[str, Any]]
    theses: list[dict[str, Any]]

    @classmethod
    def from_bundle(
        cls, bundle: OpportunityProvenance
    ) -> "OpportunityProvenanceResponse":
        return cls(
            opportunity_id=bundle.opportunity.id,
            sources=[
                OpportunitySourceResponse.from_view(item) for item in bundle.sources
            ],
            claims=[
                ProvenanceClaimResponse(
                    claim_id=claim.id,
                    statement=claim.statement,
                    claim_type=claim.claim_type,
                    verification_status=claim.verification_status,
                    created_by=claim.created_by,
                    topics=list(claim.topics),
                    entities=list(claim.entities),
                    effective_at=claim.effective_at,
                )
                for claim in bundle.claims
            ],
            evidence=[
                ProvenanceEvidenceResponse(
                    evidence_id=item.id,
                    claim_id=item.claim_id,
                    source_snapshot_id=item.source_snapshot_id,
                    relationship=item.relationship,
                    passage=item.passage,
                    location=item.location,
                    extraction_method=item.extraction_method,
                    verification_status=item.verification_status,
                )
                for item in bundle.evidence
            ],
            claim_dependencies=[
                ClaimDependencyResponse(
                    parent_claim_id=parent,
                    dependent_claim_id=dependent,
                    relationship=relationship,
                )
                for parent, dependent, relationship in bundle.claim_dependencies
            ],
            signals=[
                {
                    "signal_id": signal.id,
                    "description": signal.description,
                    "topic": signal.topic,
                    "claim_ids": list(signal.claim_ids),
                }
                for signal in bundle.signals
            ],
            themes=[
                {
                    "theme_id": theme.id,
                    "name": theme.name,
                    "description": theme.description,
                    "why_now": theme.why_now,
                    "signal_ids": list(theme.signal_ids),
                    "contradiction_review": theme.contradiction_review,
                }
                for theme in bundle.themes
            ],
            theses=[
                {
                    "thesis_id": thesis.id,
                    "theme_id": thesis.theme_id,
                    "document": thesis.document,
                }
                for thesis in bundle.theses
            ],
        )
