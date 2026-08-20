from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.ai.market_intelligence_contracts import (
    AffectedAreaDraft,
    CitedDraft,
    ClaimExtraction,
    ContradictionReview,
    ExtractedClaim,
    ImpactStepDraft,
    InvestmentLensDraft,
    ThemeDraft,
    ThemeFormation,
    ThesisDraft,
)
from app.domain.market import MarketQuote, MarketSnapshot, MarketStatus
from app.domain.market_intelligence import (
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
from app.domain.news import NewsArticle, NewsSnapshot, NewsSourceMetadata
from app.schemas.market_intelligence import ResearchOpportunityDocumentResponse
from app.services.market_intelligence import MarketIntelligencePipeline

NOW = datetime(2026, 8, 19, 18, tzinfo=timezone.utc)


class StaticNewsService:
    def get_latest(self) -> NewsSnapshot:
        articles = []
        for index, publisher in enumerate(("Primary Desk", "Specialist Desk")):
            source = NewsSourceMetadata(
                source_id=f"source-{index}",
                homepage_url=f"https://source-{index}.test",
                source_type=(
                    "company_newsroom" if index == 0 else "specialist_publication"
                ),
                quality_tier="primary" if index == 0 else "specialist",
            )
            articles.append(
                NewsArticle(
                    article_id=f"article-{index}",
                    title=f"Grid infrastructure development {index}",
                    publisher=publisher,
                    url=f"https://source-{index}.test/article",
                    published_at=NOW,
                    category="technology",
                    description="A current development affects grid infrastructure.",
                    source=source,
                )
            )
        return NewsSnapshot(
            articles=tuple(articles),
            unavailable_sources=(),
            provider="mock-news",
            retrieved_at=NOW,
        )


class StaticMarketService:
    def get_watchlist(self) -> MarketSnapshot:
        return MarketSnapshot(
            quotes=(
                MarketQuote(
                    symbol="AAPL",
                    current_price=Decimal("200"),
                    daily_change=Decimal("1"),
                    percentage_change=Decimal("0.5"),
                    previous_close=Decimal("199"),
                    currency="USD",
                    observed_at=NOW,
                ),
            ),
            market_status=MarketStatus(
                exchange="US",
                session="open",
                label="Market open",
                timezone="America/New_York",
                holiday=None,
                observed_at=NOW,
            ),
            unavailable_symbols=(),
            provider="mock-market",
            retrieved_at=NOW,
        )


class GroundedModel:
    def extract_claims(self, input_packet: dict[str, object]) -> ClaimExtraction:
        snapshots = input_packet["source_snapshots"]
        assert isinstance(snapshots, list)
        return ClaimExtraction(
            claims=[
                ExtractedClaim(
                    source_snapshot_id=str(snapshot["source_snapshot_id"]),
                    statement="A current development affects grid infrastructure.",
                    topics=["grid infrastructure", "grid equipment"],
                    entities=[],
                )
                for snapshot in snapshots
                if isinstance(snapshot, dict)
            ]
        )

    def form_themes(self, input_packet: dict[str, object]) -> ThemeFormation:
        signals = input_packet["signals"]
        assert isinstance(signals, list)
        signal = signals[0]
        assert isinstance(signal, dict)
        return ThemeFormation(
            themes=[
                ThemeDraft(
                    name="Grid infrastructure pressure",
                    description=(
                        "Independent developments point to a shared constraint."
                    ),
                    why_now=(
                        "Separate current reports now converge on the same constraint."
                    ),
                    signal_ids=[str(signal["signal_id"])],
                )
            ]
        )

    def review_contradictions(
        self, input_packet: dict[str, object]
    ) -> ContradictionReview:
        return ContradictionReview(
            findings=[],
            limitations=["Only the closed current source set was reviewed."],
            research_questions=["What evidence would challenge this connection?"],
        )

    def synthesize_thesis(self, input_packet: dict[str, object]) -> ThesisDraft:
        theme = input_packet["theme"]
        claims = input_packet["claims"]
        assert isinstance(theme, dict)
        assert isinstance(claims, list)
        claim_ids = [
            str(claim["claim_id"]) for claim in claims if isinstance(claim, dict)
        ]

        def cited(text: str) -> CitedDraft:
            return CitedDraft(text=text, claim_ids=claim_ids)

        return ThesisDraft(
            theme_id=str(theme["theme_id"]),
            summary=cited("A shared infrastructure constraint may be emerging."),
            why_now=cited("Independent current reports now point in one direction."),
            thesis_statement=cited(
                "The constraint may create a researchable second-order effect."
            ),
            mechanism=cited("The shared constraint could change industry priorities."),
            affected_industries=[
                AffectedAreaDraft(
                    name="Grid equipment",
                    relationship="direct",
                    direction="mixed",
                    rationale=cited(
                        "Grid equipment is directly connected to the constraint."
                    ),
                )
            ],
            affected_companies=[],
            impact_paths=[
                ImpactStepDraft(
                    from_node="Infrastructure constraint",
                    to_node="Grid equipment",
                    effect_order="direct",
                    direction="mixed",
                    mechanism=cited("The constraint may shift equipment demand."),
                )
            ],
            bull_case=[cited("The constraint persists and draws durable investment.")],
            bear_case=[cited("The reports reflect a temporary bottleneck.")],
            risks=[cited("The source window may overstate convergence.")],
            invalidation_conditions=[
                cited("New primary evidence shows the constraint is easing.")
            ],
            research_questions=[
                cited("Which primary filings quantify the constraint?")
            ],
            investment_lens=InvestmentLensDraft(
                long_term_relevance=cited(
                    "Persistent constraints may affect long-term industry investment."
                ),
                research_posture="research_now",
                posture_rationale=cited(
                    "Independent reports make the constraint worth deeper research."
                ),
                what_to_watch=[
                    cited("Look for primary evidence that the constraint persists.")
                ],
            ),
        )


class CrossTopicModel(GroundedModel):
    def extract_claims(self, input_packet: dict[str, object]) -> ClaimExtraction:
        snapshots = input_packet["source_snapshots"]
        assert isinstance(snapshots, list)
        topics = (
            ["data center demand"],
            ["power equipment capacity", "grid equipment"],
        )
        return ClaimExtraction(
            claims=[
                ExtractedClaim(
                    source_snapshot_id=str(snapshot["source_snapshot_id"]),
                    statement="A current development affects grid infrastructure.",
                    topics=topics[index],
                    entities=[],
                )
                for index, snapshot in enumerate(snapshots)
                if isinstance(snapshot, dict)
            ]
        )

    def form_themes(self, input_packet: dict[str, object]) -> ThemeFormation:
        signals = input_packet["signals"]
        assert isinstance(signals, list)
        selected_ids = [
            str(signal["signal_id"])
            for signal in signals
            if isinstance(signal, dict)
            and signal["topic"] in {"data center demand", "power equipment capacity"}
        ]
        return ThemeFormation(
            themes=[
                ThemeDraft(
                    name="Demand meeting equipment constraints",
                    description=(
                        "Separate observations may form one infrastructure pattern."
                    ),
                    why_now="The observations appeared in the same current window.",
                    signal_ids=selected_ids,
                )
            ]
        )


class InMemoryStore:
    def __init__(self) -> None:
        self.run = DiscoveryRun(
            id="run-1",
            status="queued",
            current_stage="sources",
            window_hours=48,
            maximum_themes=3,
            focus_topics=(),
            workflow_version="market_intelligence.workflow.v1",
            error_code=None,
            created_at=NOW,
            updated_at=NOW,
            completed_at=None,
        )
        self.sources: dict[str, SourceRecord] = {}
        self.snapshots: dict[str, SourceSnapshotRecord] = {}
        self.claims: dict[str, ClaimRecord] = {}
        self.evidence: dict[str, EvidenceRecord] = {}
        self.dependencies: list[tuple[str, str, str]] = []
        self.signals: dict[str, SignalRecord] = {}
        self.themes: dict[str, ThemeRecord] = {}
        self.theses: dict[str, ThesisRecord] = {}
        self.opportunities: dict[str, OpportunityRecord] = {}

    def get_run(self, run_id: str) -> Optional[DiscoveryRun]:
        return self.run if self.run.id == run_id else None

    def advance_run(self, run_id: str, next_stage: str) -> None:
        assert run_id == self.run.id
        self.run = replace(
            self.run,
            status="running",
            current_stage=next_stage,
            updated_at=NOW,
        )

    def finish_run(self, run_id: str, status: str) -> None:
        assert run_id == self.run.id
        self.run = replace(
            self.run,
            status=status,
            current_stage="done",
            updated_at=NOW,
            completed_at=NOW,
        )

    def save_sources(self, sources, snapshots) -> None:
        self.sources.update((item.id, item) for item in sources)
        self.snapshots.update((item.id, item) for item in snapshots)

    def list_snapshots(self, run_id: str) -> tuple[SourceSnapshotView, ...]:
        return tuple(
            SourceSnapshotView(snapshot=item, source=self.sources[item.source_id])
            for item in self.snapshots.values()
            if item.run_id == run_id
        )

    def replace_claims(self, run_id: str, claims, evidence) -> None:
        self.claims = {item.id: item for item in claims if item.run_id == run_id}
        self.evidence = {item.id: item for item in evidence if item.run_id == run_id}

    def add_evidence(self, items) -> None:
        self.evidence.update((item.id, item) for item in items)

    def add_derived_claims(self, claims, dependencies, evidence) -> None:
        self.claims.update((item.id, item) for item in claims)
        self.dependencies.extend(dependencies)
        self.evidence.update((item.id, item) for item in evidence)

    def list_claims(self, run_id: str) -> tuple[ClaimRecord, ...]:
        return tuple(item for item in self.claims.values() if item.run_id == run_id)

    def list_claim_evidence(self, run_id: str) -> tuple[ClaimEvidenceView, ...]:
        snapshots = {item.snapshot.id: item for item in self.list_snapshots(run_id)}
        return tuple(
            ClaimEvidenceView(
                claim=claim,
                evidence=tuple(
                    item for item in self.evidence.values() if item.claim_id == claim.id
                ),
                snapshots=tuple(
                    snapshots[item.source_snapshot_id]
                    for item in self.evidence.values()
                    if item.claim_id == claim.id
                    and item.source_snapshot_id in snapshots
                ),
            )
            for claim in self.list_claims(run_id)
        )

    def replace_signals(self, run_id: str, signals) -> None:
        self.signals = {item.id: item for item in signals if item.run_id == run_id}

    def list_signals(self, run_id: str) -> tuple[SignalRecord, ...]:
        return tuple(item for item in self.signals.values() if item.run_id == run_id)

    def replace_themes(self, run_id: str, themes) -> None:
        self.themes = {item.id: item for item in themes if item.run_id == run_id}

    def list_themes(self, run_id: str) -> tuple[ThemeRecord, ...]:
        return tuple(item for item in self.themes.values() if item.run_id == run_id)

    def save_theme_contradiction(
        self, theme_id: str, document: dict[str, object]
    ) -> None:
        self.themes[theme_id] = replace(
            self.themes[theme_id], contradiction_review=document
        )

    def save_theses(self, theses) -> None:
        self.theses.update((item.id, item) for item in theses)

    def list_theses(self, run_id: str) -> tuple[ThesisRecord, ...]:
        return tuple(item for item in self.theses.values() if item.run_id == run_id)

    def save_opportunities(self, opportunities) -> None:
        self.opportunities.update((item.id, item) for item in opportunities)


def test_pipeline_discovers_cross_source_theme_with_traceable_conclusions() -> None:
    store = InMemoryStore()
    pipeline = MarketIntelligencePipeline(
        store=store,
        news_service=StaticNewsService(),
        market_service=StaticMarketService(),
        model=GroundedModel(),
        source_limit=24,
        now=lambda: NOW,
    )

    pipeline.run(store.run.id)

    assert store.run.status == "incomplete"
    assert store.run.current_stage == "done"
    convergences = [
        signal
        for signal in store.signals.values()
        if signal.signal_type == "cross_source_convergence"
    ]
    assert len(convergences) >= 1
    signal = next(item for item in convergences if item.topic == "grid infrastructure")
    assert signal.independent_source_count == 2
    assert len(store.opportunities) == 1

    opportunity = next(iter(store.opportunities.values()))
    document = opportunity.document
    ResearchOpportunityDocumentResponse.model_validate(document)
    assert document["summary"]["claim_type"] == "inference"
    assert document["research_thesis"]["claim_type"] == "research_hypothesis"
    assert document["market_awareness"]["awareness_state"] == "not_assessed"
    assert document["market_awareness"]["pricing_state"] == "insufficient_data"
    assert document["investment_lens"]["orientation"] == "long_term_accumulation"
    assert document["investment_lens"]["research_posture"] == "research_now"
    assert (
        document["investment_lens"]["capital_deployment_assessment"]
        == "insufficient_data"
    )
    assert document["investment_lens"]["long_term_relevance"]["source_ids"]
    assert len(document["affected_industries"]) >= 1
    assert document["affected_industries"][0]["rationale"]["claim_type"] == "inference"
    assert document["affected_industries"][0]["rationale"]["source_ids"]
    assert document["scope"] == "current_source_mvp"
    assert opportunity.schema_version == "research_opportunity.v2"
    assert len(document["source_ids"]) == 2

    derived_claim_ids = {
        claim.id for claim in store.claims.values() if claim.claim_type != "fact"
    }
    assert derived_claim_ids
    assert all(
        dependent in derived_claim_ids
        for _, dependent, relationship in store.dependencies
        if relationship == "premise"
    )
    assert all(
        any(
            evidence.claim_id == claim_id and evidence.relationship == "contextualizes"
            for evidence in store.evidence.values()
        )
        for claim_id in derived_claim_ids
    )


def test_pipeline_can_connect_independent_signals_from_different_topics() -> None:
    store = InMemoryStore()
    pipeline = MarketIntelligencePipeline(
        store=store,
        news_service=StaticNewsService(),
        market_service=StaticMarketService(),
        model=CrossTopicModel(),
        source_limit=24,
        now=lambda: NOW,
    )

    pipeline.run(store.run.id)

    source_observations = [
        signal
        for signal in store.signals.values()
        if signal.signal_type == "source_observation"
    ]
    assert len(source_observations) >= 2
    theme = next(iter(store.themes.values()))
    assert len(theme.signal_ids) == 2
    assert store.run.status == "incomplete"
