import hashlib
import json
import logging
from collections import defaultdict
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Optional, Protocol

from app.ai.contracts import (
    AIInvalidOutputError,
    AINotConfiguredError,
    AIProviderError,
)
from app.ai.market_intelligence_contracts import (
    AffectedAreaDraft,
    CitedDraft,
    ContradictionReview,
    MarketIntelligenceModel,
    ThemeDraft,
    ThemeFormation,
    ThesisDraft,
)
from app.ai.market_intelligence_validation import (
    MarketIntelligenceValidationError,
    sanitize_claim_extraction,
    sanitize_contradiction_review,
    sanitize_theme_formation,
    sanitize_thesis_draft,
    validate_claim_extraction,
    validate_contradiction_review,
    validate_theme_formation,
    validate_thesis_draft,
)
from app.domain.market import MarketSnapshot
from app.domain.market_intelligence import (
    RESEARCH_OPPORTUNITY_SCHEMA_VERSION,
    RESEARCH_THESIS_SCHEMA_VERSION,
    ClaimEvidenceView,
    ClaimRecord,
    DiscoveryRun,
    EvidenceRecord,
    OpportunityProvenance,
    OpportunityRecord,
    SignalRecord,
    SourceRecord,
    SourceSnapshotRecord,
    SourceSnapshotView,
    ThemeRecord,
    ThesisRecord,
    stable_record_id,
)
from app.domain.news import NewsArticle, NewsSnapshot
from app.domain.source_quality import source_authority_score
from app.repositories.market_intelligence import MarketIntelligenceRepository
from app.services.market import MarketService, MarketUnavailableError
from app.services.news import NewsService, NewsUnavailableError

logger = logging.getLogger(__name__)

_GENERIC_TOPICS = {
    "ai",
    "artificial intelligence",
    "business",
    "company",
    "markets",
    "news",
    "software",
    "technology",
    "world",
}


class MarketIntelligenceUnavailableError(RuntimeError):
    """Raised when a discovery command cannot be accepted or read."""


class MarketIntelligenceNotConfiguredError(MarketIntelligenceUnavailableError):
    """Raised when the model credential required by the worker is missing."""


class MarketIntelligencePipelineError(RuntimeError):
    def __init__(self, error_code: str, retryable: bool = True) -> None:
        self.error_code = error_code
        self.retryable = retryable
        super().__init__(error_code)


class PipelineStore(Protocol):
    def get_run(self, run_id: str) -> Optional[DiscoveryRun]: ...

    def advance_run(self, run_id: str, next_stage: str) -> None: ...

    def finish_run(self, run_id: str, status: str) -> None: ...

    def save_sources(
        self,
        sources: Iterable[SourceRecord],
        snapshots: Iterable[SourceSnapshotRecord],
    ) -> None: ...

    def list_snapshots(self, run_id: str) -> tuple[SourceSnapshotView, ...]: ...

    def replace_claims(
        self,
        run_id: str,
        claims: Iterable[ClaimRecord],
        evidence: Iterable[EvidenceRecord],
    ) -> None: ...

    def add_evidence(self, items: Iterable[EvidenceRecord]) -> None: ...

    def add_derived_claims(
        self,
        claims: Iterable[ClaimRecord],
        dependencies: Iterable[tuple[str, str, str]],
        evidence: Iterable[EvidenceRecord],
    ) -> None: ...

    def list_claims(self, run_id: str) -> tuple[ClaimRecord, ...]: ...

    def list_claim_evidence(self, run_id: str) -> tuple[ClaimEvidenceView, ...]: ...

    def replace_signals(self, run_id: str, signals: Iterable[SignalRecord]) -> None: ...

    def list_signals(self, run_id: str) -> tuple[SignalRecord, ...]: ...

    def replace_themes(self, run_id: str, themes: Iterable[ThemeRecord]) -> None: ...

    def list_themes(self, run_id: str) -> tuple[ThemeRecord, ...]: ...

    def save_theme_contradiction(
        self, theme_id: str, document: dict[str, object]
    ) -> None: ...

    def save_theses(self, theses: Iterable[ThesisRecord]) -> None: ...

    def list_theses(self, run_id: str) -> tuple[ThesisRecord, ...]: ...

    def save_opportunities(
        self, opportunities: Iterable[OpportunityRecord]
    ) -> None: ...


class MarketIntelligenceService:
    def __init__(
        self,
        repository: MarketIntelligenceRepository,
        enabled: bool,
        maximum_themes_limit: int,
    ) -> None:
        self._repository = repository
        self._enabled = enabled
        self._maximum_themes_limit = maximum_themes_limit

    def start_run(
        self,
        window_hours: int,
        maximum_themes: int,
        focus_topics: tuple[str, ...],
    ) -> DiscoveryRun:
        if not self._enabled:
            raise MarketIntelligenceNotConfiguredError(
                "market intelligence model is not configured"
            )
        if maximum_themes > self._maximum_themes_limit:
            raise ValueError("maximum themes exceeds configured limit")
        return self._repository.create_run(
            window_hours=window_hours,
            maximum_themes=maximum_themes,
            focus_topics=focus_topics,
        )

    def get_run(self, run_id: str) -> DiscoveryRun:
        run = self._repository.get_run(run_id)
        if run is None:
            raise LookupError("market intelligence run not found")
        return run

    def list_opportunities(
        self, run_id: Optional[str] = None, limit: int = 10
    ) -> tuple[OpportunityRecord, ...]:
        return self._repository.list_opportunities(run_id, limit)

    def get_opportunity(self, opportunity_id: str) -> OpportunityRecord:
        opportunity = self._repository.get_opportunity(opportunity_id)
        if opportunity is None:
            raise LookupError("research opportunity not found")
        return opportunity

    def sources_for_opportunity(
        self, opportunity: OpportunityRecord
    ) -> tuple[SourceSnapshotView, ...]:
        source_ids = set(opportunity.document.get("source_ids", []))
        return tuple(
            view
            for view in self._repository.list_snapshots(opportunity.run_id)
            if view.snapshot.id in source_ids
        )

    def get_provenance(self, opportunity_id: str) -> OpportunityProvenance:
        opportunity = self.get_opportunity(opportunity_id)
        themes = {
            theme.id: theme
            for theme in self._repository.list_themes(opportunity.run_id)
        }
        theme = themes[opportunity.theme_id]
        signals = tuple(
            signal
            for signal in self._repository.list_signals(opportunity.run_id)
            if signal.id in theme.signal_ids
        )
        theses = tuple(
            thesis
            for thesis in self._repository.list_theses(opportunity.run_id)
            if thesis.id == opportunity.thesis_id
        )
        conclusion_claim_ids = {
            str(claim_id)
            for thesis in theses
            for claim_id in dict(
                thesis.document.get("conclusion_claim_ids", {})
            ).values()
        }
        dependencies = tuple(
            dependency
            for dependency in self._repository.list_claim_dependencies(
                opportunity.run_id
            )
            if dependency[1] in conclusion_claim_ids
        )
        relevant_claim_ids = conclusion_claim_ids | {
            claim_id for signal in signals for claim_id in signal.claim_ids
        }
        relevant_claim_ids.update(parent for parent, _, _ in dependencies)
        claim_views = tuple(
            view
            for view in self._repository.list_claim_evidence(opportunity.run_id)
            if view.claim.id in relevant_claim_ids
        )
        evidence = tuple(item for view in claim_views for item in view.evidence)
        source_snapshot_ids = {item.source_snapshot_id for item in evidence}
        return OpportunityProvenance(
            opportunity=opportunity,
            sources=tuple(
                view
                for view in self._repository.list_snapshots(opportunity.run_id)
                if view.snapshot.id in source_snapshot_ids
            ),
            claims=tuple(view.claim for view in claim_views),
            evidence=evidence,
            claim_dependencies=dependencies,
            signals=signals,
            themes=(theme,),
            theses=theses,
        )


class MarketIntelligencePipeline:
    def __init__(
        self,
        store: PipelineStore,
        news_service: NewsService,
        market_service: MarketService,
        model: MarketIntelligenceModel,
        source_limit: int,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._store = store
        self._news_service = news_service
        self._market_service = market_service
        self._model = model
        self._source_limit = source_limit
        self._now = now

    def run(self, run_id: str) -> None:
        while True:
            run = self._store.get_run(run_id)
            if run is None:
                raise MarketIntelligencePipelineError("run_not_found", retryable=False)
            stage = run.current_stage
            if stage == "sources":
                self._stage_sources(run)
            elif stage == "claims":
                self._stage_claims(run)
            elif stage == "signals":
                self._stage_signals(run)
            elif stage == "themes":
                self._stage_themes(run)
            elif stage == "evidence":
                self._stage_evidence(run)
            elif stage == "contradictions":
                self._stage_contradictions(run)
            elif stage == "theses":
                self._stage_theses(run)
            elif stage == "opportunities":
                self._stage_opportunities(run)
            elif stage == "done":
                return
            else:
                raise MarketIntelligencePipelineError(
                    "unknown_pipeline_stage", retryable=False
                )

    def _stage_sources(self, run: DiscoveryRun) -> None:
        try:
            news = self._news_service.get_latest()
            market = self._market_service.get_watchlist()
        except (NewsUnavailableError, MarketUnavailableError) as exc:
            raise MarketIntelligencePipelineError("source_collection_failed") from exc

        sources, snapshots = self._source_records(run, news, market)
        if not snapshots:
            raise MarketIntelligencePipelineError("no_current_sources", retryable=False)
        self._store.save_sources(sources, snapshots)
        self._store.advance_run(run.id, "claims")

    def _stage_claims(self, run: DiscoveryRun) -> None:
        snapshots = self._store.list_snapshots(run.id)
        news_snapshots = tuple(
            view for view in snapshots if view.source.document_type != "market_data"
        )
        if not news_snapshots:
            raise MarketIntelligencePipelineError("no_news_sources", retryable=False)
        packet = {
            "source_snapshots": [self._snapshot_packet(view) for view in news_snapshots]
        }
        try:
            extraction = self._model.extract_claims(packet)
            raw_claim_count = len(extraction.claims)
            raw_entity_count = sum(len(claim.entities) for claim in extraction.claims)
            extraction = sanitize_claim_extraction(extraction, news_snapshots)
            validate_claim_extraction(extraction, news_snapshots)
            logger.info(
                "market_intelligence_claims_validated accepted=%d rejected=%d "
                "entities_removed=%d",
                len(extraction.claims),
                raw_claim_count - len(extraction.claims),
                raw_entity_count
                - sum(len(claim.entities) for claim in extraction.claims),
            )
        except (AINotConfiguredError, AIProviderError) as exc:
            raise MarketIntelligencePipelineError("claim_model_unavailable") from exc
        except AIInvalidOutputError as exc:
            logger.warning(
                "market_intelligence_claim_validation_failed reasons=schema_or_parse"
            )
            raise MarketIntelligencePipelineError("claim_output_invalid") from exc
        except MarketIntelligenceValidationError as exc:
            logger.warning(
                "market_intelligence_claim_validation_failed reasons=%s",
                ",".join(exc.reason_codes),
            )
            raise MarketIntelligencePipelineError("claim_output_invalid") from exc

        snapshot_by_id = {view.snapshot.id: view for view in snapshots}
        claims: list[ClaimRecord] = []
        evidence: list[EvidenceRecord] = []
        per_snapshot_index: dict[str, int] = defaultdict(int)
        for draft in extraction.claims:
            view = snapshot_by_id[draft.source_snapshot_id]
            index = per_snapshot_index[draft.source_snapshot_id]
            per_snapshot_index[draft.source_snapshot_id] += 1
            claim_id = stable_record_id(
                "claim", run.id, draft.source_snapshot_id, index
            )
            verification = (
                "discovery_only" if view.source.discovery_only else "source_grounded"
            )
            claims.append(
                ClaimRecord(
                    id=claim_id,
                    run_id=run.id,
                    statement=draft.statement,
                    claim_type="fact",
                    effective_at=view.snapshot.published_at,
                    verification_status=verification,
                    created_by="model",
                    topics=tuple(draft.topics),
                    entities=tuple(draft.entities),
                )
            )
            evidence.append(
                self._supporting_evidence(
                    run.id,
                    claim_id,
                    view,
                    extraction_method="model_extraction",
                )
            )

        for view in snapshots:
            if view.source.document_type != "market_data":
                continue
            data = view.snapshot.structured_data
            symbol = str(data["symbol"])
            statement = (
                f"{symbol} was observed at {data['current_price']} {data['currency']} "
                f"with a previous close of {data['previous_close']} {data['currency']}."
            )
            claim_id = stable_record_id("claim", run.id, view.snapshot.id, "market")
            claims.append(
                ClaimRecord(
                    id=claim_id,
                    run_id=run.id,
                    statement=statement,
                    claim_type="fact",
                    effective_at=view.snapshot.published_at,
                    verification_status="provider_grounded",
                    created_by="deterministic",
                    topics=(symbol.lower(), "public markets"),
                    entities=(symbol.lower(),),
                )
            )
            evidence.append(
                self._supporting_evidence(
                    run.id,
                    claim_id,
                    view,
                    extraction_method="provider_structured_data",
                )
            )

        self._store.replace_claims(run.id, claims, evidence)
        self._store.advance_run(run.id, "signals")

    def _stage_signals(self, run: DiscoveryRun) -> None:
        views = self._store.list_claim_evidence(run.id)
        topic_claims: dict[str, list[ClaimEvidenceView]] = defaultdict(list)
        for view in views:
            if (
                view.claim.created_by == "model"
                or view.claim.created_by == "deterministic"
            ):
                for topic in view.claim.topics:
                    normalized = " ".join(topic.lower().split())
                    if normalized and normalized not in _GENERIC_TOPICS:
                        topic_claims[normalized].append(view)

        signals: list[SignalRecord] = []
        for topic, members in topic_claims.items():
            independent_groups = {
                snapshot.source.independence_group
                for member in members
                for snapshot in member.snapshots
            }
            source_ids = {
                snapshot.source.id
                for member in members
                for snapshot in member.snapshots
            }
            claim_ids = tuple(dict.fromkeys(member.claim.id for member in members))
            observed_at = [member.claim.effective_at for member in members]
            focus_bonus = (
                0.1 if any(focus in topic for focus in run.focus_topics) else 0.0
            )
            is_convergence = len(independent_groups) >= 2
            base_strength = 0.5 if is_convergence else 0.2
            strength = min(
                1.0,
                base_strength
                + 0.1 * max(0, len(independent_groups) - 2)
                + 0.05 * max(0, len(claim_ids) - 2)
                + focus_bonus,
            )
            signals.append(
                SignalRecord(
                    id=stable_record_id("signal", run.id, topic),
                    run_id=run.id,
                    signal_type=(
                        "cross_source_convergence"
                        if is_convergence
                        else "source_observation"
                    ),
                    description=(
                        f"Multiple independent sources connect to the topic: {topic}."
                        if is_convergence
                        else f"A source observation connects to the topic: {topic}."
                    ),
                    topic=topic,
                    first_observed_at=min(observed_at),
                    last_observed_at=max(observed_at),
                    source_count=len(source_ids),
                    independent_source_count=len(independent_groups),
                    novelty_score=0.5,
                    strength_score=round(strength, 4),
                    status="candidate" if is_convergence else "discovery",
                    claim_ids=claim_ids,
                )
            )
        signals.sort(key=lambda signal: signal.strength_score, reverse=True)
        self._store.replace_signals(run.id, signals[:12])
        self._store.advance_run(run.id, "themes")

    def _stage_themes(self, run: DiscoveryRun) -> None:
        signals = self._store.list_signals(run.id)
        if not signals:
            self._store.replace_themes(run.id, ())
            self._store.advance_run(run.id, "evidence")
            return
        claims = {claim.id: claim for claim in self._store.list_claims(run.id)}
        claim_views = {
            view.claim.id: view for view in self._store.list_claim_evidence(run.id)
        }
        packet = {
            "maximum_themes": run.maximum_themes,
            "selection_mode": "standard",
            "signals": [
                {
                    "signal_id": signal.id,
                    "signal_type": signal.signal_type,
                    "description": signal.description,
                    "topic": signal.topic,
                    "independent_source_count": signal.independent_source_count,
                    "source_group_ids": sorted(
                        {
                            snapshot.source.independence_group
                            for claim_id in signal.claim_ids
                            for snapshot in claim_views[claim_id].snapshots
                        }
                    ),
                    "strength_score": signal.strength_score,
                    "claim_ids": list(signal.claim_ids),
                    "claims": [
                        claims[claim_id].statement for claim_id in signal.claim_ids
                    ],
                }
                for signal in signals
            ],
        }
        try:
            source_group_ids = {
                group_id
                for signal in packet["signals"]
                if isinstance(signal, dict)
                for group_id in signal["source_group_ids"]
            }
            attempt_packets = [packet]
            if len(source_group_ids) >= 2:
                attempt_packets.append(
                    {
                        **packet,
                        "selection_mode": "exploratory_retry",
                        "retry_guidance": (
                            "The first pass produced no accepted theme. Select the "
                            "strongest plausible research hypothesis that spans at "
                            "least two source_group_ids. Present uncertainty "
                            "explicitly."
                        ),
                    }
                )

            output = ThemeFormation(themes=[])
            raw_theme_count = 0
            for attempt_number, attempt_packet in enumerate(attempt_packets, start=1):
                candidate = self._model.form_themes(attempt_packet)
                raw_theme_count += len(candidate.themes)
                candidate = sanitize_theme_formation(
                    candidate,
                    signals,
                    run.maximum_themes,
                )
                validate_theme_formation(candidate, signals, run.maximum_themes)
                output = ThemeFormation(
                    themes=self._themes_with_source_breadth(
                        candidate.themes,
                        signals,
                        run.id,
                    )
                )
                if output.themes:
                    break
                if attempt_number < len(attempt_packets):
                    logger.info("market_intelligence_theme_retry reason=no_theme")
            logger.info(
                "market_intelligence_themes_validated accepted=%d rejected=%d",
                len(output.themes),
                raw_theme_count - len(output.themes),
            )
        except (AINotConfiguredError, AIProviderError) as exc:
            raise MarketIntelligencePipelineError("theme_model_unavailable") from exc
        except AIInvalidOutputError as exc:
            logger.warning(
                "market_intelligence_theme_validation_failed reasons=schema_or_parse"
            )
            raise MarketIntelligencePipelineError("theme_output_invalid") from exc
        except MarketIntelligenceValidationError as exc:
            logger.warning(
                "market_intelligence_theme_validation_failed reasons=%s",
                ",".join(exc.reason_codes),
            )
            raise MarketIntelligencePipelineError("theme_output_invalid") from exc

        signal_by_id = {signal.id: signal for signal in signals}
        now = self._now()
        themes = []
        for index, draft in enumerate(output.themes):
            members = [signal_by_id[signal_id] for signal_id in draft.signal_ids]
            age_hours = min(
                (now - signal.last_observed_at).total_seconds() / 3600
                for signal in members
            )
            freshness = max(0.0, 1.0 - age_hours / run.window_hours)
            themes.append(
                ThemeRecord(
                    id=stable_record_id("theme", run.id, index),
                    run_id=run.id,
                    name=draft.name,
                    description=draft.description,
                    why_now=draft.why_now,
                    first_detected_at=now,
                    freshness_score=round(freshness, 4),
                    novelty_score=round(
                        mean(item.novelty_score for item in members), 4
                    ),
                    status="candidate",
                    signal_ids=tuple(draft.signal_ids),
                    contradiction_review={},
                )
            )
        self._store.replace_themes(run.id, themes)
        self._store.advance_run(run.id, "evidence")

    def _themes_with_source_breadth(
        self,
        drafts: Iterable[ThemeDraft],
        signals: tuple[SignalRecord, ...],
        run_id: str,
    ) -> list[ThemeDraft]:
        signals_by_id = {signal.id: signal for signal in signals}
        views = {
            view.claim.id: view for view in self._store.list_claim_evidence(run_id)
        }
        accepted = []
        for draft in drafts:
            signal_ids = draft.signal_ids
            independence_groups = {
                snapshot.source.independence_group
                for signal_id in signal_ids
                for claim_id in signals_by_id[signal_id].claim_ids
                for snapshot in views[claim_id].snapshots
            }
            if len(independence_groups) >= 2:
                accepted.append(draft)
        return accepted

    def _stage_evidence(self, run: DiscoveryRun) -> None:
        views = self._store.list_claim_evidence(run.id)
        if any(not view.evidence for view in views):
            raise MarketIntelligencePipelineError(
                "claim_without_evidence", retryable=False
            )
        self._store.advance_run(run.id, "contradictions")

    def _stage_contradictions(self, run: DiscoveryRun) -> None:
        themes = self._store.list_themes(run.id)
        signals = {signal.id: signal for signal in self._store.list_signals(run.id)}
        claim_views = {
            view.claim.id: view for view in self._store.list_claim_evidence(run.id)
        }
        for theme in themes:
            claim_ids = tuple(
                dict.fromkeys(
                    claim_id
                    for signal_id in theme.signal_ids
                    for claim_id in signals[signal_id].claim_ids
                )
            )
            claims = tuple(claim_views[claim_id].claim for claim_id in claim_ids)
            packet = {
                "theme": {
                    "theme_id": theme.id,
                    "name": theme.name,
                    "description": theme.description,
                    "why_now": theme.why_now,
                },
                "claims": [
                    {
                        "claim_id": claim.id,
                        "statement": claim.statement,
                        "verification_status": claim.verification_status,
                    }
                    for claim in claims
                ],
                "scope_limitation": (
                    "This MVP can review only the currently ingested closed source set."
                ),
            }
            try:
                review = self._model.review_contradictions(packet)
                review = sanitize_contradiction_review(review, claims)
                validate_contradiction_review(review, claims)
            except (AINotConfiguredError, AIProviderError) as exc:
                raise MarketIntelligencePipelineError(
                    "contradiction_model_unavailable"
                ) from exc
            except (AIInvalidOutputError, MarketIntelligenceValidationError) as exc:
                raise MarketIntelligencePipelineError(
                    "contradiction_output_invalid"
                ) from exc

            contradiction_evidence = self._contradiction_evidence(
                run.id, review, claim_views
            )
            self._store.add_evidence(contradiction_evidence)
            document = review.model_dump(mode="json")
            document["scope"] = "closed_current_source_packet"
            document["external_search_completed"] = False
            self._store.save_theme_contradiction(theme.id, document)
        self._store.advance_run(run.id, "theses")

    def _stage_theses(self, run: DiscoveryRun) -> None:
        themes = self._store.list_themes(run.id)
        signals = {signal.id: signal for signal in self._store.list_signals(run.id)}
        base_views = {
            view.claim.id: view for view in self._store.list_claim_evidence(run.id)
        }
        theses: list[ThesisRecord] = []
        for theme in themes:
            claim_ids = tuple(
                dict.fromkeys(
                    claim_id
                    for signal_id in theme.signal_ids
                    for claim_id in signals[signal_id].claim_ids
                )
            )
            claims = tuple(base_views[claim_id].claim for claim_id in claim_ids)
            packet = self._thesis_packet(theme, signals, base_views, claim_ids)
            try:
                draft: Optional[ThesisDraft] = None
                raw_area_count = 0
                for attempt_number in range(1, 3):
                    candidate = self._model.synthesize_thesis(packet)
                    raw_area_count = len(candidate.affected_industries) + len(
                        candidate.affected_companies
                    )
                    candidate = sanitize_thesis_draft(candidate, claims)
                    try:
                        validate_thesis_draft(candidate, theme.id, claims)
                    except MarketIntelligenceValidationError as exc:
                        if attempt_number == 2:
                            raise
                        logger.info(
                            "market_intelligence_thesis_retry reasons=%s",
                            ",".join(exc.reason_codes),
                        )
                        packet = {
                            **packet,
                            "validation_feedback": {
                                "reason_codes": list(exc.reason_codes),
                                "corrections": [
                                    "Use only known claim IDs.",
                                    "Use no numeric digits in generated text.",
                                    "Keep at least one industry inference with a "
                                    "rationale citing known premise claims.",
                                    "Do not write URLs or trading instructions.",
                                ],
                            },
                        }
                        continue
                    draft = candidate
                    break
                if draft is None:
                    raise MarketIntelligenceValidationError(("thesis_retry_exhausted",))
                logger.info(
                    "market_intelligence_thesis_validated affected_areas=%d "
                    "affected_areas_removed=%d",
                    len(draft.affected_industries) + len(draft.affected_companies),
                    raw_area_count
                    - len(draft.affected_industries)
                    - len(draft.affected_companies),
                )
            except (AINotConfiguredError, AIProviderError) as exc:
                raise MarketIntelligencePipelineError(
                    "thesis_model_unavailable"
                ) from exc
            except AIInvalidOutputError as exc:
                logger.warning(
                    "market_intelligence_thesis_validation_failed "
                    "reasons=schema_or_parse"
                )
                raise MarketIntelligencePipelineError(
                    "thesis_output_invalid", retryable=False
                ) from exc
            except MarketIntelligenceValidationError as exc:
                logger.warning(
                    "market_intelligence_thesis_validation_failed reasons=%s",
                    ",".join(exc.reason_codes),
                )
                raise MarketIntelligencePipelineError(
                    "thesis_output_invalid", retryable=False
                ) from exc

            derived_claims, dependencies, evidence, conclusion_ids = (
                self._materialize_conclusions(run.id, theme, draft, base_views)
            )
            self._store.add_derived_claims(derived_claims, dependencies, evidence)
            thesis_id = stable_record_id("thesis", run.id, theme.id)
            theses.append(
                ThesisRecord(
                    id=thesis_id,
                    run_id=run.id,
                    theme_id=theme.id,
                    document={
                        "draft": draft.model_dump(mode="json"),
                        "conclusion_claim_ids": conclusion_ids,
                        "contradiction_review": theme.contradiction_review,
                    },
                    status="preliminary",
                    schema_version=RESEARCH_THESIS_SCHEMA_VERSION,
                    created_at=self._now(),
                )
            )
        self._store.save_theses(theses)
        self._store.advance_run(run.id, "opportunities")

    def _stage_opportunities(self, run: DiscoveryRun) -> None:
        themes = {theme.id: theme for theme in self._store.list_themes(run.id)}
        signals = {signal.id: signal for signal in self._store.list_signals(run.id)}
        views = {
            view.claim.id: view for view in self._store.list_claim_evidence(run.id)
        }
        opportunities: list[OpportunityRecord] = []
        for thesis in self._store.list_theses(run.id):
            theme = themes[thesis.theme_id]
            draft = ThesisDraft.model_validate(thesis.document["draft"])
            conclusion_ids = dict(thesis.document["conclusion_claim_ids"])
            document, priority, confidence, awareness = self._opportunity_document(
                theme, draft, conclusion_ids, signals, views
            )
            opportunities.append(
                OpportunityRecord(
                    id=stable_record_id("opportunity", run.id, theme.id),
                    run_id=run.id,
                    theme_id=theme.id,
                    thesis_id=thesis.id,
                    document=document,
                    status="incomplete",
                    priority_label=str(priority["label"]),
                    priority_score=float(priority["score"]),
                    confidence_label=str(confidence["label"]),
                    confidence_score=float(confidence["score"]),
                    market_awareness=awareness,
                    as_of=self._now(),
                    schema_version=RESEARCH_OPPORTUNITY_SCHEMA_VERSION,
                    created_at=self._now(),
                )
            )
        self._store.save_opportunities(opportunities)
        self._store.finish_run(run.id, "incomplete" if opportunities else "complete")

    def _source_records(
        self,
        run: DiscoveryRun,
        news: NewsSnapshot,
        market: MarketSnapshot,
    ) -> tuple[tuple[SourceRecord, ...], tuple[SourceSnapshotRecord, ...]]:
        now = self._now()
        cutoff = now - timedelta(hours=run.window_hours)
        articles = [
            article for article in news.articles if article.published_at >= cutoff
        ]
        articles = articles[: self._source_limit]
        sources: dict[str, SourceRecord] = {}
        snapshots: list[SourceSnapshotRecord] = []
        seen_hashes: set[str] = set()
        for article in articles:
            source = self._news_source(article, now)
            excerpt = f"{article.title}. {article.description}"
            content_hash = hashlib.sha256(excerpt.encode()).hexdigest()
            if content_hash in seen_hashes:
                continue
            seen_hashes.add(content_hash)
            sources[source.id] = source
            snapshots.append(
                SourceSnapshotRecord(
                    id=stable_record_id("snapshot", run.id, article.article_id),
                    run_id=run.id,
                    source_id=source.id,
                    canonical_url=article.url,
                    title=article.title,
                    published_at=article.published_at,
                    retrieved_at=news.retrieved_at,
                    content_hash=content_hash,
                    excerpt=excerpt,
                    structured_data={"category": article.category},
                )
            )

        market_source_id = stable_record_id("source", "market", market.provider)
        market_source = SourceRecord(
            id=market_source_id,
            publisher=market.provider,
            canonical_url=None,
            source_class="primary_evidence",
            document_type="market_data",
            authority_tier="market_data",
            independence_group=market.provider.lower(),
            discovery_only=False,
            created_at=now,
        )
        sources[market_source.id] = market_source
        for quote in market.quotes:
            data = {
                "symbol": quote.symbol,
                "current_price": str(quote.current_price),
                "daily_change": str(quote.daily_change),
                "percentage_change": str(quote.percentage_change),
                "previous_close": str(quote.previous_close),
                "currency": quote.currency,
                "observed_at": quote.observed_at.isoformat(),
            }
            excerpt = json.dumps(data, sort_keys=True, separators=(",", ":"))
            snapshots.append(
                SourceSnapshotRecord(
                    id=stable_record_id("snapshot", run.id, "market", quote.symbol),
                    run_id=run.id,
                    source_id=market_source.id,
                    canonical_url=None,
                    title=f"{quote.symbol} market observation",
                    published_at=quote.observed_at,
                    retrieved_at=market.retrieved_at,
                    content_hash=hashlib.sha256(excerpt.encode()).hexdigest(),
                    excerpt=excerpt,
                    structured_data=data,
                )
            )
        return tuple(sources.values()), tuple(snapshots)

    @staticmethod
    def _news_source(article: NewsArticle, created_at: datetime) -> SourceRecord:
        quality = article.source.quality_tier
        source_class = "primary_evidence" if quality == "primary" else "reporting"
        authority = {
            "primary": "primary",
            "high_quality_journalism": "high_quality_journalism",
            "specialist": "specialist",
        }[quality]
        return SourceRecord(
            id=f"news:{article.source.source_id}",
            publisher=article.publisher,
            canonical_url=article.source.homepage_url,
            source_class=source_class,  # type: ignore[arg-type]
            document_type=article.source.source_type,
            authority_tier=authority,
            independence_group=article.publisher.lower(),
            discovery_only=False,
            created_at=created_at,
        )

    @staticmethod
    def _snapshot_packet(view: SourceSnapshotView) -> dict[str, object]:
        return {
            "source_snapshot_id": view.snapshot.id,
            "title": view.snapshot.title,
            "excerpt": view.snapshot.excerpt,
            "publisher": view.source.publisher,
            "source_class": view.source.source_class,
            "authority_tier": view.source.authority_tier,
            "published_at": view.snapshot.published_at.isoformat(),
        }

    @staticmethod
    def _supporting_evidence(
        run_id: str,
        claim_id: str,
        view: SourceSnapshotView,
        extraction_method: str,
    ) -> EvidenceRecord:
        return EvidenceRecord(
            id=stable_record_id("evidence", claim_id, view.snapshot.id, "supports"),
            run_id=run_id,
            claim_id=claim_id,
            source_snapshot_id=view.snapshot.id,
            relationship="supports",
            passage=view.snapshot.excerpt,
            location="title_and_excerpt",
            extraction_method=extraction_method,
            verification_status="source_resolved",
        )

    @staticmethod
    def _contradiction_evidence(
        run_id: str,
        review: ContradictionReview,
        views: dict[str, ClaimEvidenceView],
    ) -> tuple[EvidenceRecord, ...]:
        items = []
        for finding in review.findings:
            source_view = views[finding.evidence_claim_id]
            for evidence in source_view.evidence:
                items.append(
                    EvidenceRecord(
                        id=stable_record_id(
                            "evidence",
                            finding.target_claim_id,
                            evidence.source_snapshot_id,
                            "contradicts",
                        ),
                        run_id=run_id,
                        claim_id=finding.target_claim_id,
                        source_snapshot_id=evidence.source_snapshot_id,
                        relationship="contradicts",
                        passage=evidence.passage,
                        location=evidence.location,
                        extraction_method="contradiction_review",
                        verification_status="source_resolved",
                    )
                )
        return tuple(items)

    @staticmethod
    def _theme_claim_ids(
        theme: ThemeRecord, signals: dict[str, SignalRecord]
    ) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                claim_id
                for signal_id in theme.signal_ids
                for claim_id in signals[signal_id].claim_ids
            )
        )

    def _thesis_packet(
        self,
        theme: ThemeRecord,
        signals: dict[str, SignalRecord],
        views: dict[str, ClaimEvidenceView],
        claim_ids: tuple[str, ...],
    ) -> dict[str, object]:
        return {
            "theme": {
                "theme_id": theme.id,
                "name": theme.name,
                "description": theme.description,
                "why_now": theme.why_now,
            },
            "signals": [
                {
                    "signal_id": signal_id,
                    "description": signals[signal_id].description,
                    "claim_ids": list(signals[signal_id].claim_ids),
                }
                for signal_id in theme.signal_ids
            ],
            "claims": [
                {
                    "claim_id": claim_id,
                    "statement": views[claim_id].claim.statement,
                    "entities": list(views[claim_id].claim.entities),
                    "topics": list(views[claim_id].claim.topics),
                    "verification_status": views[claim_id].claim.verification_status,
                }
                for claim_id in claim_ids
            ],
            "contradiction_review": theme.contradiction_review,
            "market_awareness": {
                "awareness_state": "not_assessed",
                "pricing_state": "insufficient_data",
            },
        }

    def _materialize_conclusions(
        self,
        run_id: str,
        theme: ThemeRecord,
        draft: ThesisDraft,
        base_views: dict[str, ClaimEvidenceView],
    ) -> tuple[
        tuple[ClaimRecord, ...],
        tuple[tuple[str, str, str], ...],
        tuple[EvidenceRecord, ...],
        dict[str, str],
    ]:
        now = self._now()
        claims: list[ClaimRecord] = []
        dependencies: list[tuple[str, str, str]] = []
        evidence: dict[str, EvidenceRecord] = {}
        conclusion_ids: dict[str, str] = {}
        for path, claim_type, cited in self._labeled_conclusions(draft):
            claim_id = stable_record_id("claim", run_id, theme.id, path)
            conclusion_ids[path] = claim_id
            claims.append(
                ClaimRecord(
                    id=claim_id,
                    run_id=run_id,
                    statement=cited.text,
                    claim_type=claim_type,  # type: ignore[arg-type]
                    effective_at=now,
                    verification_status="inferred",
                    created_by="model",
                    topics=(theme.name.lower(),),
                    entities=(),
                )
            )
            for parent_claim_id in cited.claim_ids:
                dependencies.append((parent_claim_id, claim_id, "premise"))
                for parent_evidence in base_views[parent_claim_id].evidence:
                    evidence_id = stable_record_id(
                        "evidence",
                        claim_id,
                        parent_evidence.source_snapshot_id,
                        "contextualizes",
                    )
                    evidence[evidence_id] = EvidenceRecord(
                        id=evidence_id,
                        run_id=run_id,
                        claim_id=claim_id,
                        source_snapshot_id=parent_evidence.source_snapshot_id,
                        relationship="contextualizes",
                        passage=parent_evidence.passage,
                        location=parent_evidence.location,
                        extraction_method="derived_provenance",
                        verification_status="premise_resolved",
                    )
        return (
            tuple(claims),
            tuple(dependencies),
            tuple(evidence.values()),
            conclusion_ids,
        )

    @staticmethod
    def _labeled_conclusions(
        draft: ThesisDraft,
    ) -> Iterable[tuple[str, str, CitedDraft]]:
        yield "summary", "inference", draft.summary
        yield "why_now", "inference", draft.why_now
        yield "thesis_statement", "research_hypothesis", draft.thesis_statement
        yield "mechanism", "inference", draft.mechanism
        for index, item in enumerate(draft.affected_industries):
            yield f"affected_industries.{index}", "inference", item.rationale
        for index, item in enumerate(draft.affected_companies):
            yield f"affected_companies.{index}", "inference", item.rationale
        for index, item in enumerate(draft.impact_paths):
            yield f"impact_paths.{index}", "inference", item.mechanism
        for index, item in enumerate(draft.bull_case):
            yield f"bull_case.{index}", "research_hypothesis", item
        for index, item in enumerate(draft.bear_case):
            yield f"bear_case.{index}", "research_hypothesis", item
        for index, item in enumerate(draft.risks):
            yield f"risks.{index}", "inference", item
        for index, item in enumerate(draft.invalidation_conditions):
            yield f"invalidation_conditions.{index}", "research_hypothesis", item
        for index, item in enumerate(draft.research_questions):
            yield f"research_questions.{index}", "research_hypothesis", item
        yield (
            "investment_lens.long_term_relevance",
            "inference",
            draft.investment_lens.long_term_relevance,
        )
        yield (
            "investment_lens.posture_rationale",
            "inference",
            draft.investment_lens.posture_rationale,
        )
        for index, item in enumerate(draft.investment_lens.what_to_watch):
            yield f"investment_lens.what_to_watch.{index}", "inference", item

    def _opportunity_document(
        self,
        theme: ThemeRecord,
        draft: ThesisDraft,
        conclusion_ids: dict[str, object],
        signals: dict[str, SignalRecord],
        views: dict[str, ClaimEvidenceView],
    ) -> tuple[
        dict[str, object], dict[str, object], dict[str, object], dict[str, object]
    ]:
        def cited(path: str, item: CitedDraft, claim_type: str) -> dict[str, object]:
            conclusion_id = str(conclusion_ids[path])
            view = views[conclusion_id]
            return {
                "text": item.text,
                "claim_type": claim_type,
                "claim_ids": [conclusion_id],
                "premise_claim_ids": list(item.claim_ids),
                "evidence_ids": [evidence.id for evidence in view.evidence],
                "source_ids": list(
                    dict.fromkeys(
                        evidence.source_snapshot_id for evidence in view.evidence
                    )
                ),
            }

        signal_items = []
        relevant_base_claim_ids: list[str] = []
        for signal_id in theme.signal_ids:
            signal = signals[signal_id]
            relevant_base_claim_ids.extend(signal.claim_ids)
            signal_source_ids = list(
                dict.fromkeys(
                    evidence.source_snapshot_id
                    for claim_id in signal.claim_ids
                    for evidence in views[claim_id].evidence
                )
            )
            signal_items.append(
                {
                    "signal_id": signal.id,
                    "description": signal.description,
                    "topic": signal.topic,
                    "claim_type": "signal",
                    "claim_ids": list(signal.claim_ids),
                    "source_ids": signal_source_ids,
                    "independent_source_count": signal.independent_source_count,
                    "strength_score": signal.strength_score,
                }
            )

        def affected(
            kind: str, items: list[AffectedAreaDraft]
        ) -> list[dict[str, object]]:
            result = []
            for index, raw in enumerate(items):
                item = raw
                path = f"{kind}.{index}"
                result.append(
                    {
                        "name": item.name,
                        "relationship": item.relationship,
                        "direction": item.direction,
                        "rationale": cited(
                            path,
                            item.rationale,
                            "inference",
                        ),
                    }
                )
            return result

        affected_industries = affected(
            "affected_industries", list(draft.affected_industries)
        )
        affected_companies = affected(
            "affected_companies", list(draft.affected_companies)
        )
        impact_paths = [
            {
                "from_node": item.from_node,
                "to_node": item.to_node,
                "effect_order": item.effect_order,
                "direction": item.direction,
                "mechanism": cited(
                    f"impact_paths.{index}", item.mechanism, "inference"
                ),
            }
            for index, item in enumerate(draft.impact_paths)
        ]
        review = theme.contradiction_review
        contradictory_evidence = []
        for finding in review.get("findings", []):
            if not isinstance(finding, dict):
                continue
            evidence_claim_id = str(finding["evidence_claim_id"])
            target_claim_id = str(finding["target_claim_id"])
            target_evidence = [
                evidence
                for evidence in views[target_claim_id].evidence
                if evidence.relationship == "contradicts"
            ]
            contradictory_evidence.append(
                {
                    "text": str(finding["explanation"]),
                    "claim_type": "inference",
                    "claim_ids": [evidence_claim_id, target_claim_id],
                    "premise_claim_ids": [evidence_claim_id],
                    "evidence_ids": [item.id for item in target_evidence],
                    "source_ids": list(
                        dict.fromkeys(
                            item.source_snapshot_id for item in target_evidence
                        )
                    ),
                }
            )

        relevant_views = [
            views[claim_id] for claim_id in dict.fromkeys(relevant_base_claim_ids)
        ]
        sources = {
            snapshot.snapshot.id: snapshot
            for view in relevant_views
            for snapshot in view.snapshots
        }
        authority_scores = [
            source_authority_score(view.source.authority_tier)
            for view in sources.values()
        ]
        independent_groups = {
            view.source.independence_group for view in sources.values()
        }
        signal_strength = mean(
            signals[signal_id].strength_score for signal_id in theme.signal_ids
        )
        priority_score = round(
            100
            * (
                0.4 * signal_strength
                + 0.25 * theme.freshness_score
                + 0.15 * theme.novelty_score
                + 0.2 * min(1.0, len(independent_groups) / 4)
            ),
            1,
        )
        priority = {
            "label": self._band(priority_score, 45, 70),
            "score": priority_score,
            "method_version": "research_priority.v1",
            "components": {
                "signal_strength": round(signal_strength, 4),
                "freshness": theme.freshness_score,
                "novelty": theme.novelty_score,
                "independent_source_breadth": len(independent_groups),
            },
        }
        confidence_score = min(
            65.0,
            round(
                100
                * (
                    0.5 * (mean(authority_scores) if authority_scores else 0.0)
                    + 0.3 * min(1.0, len(independent_groups) / 3)
                    + 0.2 * 0.5
                ),
                1,
            ),
        )
        confidence = {
            "label": self._band(confidence_score, 40, 70),
            "score": confidence_score,
            "method_version": "research_confidence.v1",
            "components": {
                "source_authority": round(
                    mean(authority_scores) if authority_scores else 0.0, 4
                ),
                "independent_source_breadth": len(independent_groups),
                "external_contradiction_search": False,
            },
            "limitations": list(review.get("limitations", [])),
        }
        awareness = {
            "awareness_state": "not_assessed",
            "pricing_state": "insufficient_data",
            "reporting_breadth": len(independent_groups),
            "community_signal_count": 0,
            "company_mention_count": len(
                {entity for view in relevant_views for entity in view.claim.entities}
            ),
            "observed_market_reaction": None,
            "as_of": self._now().isoformat(),
            "method_version": "market_awareness.v1",
        }
        source_quality = {
            "source_count": len(sources),
            "independent_source_count": len(independent_groups),
            "authority_counts": dict(
                (
                    authority,
                    sum(
                        1
                        for view in sources.values()
                        if view.source.authority_tier == authority
                    ),
                )
                for authority in sorted(
                    {view.source.authority_tier for view in sources.values()}
                )
            ),
            "discovery_only_count": sum(
                1 for view in sources.values() if view.source.discovery_only
            ),
        }
        investment_lens = {
            "orientation": "long_term_accumulation",
            "research_posture": draft.investment_lens.research_posture,
            "long_term_relevance": cited(
                "investment_lens.long_term_relevance",
                draft.investment_lens.long_term_relevance,
                "inference",
            ),
            "posture_rationale": cited(
                "investment_lens.posture_rationale",
                draft.investment_lens.posture_rationale,
                "inference",
            ),
            "what_to_watch": [
                cited(
                    f"investment_lens.what_to_watch.{index}",
                    item,
                    "inference",
                )
                for index, item in enumerate(draft.investment_lens.what_to_watch)
            ],
            "capital_deployment_assessment": "insufficient_data",
            "capital_deployment_limitations": [
                "Broad-market benchmarks, breadth, rates, and volatility are "
                "not assessed.",
                "Valuation and whether the theme is already priced in are not "
                "assessed.",
                "Portfolio fit, liquidity needs, and risk tolerance are not assessed.",
            ],
        }
        document: dict[str, object] = {
            "theme": {
                "name": theme.name,
                "description": theme.description,
                "signal_ids": list(theme.signal_ids),
            },
            "summary": cited("summary", draft.summary, "inference"),
            "why_now": cited("why_now", draft.why_now, "inference"),
            "detected_signals": signal_items,
            "affected_industries": affected_industries,
            "affected_companies": affected_companies,
            "impact_paths": impact_paths,
            "research_thesis": cited(
                "thesis_statement",
                draft.thesis_statement,
                "research_hypothesis",
            ),
            "mechanism": cited("mechanism", draft.mechanism, "inference"),
            "bull_case": [
                cited(f"bull_case.{index}", item, "research_hypothesis")
                for index, item in enumerate(draft.bull_case)
            ],
            "bear_case": [
                cited(f"bear_case.{index}", item, "research_hypothesis")
                for index, item in enumerate(draft.bear_case)
            ],
            "contradictory_evidence": contradictory_evidence,
            "risks": [
                cited(f"risks.{index}", item, "inference")
                for index, item in enumerate(draft.risks)
            ],
            "invalidation_conditions": [
                cited(
                    f"invalidation_conditions.{index}",
                    item,
                    "research_hypothesis",
                )
                for index, item in enumerate(draft.invalidation_conditions)
            ],
            "research_questions": [
                cited(f"research_questions.{index}", item, "research_hypothesis")
                for index, item in enumerate(draft.research_questions)
            ],
            "source_quality": source_quality,
            "source_ids": list(sources),
            "research_priority": priority,
            "confidence": confidence,
            "market_awareness": awareness,
            "investment_lens": investment_lens,
            "scope": "current_source_mvp",
        }
        return document, priority, confidence, awareness

    @staticmethod
    def _band(score: float, medium_threshold: float, high_threshold: float) -> str:
        if score >= high_threshold:
            return "high"
        if score >= medium_threshold:
            return "medium"
        return "low"
