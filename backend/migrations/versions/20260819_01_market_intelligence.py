"""Create the Market Intelligence provenance pipeline tables.

Revision ID: 20260819_01
Revises:
Create Date: 2026-08-19
"""

from collections.abc import Sequence
from typing import Optional

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260819_01"
down_revision: Optional[str] = None
branch_labels: Optional[Sequence[str]] = None
depends_on: Optional[Sequence[str]] = None


def upgrade() -> None:
    op.create_table(
        "discovery_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("current_stage", sa.String(length=40), nullable=False),
        sa.Column("window_hours", sa.Integer(), nullable=False),
        sa.Column("maximum_themes", sa.Integer(), nullable=False),
        sa.Column("focus_topics", postgresql.JSONB(), nullable=False),
        sa.Column("workflow_version", sa.String(length=80), nullable=False),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_discovery_runs_status", "discovery_runs", ["status"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_by", sa.String(length=120), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["discovery_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_available_at", "jobs", ["available_at"])
    op.create_index("ix_jobs_lease_expires_at", "jobs", ["lease_expires_at"])
    op.create_index(
        "ix_jobs_claimable",
        "jobs",
        ["status", "available_at", "lease_expires_at"],
    )

    op.create_table(
        "sources",
        sa.Column("id", sa.String(length=120), nullable=False),
        sa.Column("publisher", sa.String(length=240), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("source_class", sa.String(length=30), nullable=False),
        sa.Column("document_type", sa.String(length=50), nullable=False),
        sa.Column("authority_tier", sa.String(length=40), nullable=False),
        sa.Column("independence_group", sa.String(length=160), nullable=False),
        sa.Column("discovery_only", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "source_snapshots",
        sa.Column("id", sa.String(length=120), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=120), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("structured_data", postgresql.JSONB(), nullable=False),
        sa.Column("extraction_status", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["discovery_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "content_hash", name="uq_snapshot_run_hash"),
    )
    op.create_index("ix_source_snapshots_run_id", "source_snapshots", ["run_id"])
    op.create_index("ix_source_snapshots_source_id", "source_snapshots", ["source_id"])

    op.create_table(
        "claims",
        sa.Column("id", sa.String(length=120), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("claim_type", sa.String(length=30), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verification_status", sa.String(length=30), nullable=False),
        sa.Column("created_by", sa.String(length=30), nullable=False),
        sa.Column("topics", postgresql.JSONB(), nullable=False),
        sa.Column("entities", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["discovery_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_claims_run_id", "claims", ["run_id"])

    op.create_table(
        "claim_dependencies",
        sa.Column("parent_claim_id", sa.String(length=120), nullable=False),
        sa.Column("dependent_claim_id", sa.String(length=120), nullable=False),
        sa.Column("relationship", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(
            ["dependent_claim_id"], ["claims.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["parent_claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("parent_claim_id", "dependent_claim_id"),
    )

    op.create_table(
        "evidence",
        sa.Column("id", sa.String(length=120), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("claim_id", sa.String(length=120), nullable=False),
        sa.Column("source_snapshot_id", sa.String(length=120), nullable=False),
        sa.Column("relationship", sa.String(length=30), nullable=False),
        sa.Column("passage", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=120), nullable=False),
        sa.Column("extraction_method", sa.String(length=40), nullable=False),
        sa.Column("verification_status", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["discovery_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_snapshot_id"], ["source_snapshots.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "claim_id",
            "source_snapshot_id",
            "relationship",
            name="uq_evidence_claim_snapshot_relationship",
        ),
    )
    op.create_index("ix_evidence_run_id", "evidence", ["run_id"])
    op.create_index("ix_evidence_claim_id", "evidence", ["claim_id"])
    op.create_index(
        "ix_evidence_source_snapshot_id", "evidence", ["source_snapshot_id"]
    )

    op.create_table(
        "signals",
        sa.Column("id", sa.String(length=120), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("signal_type", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("topic", sa.String(length=160), nullable=False),
        sa.Column("first_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_count", sa.Integer(), nullable=False),
        sa.Column("independent_source_count", sa.Integer(), nullable=False),
        sa.Column("novelty_score", sa.Float(), nullable=False),
        sa.Column("strength_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["discovery_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signals_run_id", "signals", ["run_id"])

    op.create_table(
        "signal_claims",
        sa.Column("signal_id", sa.String(length=120), nullable=False),
        sa.Column("claim_id", sa.String(length=120), nullable=False),
        sa.Column("contribution", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("signal_id", "claim_id"),
    )

    op.create_table(
        "themes",
        sa.Column("id", sa.String(length=120), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("why_now", sa.Text(), nullable=False),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("freshness_score", sa.Float(), nullable=False),
        sa.Column("novelty_score", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("contradiction_review", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["discovery_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_themes_run_id", "themes", ["run_id"])

    op.create_table(
        "theme_signals",
        sa.Column("theme_id", sa.String(length=120), nullable=False),
        sa.Column("signal_id", sa.String(length=120), nullable=False),
        sa.Column("relationship", sa.String(length=30), nullable=False),
        sa.ForeignKeyConstraint(["signal_id"], ["signals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("theme_id", "signal_id"),
    )

    op.create_table(
        "research_theses",
        sa.Column("id", sa.String(length=120), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("theme_id", sa.String(length=120), nullable=False),
        sa.Column("document", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("schema_version", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["discovery_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("theme_id"),
    )
    op.create_index("ix_research_theses_run_id", "research_theses", ["run_id"])

    op.create_table(
        "research_opportunities",
        sa.Column("id", sa.String(length=120), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("theme_id", sa.String(length=120), nullable=False),
        sa.Column("thesis_id", sa.String(length=120), nullable=False),
        sa.Column("document", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("priority_label", sa.String(length=20), nullable=False),
        sa.Column("priority_score", sa.Float(), nullable=False),
        sa.Column("confidence_label", sa.String(length=20), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("market_awareness", postgresql.JSONB(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["discovery_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["theme_id"], ["themes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["thesis_id"], ["research_theses.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("theme_id"),
        sa.UniqueConstraint("thesis_id"),
    )
    op.create_index(
        "ix_research_opportunities_run_id", "research_opportunities", ["run_id"]
    )


def downgrade() -> None:
    op.drop_table("research_opportunities")
    op.drop_table("research_theses")
    op.drop_table("theme_signals")
    op.drop_table("themes")
    op.drop_table("signal_claims")
    op.drop_table("signals")
    op.drop_table("evidence")
    op.drop_table("claim_dependencies")
    op.drop_table("claims")
    op.drop_table("source_snapshots")
    op.drop_table("sources")
    op.drop_table("jobs")
    op.drop_table("discovery_runs")
