"""Add provenance and lifecycle check constraints.

Revision ID: 20260819_02
Revises: 20260819_01
Create Date: 2026-08-19
"""

from collections.abc import Sequence
from typing import Optional

from alembic import op

revision: str = "20260819_02"
down_revision: Optional[str] = "20260819_01"
branch_labels: Optional[Sequence[str]] = None
depends_on: Optional[Sequence[str]] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_discovery_runs_status",
        "discovery_runs",
        "status IN ('queued', 'running', 'complete', 'incomplete', "
        "'failed', 'cancelled')",
    )
    op.create_check_constraint(
        "ck_jobs_status",
        "jobs",
        "status IN ('queued', 'running', 'complete', 'failed')",
    )
    op.create_check_constraint(
        "ck_sources_source_class",
        "sources",
        "source_class IN ('primary_evidence', 'reporting', 'discovery')",
    )
    op.create_check_constraint(
        "ck_claims_claim_type",
        "claims",
        "claim_type IN ('fact', 'signal', 'inference', 'research_hypothesis')",
    )
    op.create_check_constraint(
        "ck_claim_dependencies_relationship",
        "claim_dependencies",
        "relationship IN ('premise')",
    )
    op.create_check_constraint(
        "ck_evidence_relationship",
        "evidence",
        "relationship IN ('supports', 'contradicts', 'contextualizes')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_evidence_relationship",
        "evidence",
        type_="check",
    )
    op.drop_constraint(
        "ck_claim_dependencies_relationship",
        "claim_dependencies",
        type_="check",
    )
    op.drop_constraint(
        "ck_claims_claim_type",
        "claims",
        type_="check",
    )
    op.drop_constraint(
        "ck_sources_source_class",
        "sources",
        type_="check",
    )
    op.drop_constraint("ck_jobs_status", "jobs", type_="check")
    op.drop_constraint(
        "ck_discovery_runs_status",
        "discovery_runs",
        type_="check",
    )
