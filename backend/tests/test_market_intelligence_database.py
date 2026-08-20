import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete, inspect

from app.db.models.market_intelligence import (
    ClaimModel,
    DiscoveryRunModel,
    JobModel,
)
from app.db.session import SessionLocal
from app.domain.market_intelligence import ClaimRecord, SignalRecord, ThemeRecord
from app.repositories.jobs import JobRepository
from app.repositories.market_intelligence import MarketIntelligenceRepository

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_DATABASE_TESTS") != "1",
    reason="requires migrated PostgreSQL",
)


def test_provenance_constraints_exist() -> None:
    with SessionLocal() as session:
        inspector = inspect(session.bind)
        evidence_constraints = {
            item["name"] for item in inspector.get_check_constraints("evidence")
        }
        claim_constraints = {
            item["name"] for item in inspector.get_check_constraints("claims")
        }

    assert "ck_evidence_relationship" in evidence_constraints
    assert "ck_claims_claim_type" in claim_constraints


def test_postgres_job_claim_retry_and_terminal_failure() -> None:
    run_id = ""
    try:
        with SessionLocal() as session:
            run = MarketIntelligenceRepository(session).create_run(
                window_hours=48,
                maximum_themes=3,
                focus_topics=(),
            )
            run_id = run.id

        with SessionLocal() as session:
            jobs = JobRepository(session)
            first = jobs.claim_next(
                "test-worker",
                lease_seconds=60,
                run_id=run_id,
            )
            assert first is not None
            assert first.run_id == run_id
            assert first.attempts == 1
            assert first.job_type == "market_intelligence.discovery"
            assert jobs.fail(first.id, "retryable_test", retry_delay_seconds=0) is False

        with SessionLocal() as session:
            jobs = JobRepository(session)
            second = jobs.claim_next(
                "test-worker",
                lease_seconds=60,
                run_id=run_id,
            )
            assert second is not None
            assert second.id == first.id
            assert second.attempts == 2
            assert (
                jobs.fail(
                    second.id,
                    "terminal_test",
                    retry_delay_seconds=0,
                    force_terminal=True,
                )
                is True
            )
            MarketIntelligenceRepository(session).fail_run(
                run_id,
                "terminal_test",
                terminal=True,
            )
            job = session.get(JobModel, second.id)
            assert job is not None
            assert job.status == "failed"
            assert (
                MarketIntelligenceRepository(session).get_run(run_id).status == "failed"
            )
    finally:
        if run_id:
            with SessionLocal() as session:
                session.execute(
                    delete(DiscoveryRunModel).where(DiscoveryRunModel.id == run_id)
                )
                session.commit()


def test_signal_and_theme_links_are_inserted_after_their_parents() -> None:
    run_id = ""
    now = datetime.now(timezone.utc)
    try:
        with SessionLocal() as session:
            repository = MarketIntelligenceRepository(session)
            run = repository.create_run(
                window_hours=48,
                maximum_themes=3,
                focus_topics=(),
            )
            run_id = run.id
            session.add(
                ClaimModel(
                    id=f"claim:{run_id}",
                    run_id=run_id,
                    statement="A source-grounded test claim.",
                    claim_type="fact",
                    effective_at=now,
                    verification_status="source_grounded",
                    created_by="test",
                    topics=["test topic"],
                    entities=[],
                )
            )
            session.commit()

            derived_claim = ClaimRecord(
                id=f"derived:{run_id}",
                run_id=run_id,
                statement="A traceable test inference.",
                claim_type="inference",
                effective_at=now,
                verification_status="premise_grounded",
                created_by="test",
                topics=("test topic",),
                entities=(),
            )
            repository.add_derived_claims(
                (derived_claim,),
                ((f"claim:{run_id}", derived_claim.id, "premise"),),
                (),
            )
            assert repository.list_claim_dependencies(run_id) == (
                (f"claim:{run_id}", derived_claim.id, "premise"),
            )

            signal = SignalRecord(
                id=f"signal:{run_id}",
                run_id=run_id,
                signal_type="source_observation",
                description="A test signal.",
                topic="test topic",
                first_observed_at=now,
                last_observed_at=now,
                source_count=1,
                independent_source_count=1,
                novelty_score=1.0,
                strength_score=1.0,
                status="candidate",
                claim_ids=(f"claim:{run_id}",),
            )
            repository.replace_signals(run_id, (signal,))

            theme = ThemeRecord(
                id=f"theme:{run_id}",
                run_id=run_id,
                name="Test theme",
                description="A test theme description.",
                why_now="The test signal is current.",
                first_detected_at=now,
                freshness_score=1.0,
                novelty_score=1.0,
                status="candidate",
                signal_ids=(signal.id,),
                contradiction_review={},
            )
            repository.replace_themes(run_id, (theme,))

            assert repository.list_signals(run_id) == (signal,)
            assert repository.list_themes(run_id) == (theme,)
    finally:
        if run_id:
            with SessionLocal() as session:
                session.execute(
                    delete(DiscoveryRunModel).where(DiscoveryRunModel.id == run_id)
                )
                session.commit()
