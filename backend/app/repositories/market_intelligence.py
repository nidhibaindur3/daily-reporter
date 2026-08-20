from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models.market_intelligence import (
    ClaimDependencyModel,
    ClaimModel,
    DiscoveryRunModel,
    EvidenceModel,
    JobModel,
    ResearchOpportunityModel,
    ResearchThesisModel,
    SignalClaimModel,
    SignalModel,
    SourceModel,
    SourceSnapshotModel,
    ThemeModel,
    ThemeSignalModel,
)
from app.domain.market_intelligence import (
    MARKET_INTELLIGENCE_WORKFLOW_VERSION,
    ClaimEvidenceView,
    ClaimRecord,
    DiscoveryRun,
    EvidenceRecord,
    OpportunityRecord,
    SignalRecord,
    SourceRecord,
    SourceSnapshotRecord,
    SourceSnapshotView,
    ThemeRecord,
    ThesisRecord,
)


class MarketIntelligenceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_run(
        self,
        window_hours: int,
        maximum_themes: int,
        focus_topics: tuple[str, ...],
        max_attempts: int = 3,
    ) -> DiscoveryRun:
        now = datetime.now(timezone.utc)
        run_id = str(uuid4())
        run = DiscoveryRunModel(
            id=run_id,
            status="queued",
            current_stage="sources",
            window_hours=window_hours,
            maximum_themes=maximum_themes,
            focus_topics=list(focus_topics),
            workflow_version=MARKET_INTELLIGENCE_WORKFLOW_VERSION,
            error_code=None,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )
        job = JobModel(
            id=str(uuid4()),
            run_id=run_id,
            job_type="market_intelligence.discovery",
            status="queued",
            payload={"run_id": run_id},
            attempts=0,
            max_attempts=max_attempts,
            available_at=now,
            locked_by=None,
            locked_at=None,
            lease_expires_at=None,
            error_code=None,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )
        self._session.add_all([run, job])
        self._session.commit()
        return self._run_record(run)

    def get_run(self, run_id: str) -> Optional[DiscoveryRun]:
        model = self._session.get(DiscoveryRunModel, run_id)
        return self._run_record(model) if model is not None else None

    def advance_run(self, run_id: str, next_stage: str) -> None:
        run = self._required_run(run_id)
        run.status = "running"
        run.current_stage = next_stage
        run.error_code = None
        run.updated_at = datetime.now(timezone.utc)
        self._session.commit()

    def finish_run(self, run_id: str, status: str) -> None:
        now = datetime.now(timezone.utc)
        run = self._required_run(run_id)
        run.status = status
        run.current_stage = "done"
        run.error_code = None
        run.updated_at = now
        run.completed_at = now
        self._session.commit()

    def fail_run(self, run_id: str, error_code: str, terminal: bool) -> None:
        run = self._required_run(run_id)
        run.status = "failed" if terminal else "queued"
        run.error_code = error_code
        run.updated_at = datetime.now(timezone.utc)
        if terminal:
            run.completed_at = run.updated_at
        self._session.commit()

    def save_sources(
        self,
        sources: Iterable[SourceRecord],
        snapshots: Iterable[SourceSnapshotRecord],
    ) -> None:
        for source in sources:
            self._session.merge(
                SourceModel(
                    id=source.id,
                    publisher=source.publisher,
                    canonical_url=source.canonical_url,
                    source_class=source.source_class,
                    document_type=source.document_type,
                    authority_tier=source.authority_tier,
                    independence_group=source.independence_group,
                    discovery_only=source.discovery_only,
                    created_at=source.created_at,
                )
            )
        for snapshot in snapshots:
            self._session.merge(
                SourceSnapshotModel(
                    id=snapshot.id,
                    run_id=snapshot.run_id,
                    source_id=snapshot.source_id,
                    canonical_url=snapshot.canonical_url,
                    title=snapshot.title,
                    published_at=snapshot.published_at,
                    retrieved_at=snapshot.retrieved_at,
                    content_hash=snapshot.content_hash,
                    excerpt=snapshot.excerpt,
                    structured_data=snapshot.structured_data,
                    extraction_status=snapshot.extraction_status,
                )
            )
        self._session.commit()

    def list_snapshots(self, run_id: str) -> tuple[SourceSnapshotView, ...]:
        rows = self._session.execute(
            select(SourceSnapshotModel, SourceModel)
            .join(SourceModel, SourceModel.id == SourceSnapshotModel.source_id)
            .where(SourceSnapshotModel.run_id == run_id)
            .order_by(SourceSnapshotModel.published_at.desc())
        ).all()
        return tuple(
            SourceSnapshotView(
                snapshot=self._snapshot_record(snapshot),
                source=self._source_record(source),
            )
            for snapshot, source in rows
        )

    def replace_claims(
        self,
        run_id: str,
        claims: Iterable[ClaimRecord],
        evidence: Iterable[EvidenceRecord],
    ) -> None:
        claim_ids = select(ClaimModel.id).where(ClaimModel.run_id == run_id)
        self._session.execute(
            delete(ClaimDependencyModel).where(
                ClaimDependencyModel.parent_claim_id.in_(claim_ids)
            )
        )
        self._session.execute(
            delete(EvidenceModel).where(EvidenceModel.run_id == run_id)
        )
        self._session.execute(delete(ClaimModel).where(ClaimModel.run_id == run_id))
        for claim in claims:
            self._session.add(
                ClaimModel(
                    id=claim.id,
                    run_id=claim.run_id,
                    statement=claim.statement,
                    claim_type=claim.claim_type,
                    effective_at=claim.effective_at,
                    verification_status=claim.verification_status,
                    created_by=claim.created_by,
                    topics=list(claim.topics),
                    entities=list(claim.entities),
                )
            )
        self._session.flush()
        for item in evidence:
            self._session.add(self._evidence_model(item))
        self._session.commit()

    def add_evidence(self, items: Iterable[EvidenceRecord]) -> None:
        for item in items:
            self._session.merge(self._evidence_model(item))
        self._session.commit()

    def add_derived_claims(
        self,
        claims: Iterable[ClaimRecord],
        dependencies: Iterable[tuple[str, str, str]],
        evidence: Iterable[EvidenceRecord],
    ) -> None:
        for claim in claims:
            self._session.merge(
                ClaimModel(
                    id=claim.id,
                    run_id=claim.run_id,
                    statement=claim.statement,
                    claim_type=claim.claim_type,
                    effective_at=claim.effective_at,
                    verification_status=claim.verification_status,
                    created_by=claim.created_by,
                    topics=list(claim.topics),
                    entities=list(claim.entities),
                )
            )
        self._session.flush()
        for parent_claim_id, dependent_claim_id, relationship in dependencies:
            self._session.merge(
                ClaimDependencyModel(
                    parent_claim_id=parent_claim_id,
                    dependent_claim_id=dependent_claim_id,
                    relationship=relationship,
                )
            )
        for item in evidence:
            self._session.merge(self._evidence_model(item))
        self._session.commit()

    def list_claim_dependencies(self, run_id: str) -> tuple[tuple[str, str, str], ...]:
        claim_ids = select(ClaimModel.id).where(ClaimModel.run_id == run_id)
        models = self._session.execute(
            select(ClaimDependencyModel).where(
                ClaimDependencyModel.dependent_claim_id.in_(claim_ids)
            )
        ).scalars()
        return tuple(
            (model.parent_claim_id, model.dependent_claim_id, model.relationship)
            for model in models
        )

    def list_claims(self, run_id: str) -> tuple[ClaimRecord, ...]:
        models = self._session.execute(
            select(ClaimModel)
            .where(ClaimModel.run_id == run_id)
            .order_by(ClaimModel.effective_at.desc(), ClaimModel.id)
        ).scalars()
        return tuple(self._claim_record(model) for model in models)

    def list_claim_evidence(self, run_id: str) -> tuple[ClaimEvidenceView, ...]:
        claims = self.list_claims(run_id)
        evidence_models = tuple(
            self._session.execute(
                select(EvidenceModel).where(EvidenceModel.run_id == run_id)
            ).scalars()
        )
        snapshots = {view.snapshot.id: view for view in self.list_snapshots(run_id)}
        by_claim: dict[str, list[EvidenceRecord]] = {}
        by_claim_snapshots: dict[str, list[SourceSnapshotView]] = {}
        for model in evidence_models:
            item = self._evidence_record(model)
            by_claim.setdefault(item.claim_id, []).append(item)
            view = snapshots.get(item.source_snapshot_id)
            if view is not None:
                by_claim_snapshots.setdefault(item.claim_id, []).append(view)
        return tuple(
            ClaimEvidenceView(
                claim=claim,
                evidence=tuple(by_claim.get(claim.id, [])),
                snapshots=tuple(by_claim_snapshots.get(claim.id, [])),
            )
            for claim in claims
        )

    def replace_signals(self, run_id: str, signals: Iterable[SignalRecord]) -> None:
        records = tuple(signals)
        signal_ids = select(SignalModel.id).where(SignalModel.run_id == run_id)
        self._session.execute(
            delete(SignalClaimModel).where(SignalClaimModel.signal_id.in_(signal_ids))
        )
        self._session.execute(delete(SignalModel).where(SignalModel.run_id == run_id))
        for signal in records:
            self._session.add(
                SignalModel(
                    id=signal.id,
                    run_id=signal.run_id,
                    signal_type=signal.signal_type,
                    description=signal.description,
                    topic=signal.topic,
                    first_observed_at=signal.first_observed_at,
                    last_observed_at=signal.last_observed_at,
                    source_count=signal.source_count,
                    independent_source_count=signal.independent_source_count,
                    novelty_score=signal.novelty_score,
                    strength_score=signal.strength_score,
                    status=signal.status,
                )
            )
        self._session.flush()
        for signal in records:
            for claim_id in signal.claim_ids:
                self._session.add(
                    SignalClaimModel(
                        signal_id=signal.id,
                        claim_id=claim_id,
                        contribution="member",
                    )
                )
        self._session.commit()

    def list_signals(self, run_id: str) -> tuple[SignalRecord, ...]:
        models = tuple(
            self._session.execute(
                select(SignalModel)
                .where(SignalModel.run_id == run_id)
                .order_by(SignalModel.strength_score.desc(), SignalModel.topic)
            ).scalars()
        )
        links = (
            tuple(
                self._session.execute(
                    select(SignalClaimModel).where(
                        SignalClaimModel.signal_id.in_([model.id for model in models])
                    )
                ).scalars()
            )
            if models
            else ()
        )
        claim_ids: dict[str, list[str]] = {}
        for link in links:
            claim_ids.setdefault(link.signal_id, []).append(link.claim_id)
        return tuple(
            SignalRecord(
                id=model.id,
                run_id=model.run_id,
                signal_type=model.signal_type,
                description=model.description,
                topic=model.topic,
                first_observed_at=model.first_observed_at,
                last_observed_at=model.last_observed_at,
                source_count=model.source_count,
                independent_source_count=model.independent_source_count,
                novelty_score=model.novelty_score,
                strength_score=model.strength_score,
                status=model.status,
                claim_ids=tuple(claim_ids.get(model.id, [])),
            )
            for model in models
        )

    def replace_themes(self, run_id: str, themes: Iterable[ThemeRecord]) -> None:
        records = tuple(themes)
        theme_ids = select(ThemeModel.id).where(ThemeModel.run_id == run_id)
        self._session.execute(
            delete(ThemeSignalModel).where(ThemeSignalModel.theme_id.in_(theme_ids))
        )
        self._session.execute(delete(ThemeModel).where(ThemeModel.run_id == run_id))
        for theme in records:
            self._session.add(
                ThemeModel(
                    id=theme.id,
                    run_id=theme.run_id,
                    name=theme.name,
                    description=theme.description,
                    why_now=theme.why_now,
                    first_detected_at=theme.first_detected_at,
                    freshness_score=theme.freshness_score,
                    novelty_score=theme.novelty_score,
                    status=theme.status,
                    contradiction_review=theme.contradiction_review,
                )
            )
        self._session.flush()
        for theme in records:
            for signal_id in theme.signal_ids:
                self._session.add(
                    ThemeSignalModel(
                        theme_id=theme.id,
                        signal_id=signal_id,
                        relationship="member",
                    )
                )
        self._session.commit()

    def list_themes(self, run_id: str) -> tuple[ThemeRecord, ...]:
        models = tuple(
            self._session.execute(
                select(ThemeModel)
                .where(ThemeModel.run_id == run_id)
                .order_by(ThemeModel.freshness_score.desc(), ThemeModel.name)
            ).scalars()
        )
        links = (
            tuple(
                self._session.execute(
                    select(ThemeSignalModel).where(
                        ThemeSignalModel.theme_id.in_([model.id for model in models])
                    )
                ).scalars()
            )
            if models
            else ()
        )
        signal_ids: dict[str, list[str]] = {}
        for link in links:
            signal_ids.setdefault(link.theme_id, []).append(link.signal_id)
        return tuple(
            ThemeRecord(
                id=model.id,
                run_id=model.run_id,
                name=model.name,
                description=model.description,
                why_now=model.why_now,
                first_detected_at=model.first_detected_at,
                freshness_score=model.freshness_score,
                novelty_score=model.novelty_score,
                status=model.status,
                signal_ids=tuple(signal_ids.get(model.id, [])),
                contradiction_review=dict(model.contradiction_review),
            )
            for model in models
        )

    def save_theme_contradiction(
        self, theme_id: str, document: dict[str, object]
    ) -> None:
        theme = self._session.get(ThemeModel, theme_id)
        if theme is None:
            raise LookupError("theme not found")
        theme.contradiction_review = document
        self._session.commit()

    def save_theses(self, theses: Iterable[ThesisRecord]) -> None:
        for thesis in theses:
            self._session.merge(
                ResearchThesisModel(
                    id=thesis.id,
                    run_id=thesis.run_id,
                    theme_id=thesis.theme_id,
                    document=thesis.document,
                    status=thesis.status,
                    schema_version=thesis.schema_version,
                    created_at=thesis.created_at,
                )
            )
        self._session.commit()

    def list_theses(self, run_id: str) -> tuple[ThesisRecord, ...]:
        models = self._session.execute(
            select(ResearchThesisModel).where(ResearchThesisModel.run_id == run_id)
        ).scalars()
        return tuple(
            ThesisRecord(
                id=model.id,
                run_id=model.run_id,
                theme_id=model.theme_id,
                document=dict(model.document),
                status=model.status,
                schema_version=model.schema_version,
                created_at=model.created_at,
            )
            for model in models
        )

    def save_opportunities(self, opportunities: Iterable[OpportunityRecord]) -> None:
        for opportunity in opportunities:
            self._session.merge(
                ResearchOpportunityModel(
                    id=opportunity.id,
                    run_id=opportunity.run_id,
                    theme_id=opportunity.theme_id,
                    thesis_id=opportunity.thesis_id,
                    document=opportunity.document,
                    status=opportunity.status,
                    priority_label=opportunity.priority_label,
                    priority_score=opportunity.priority_score,
                    confidence_label=opportunity.confidence_label,
                    confidence_score=opportunity.confidence_score,
                    market_awareness=opportunity.market_awareness,
                    as_of=opportunity.as_of,
                    schema_version=opportunity.schema_version,
                    created_at=opportunity.created_at,
                )
            )
        self._session.commit()

    def list_opportunities(
        self, run_id: Optional[str] = None, limit: int = 10
    ) -> tuple[OpportunityRecord, ...]:
        statement = select(ResearchOpportunityModel)
        if run_id is not None:
            statement = statement.where(ResearchOpportunityModel.run_id == run_id)
        models = self._session.execute(
            statement.order_by(
                ResearchOpportunityModel.created_at.desc(),
                ResearchOpportunityModel.priority_score.desc(),
            ).limit(limit)
        ).scalars()
        return tuple(self._opportunity_record(model) for model in models)

    def get_opportunity(self, opportunity_id: str) -> Optional[OpportunityRecord]:
        model = self._session.get(ResearchOpportunityModel, opportunity_id)
        return self._opportunity_record(model) if model is not None else None

    def _required_run(self, run_id: str) -> DiscoveryRunModel:
        run = self._session.get(DiscoveryRunModel, run_id)
        if run is None:
            raise LookupError("discovery run not found")
        return run

    @staticmethod
    def _run_record(model: DiscoveryRunModel) -> DiscoveryRun:
        return DiscoveryRun(
            id=model.id,
            status=model.status,
            current_stage=model.current_stage,
            window_hours=model.window_hours,
            maximum_themes=model.maximum_themes,
            focus_topics=tuple(model.focus_topics),
            workflow_version=model.workflow_version,
            error_code=model.error_code,
            created_at=model.created_at,
            updated_at=model.updated_at,
            completed_at=model.completed_at,
        )

    @staticmethod
    def _source_record(model: SourceModel) -> SourceRecord:
        return SourceRecord(
            id=model.id,
            publisher=model.publisher,
            canonical_url=model.canonical_url,
            source_class=model.source_class,  # type: ignore[arg-type]
            document_type=model.document_type,
            authority_tier=model.authority_tier,
            independence_group=model.independence_group,
            discovery_only=model.discovery_only,
            created_at=model.created_at,
        )

    @staticmethod
    def _snapshot_record(model: SourceSnapshotModel) -> SourceSnapshotRecord:
        return SourceSnapshotRecord(
            id=model.id,
            run_id=model.run_id,
            source_id=model.source_id,
            canonical_url=model.canonical_url,
            title=model.title,
            published_at=model.published_at,
            retrieved_at=model.retrieved_at,
            content_hash=model.content_hash,
            excerpt=model.excerpt,
            structured_data=dict(model.structured_data),
            extraction_status=model.extraction_status,
        )

    @staticmethod
    def _claim_record(model: ClaimModel) -> ClaimRecord:
        return ClaimRecord(
            id=model.id,
            run_id=model.run_id,
            statement=model.statement,
            claim_type=model.claim_type,  # type: ignore[arg-type]
            effective_at=model.effective_at,
            verification_status=model.verification_status,
            created_by=model.created_by,
            topics=tuple(model.topics),
            entities=tuple(model.entities),
        )

    @staticmethod
    def _evidence_model(item: EvidenceRecord) -> EvidenceModel:
        return EvidenceModel(
            id=item.id,
            run_id=item.run_id,
            claim_id=item.claim_id,
            source_snapshot_id=item.source_snapshot_id,
            relationship=item.relationship,
            passage=item.passage,
            location=item.location,
            extraction_method=item.extraction_method,
            verification_status=item.verification_status,
        )

    @staticmethod
    def _evidence_record(model: EvidenceModel) -> EvidenceRecord:
        return EvidenceRecord(
            id=model.id,
            run_id=model.run_id,
            claim_id=model.claim_id,
            source_snapshot_id=model.source_snapshot_id,
            relationship=model.relationship,  # type: ignore[arg-type]
            passage=model.passage,
            location=model.location,
            extraction_method=model.extraction_method,
            verification_status=model.verification_status,
        )

    @staticmethod
    def _opportunity_record(model: ResearchOpportunityModel) -> OpportunityRecord:
        return OpportunityRecord(
            id=model.id,
            run_id=model.run_id,
            theme_id=model.theme_id,
            thesis_id=model.thesis_id,
            document=dict(model.document),
            status=model.status,
            priority_label=model.priority_label,
            priority_score=model.priority_score,
            confidence_label=model.confidence_label,
            confidence_score=model.confidence_score,
            market_awareness=dict(model.market_awareness),
            as_of=model.as_of,
            schema_version=model.schema_version,
            created_at=model.created_at,
        )
