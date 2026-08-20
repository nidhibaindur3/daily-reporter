from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DiscoveryRunModel(Base):
    __tablename__ = "discovery_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    current_stage: Mapped[str] = mapped_column(String(40), nullable=False)
    window_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    maximum_themes: Mapped[int] = mapped_column(Integer, nullable=False)
    focus_topics: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    workflow_version: Mapped[str] = mapped_column(String(80), nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'complete', 'incomplete', "
            "'failed', 'cancelled')",
            name="ck_discovery_runs_status",
        ),
    )


class JobModel(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("discovery_runs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    locked_by: Mapped[Optional[str]] = mapped_column(String(120))
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), index=True
    )
    error_code: Mapped[Optional[str]] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'complete', 'failed')",
            name="ck_jobs_status",
        ),
        Index("ix_jobs_claimable", "status", "available_at", "lease_expires_at"),
    )


class SourceModel(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    publisher: Mapped[str] = mapped_column(String(240), nullable=False)
    canonical_url: Mapped[Optional[str]] = mapped_column(Text)
    source_class: Mapped[str] = mapped_column(String(30), nullable=False)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False)
    authority_tier: Mapped[str] = mapped_column(String(40), nullable=False)
    independence_group: Mapped[str] = mapped_column(String(160), nullable=False)
    discovery_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "source_class IN ('primary_evidence', 'reporting', 'discovery')",
            name="ck_sources_source_class",
        ),
    )


class SourceSnapshotModel(Base):
    __tablename__ = "source_snapshots"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("discovery_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    canonical_url: Mapped[Optional[str]] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    structured_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    extraction_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="ready"
    )

    __table_args__ = (
        UniqueConstraint("run_id", "content_hash", name="uq_snapshot_run_hash"),
    )


class ClaimModel(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("discovery_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(30), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_by: Mapped[str] = mapped_column(String(30), nullable=False)
    topics: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    entities: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    __table_args__ = (
        CheckConstraint(
            "claim_type IN ('fact', 'signal', 'inference', 'research_hypothesis')",
            name="ck_claims_claim_type",
        ),
    )


class ClaimDependencyModel(Base):
    __tablename__ = "claim_dependencies"

    parent_claim_id: Mapped[str] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), primary_key=True
    )
    dependent_claim_id: Mapped[str] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), primary_key=True
    )
    relationship: Mapped[str] = mapped_column(String(40), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "relationship IN ('premise')",
            name="ck_claim_dependencies_relationship",
        ),
    )


class EvidenceModel(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("discovery_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    claim_id: Mapped[str] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("source_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship: Mapped[str] = mapped_column(String(30), nullable=False)
    passage: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str] = mapped_column(String(120), nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(40), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(30), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "relationship IN ('supports', 'contradicts', 'contextualizes')",
            name="ck_evidence_relationship",
        ),
        UniqueConstraint(
            "claim_id",
            "source_snapshot_id",
            "relationship",
            name="uq_evidence_claim_snapshot_relationship",
        ),
    )


class SignalModel(Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("discovery_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    signal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str] = mapped_column(String(160), nullable=False)
    first_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_count: Mapped[int] = mapped_column(Integer, nullable=False)
    independent_source_count: Mapped[int] = mapped_column(Integer, nullable=False)
    novelty_score: Mapped[float] = mapped_column(Float, nullable=False)
    strength_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)


class SignalClaimModel(Base):
    __tablename__ = "signal_claims"

    signal_id: Mapped[str] = mapped_column(
        ForeignKey("signals.id", ondelete="CASCADE"), primary_key=True
    )
    claim_id: Mapped[str] = mapped_column(
        ForeignKey("claims.id", ondelete="CASCADE"), primary_key=True
    )
    contribution: Mapped[str] = mapped_column(String(30), nullable=False)


class ThemeModel(Base):
    __tablename__ = "themes"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("discovery_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    why_now: Mapped[str] = mapped_column(Text, nullable=False)
    first_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    freshness_score: Mapped[float] = mapped_column(Float, nullable=False)
    novelty_score: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    contradiction_review: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )


class ThemeSignalModel(Base):
    __tablename__ = "theme_signals"

    theme_id: Mapped[str] = mapped_column(
        ForeignKey("themes.id", ondelete="CASCADE"), primary_key=True
    )
    signal_id: Mapped[str] = mapped_column(
        ForeignKey("signals.id", ondelete="CASCADE"), primary_key=True
    )
    relationship: Mapped[str] = mapped_column(String(30), nullable=False)


class ResearchThesisModel(Base):
    __tablename__ = "research_theses"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("discovery_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    theme_id: Mapped[str] = mapped_column(
        ForeignKey("themes.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class ResearchOpportunityModel(Base):
    __tablename__ = "research_opportunities"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("discovery_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    theme_id: Mapped[str] = mapped_column(
        ForeignKey("themes.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    thesis_id: Mapped[str] = mapped_column(
        ForeignKey("research_theses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    document: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    priority_label: Mapped[str] = mapped_column(String(20), nullable=False)
    priority_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_label: Mapped[str] = mapped_column(String(20), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    market_awareness: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
