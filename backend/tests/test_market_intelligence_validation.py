from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.ai.market_intelligence_contracts import (
    AffectedAreaDraft,
    CitedDraft,
    ClaimExtraction,
    ExtractedClaim,
    InvestmentLensDraft,
    ThemeDraft,
    ThemeFormation,
    ThesisDraft,
)
from app.ai.market_intelligence_validation import (
    MarketIntelligenceValidationError,
    sanitize_claim_extraction,
    sanitize_theme_formation,
    sanitize_thesis_draft,
    validate_thesis_draft,
)
from app.domain.market_intelligence import (
    ClaimRecord,
    SignalRecord,
    SourceRecord,
    SourceSnapshotRecord,
    SourceSnapshotView,
)


def thesis(statement: str, claim_id: str) -> ThesisDraft:
    cited = CitedDraft(text=statement, claim_ids=[claim_id])
    return ThesisDraft(
        theme_id="theme-1",
        summary=cited,
        why_now=cited,
        thesis_statement=cited,
        mechanism=cited,
        affected_industries=[
            AffectedAreaDraft(
                name="Electrical equipment manufacturing",
                relationship="second_order",
                direction="mixed",
                rationale=cited,
            )
        ],
        affected_companies=[],
        impact_paths=[],
        bull_case=[cited],
        bear_case=[cited],
        risks=[cited],
        invalidation_conditions=[cited],
        research_questions=[cited],
        investment_lens=InvestmentLensDraft(
            long_term_relevance=cited,
            research_posture="watch_for_confirmation",
            posture_rationale=cited,
            what_to_watch=[cited],
        ),
    )


def source_claim() -> ClaimRecord:
    return ClaimRecord(
        id="claim-1",
        run_id="run-1",
        statement="The provider observed a value of 10.",
        claim_type="fact",
        effective_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
        verification_status="source_grounded",
        created_by="model",
        topics=("topic",),
        entities=(),
    )


def source_snapshot() -> SourceSnapshotView:
    return SourceSnapshotView(
        source=SourceRecord(
            id="source-1",
            publisher="Primary Desk",
            canonical_url="https://primary.test",
            source_class="primary_evidence",
            document_type="company_newsroom",
            authority_tier="primary",
            independence_group="primary-desk",
            discovery_only=False,
            created_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
        ),
        snapshot=SourceSnapshotRecord(
            id="snapshot-1",
            run_id="run-1",
            source_id="source-1",
            canonical_url="https://primary.test/update",
            title="Acme expands grid capacity",
            published_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
            retrieved_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
            content_hash="a" * 64,
            excerpt="Acme expands grid capacity by 10 units.",
            structured_data={},
        ),
    )


def test_claim_sanitization_keeps_safe_claims_and_removes_ungrounded_entities() -> None:
    output = ClaimExtraction(
        claims=[
            ExtractedClaim(
                source_snapshot_id="snapshot-1",
                statement="Acme expands grid capacity by 10 units.",
                topics=["grid capacity"],
                entities=["Acme", "Invented Corp"],
            ),
            ExtractedClaim(
                source_snapshot_id="unknown",
                statement="An unknown source reported 99 units.",
                topics=["grid capacity"],
                entities=[],
            ),
        ]
    )

    sanitized = sanitize_claim_extraction(output, (source_snapshot(),))

    assert len(sanitized.claims) == 1
    assert sanitized.claims[0].entities == ["acme"]


def test_claim_sanitization_fails_when_no_safe_claims_remain() -> None:
    output = ClaimExtraction(
        claims=[
            ExtractedClaim(
                source_snapshot_id="snapshot-1",
                statement="Acme expands grid capacity by 99 units.",
                topics=["grid capacity"],
                entities=["Acme"],
            )
        ]
    )

    with pytest.raises(MarketIntelligenceValidationError) as error:
        sanitize_claim_extraction(output, (source_snapshot(),))

    assert set(error.value.reason_codes) == {
        "no_valid_claims",
        "unsupported_numeric_value",
    }


def test_theme_sanitization_discards_unknown_and_unsafe_candidates() -> None:
    signal = SignalRecord(
        id="signal-1",
        run_id="run-1",
        signal_type="cross_source_convergence",
        description="Two sources share a topic.",
        topic="grid capacity",
        first_observed_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
        last_observed_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
        source_count=2,
        independent_source_count=2,
        novelty_score=0.5,
        strength_score=0.5,
        status="candidate",
        claim_ids=("claim-1",),
    )
    output = ThemeFormation(
        themes=[
            ThemeDraft(
                name="Grounded capacity pressure",
                description="Separate observations may share a mechanism.",
                why_now="The observations converge in the current window.",
                signal_ids=["signal-1"],
            ),
            ThemeDraft(
                name="Unknown signal",
                description="This candidate has no known signal.",
                why_now="It should be discarded.",
                signal_ids=["unknown"],
            ),
            ThemeDraft(
                name="Projected 99 percent increase",
                description="This candidate invents a value.",
                why_now="It should be discarded.",
                signal_ids=["signal-1"],
            ),
        ]
    )

    sanitized = sanitize_theme_formation(output, (signal,), maximum_themes=3)

    assert [theme.name for theme in sanitized.themes] == ["Grounded capacity pressure"]


@pytest.mark.parametrize(
    ("statement", "claim_id", "reason"),
    [
        ("A projected value is 99.", "claim-1", "unsupported_numeric_value"),
        ("Buy the stock based on this signal.", "claim-1", "trading_directive"),
        ("Read invented.example.com.", "claim-1", "generated_url"),
        ("A grounded statement.", "unknown", "unknown_claim_id"),
    ],
)
def test_thesis_validation_rejects_unsafe_or_untraceable_claims(
    statement: str,
    claim_id: str,
    reason: str,
) -> None:
    with pytest.raises(MarketIntelligenceValidationError) as error:
        validate_thesis_draft(
            thesis(statement, claim_id),
            "theme-1",
            (source_claim(),),
        )

    assert reason in error.value.reason_codes


def test_thesis_validation_rejects_company_not_named_in_premise_claims() -> None:
    output = thesis("A grounded statement.", "claim-1")
    output.affected_companies = [
        AffectedAreaDraft(
            name="Invented Corp",
            relationship="direct",
            direction="positive",
            rationale=CitedDraft(
                text="The company could be affected.",
                claim_ids=["claim-1"],
            ),
        )
    ]

    with pytest.raises(MarketIntelligenceValidationError) as error:
        validate_thesis_draft(output, "theme-1", (source_claim(),))

    assert "unsupported_company" in error.value.reason_codes


def test_thesis_validation_allows_cited_industry_inference() -> None:
    output = thesis(
        "Electrical equipment manufacturers may be affected through demand.",
        "claim-1",
    )

    validate_thesis_draft(output, "theme-1", (source_claim(),))


def test_thesis_contract_requires_at_least_one_industry_inference() -> None:
    payload = thesis("A grounded statement.", "claim-1").model_dump()
    payload["affected_industries"] = []

    with pytest.raises(ValidationError):
        ThesisDraft.model_validate(payload)


def test_thesis_validation_allows_cited_broad_industry_as_fallback() -> None:
    output = thesis("A grounded statement.", "claim-1")
    output.affected_industries[0] = AffectedAreaDraft(
        name="Technology",
        relationship="direct",
        direction="unknown",
        rationale=CitedDraft(
            text="Technology could be affected.",
            claim_ids=["claim-1"],
        ),
    )

    validate_thesis_draft(output, "theme-1", (source_claim(),))


def test_thesis_validation_rejects_missing_industry_after_sanitization() -> None:
    output = thesis("A grounded statement.", "claim-1").model_copy(
        update={"affected_industries": []}
    )

    with pytest.raises(MarketIntelligenceValidationError) as error:
        validate_thesis_draft(output, "theme-1", (source_claim(),))

    assert "missing_affected_industry" in error.value.reason_codes


def test_thesis_sanitization_uses_cited_broad_industry_as_fallback() -> None:
    output = thesis("A grounded statement.", "claim-1")
    output.affected_industries = [
        AffectedAreaDraft(
            name="Technology",
            relationship="direct",
            direction="unknown",
            rationale=CitedDraft(
                text="Technology could be affected.",
                claim_ids=["claim-1"],
            ),
        )
    ]

    sanitized = sanitize_thesis_draft(output, (source_claim(),))

    assert [area.name for area in sanitized.affected_industries] == ["Technology"]


def test_thesis_sanitization_keeps_industry_inference_and_removes_company() -> None:
    output = thesis("A grounded statement.", "claim-1")
    output.affected_companies = [
        AffectedAreaDraft(
            name="Invented Corp",
            relationship="direct",
            direction="positive",
            rationale=CitedDraft(
                text="The company could be affected.",
                claim_ids=["claim-1"],
            ),
        )
    ]

    sanitized = sanitize_thesis_draft(output, (source_claim(),))

    assert [area.name for area in sanitized.affected_industries] == [
        "Electrical equipment manufacturing"
    ]
    assert sanitized.affected_companies == []
