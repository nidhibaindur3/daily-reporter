from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize_text(value: str, maximum: int) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        raise ValueError("text cannot be empty")
    if len(normalized) > maximum:
        raise ValueError(f"text cannot exceed {maximum} characters")
    return normalized


def _normalize_labels(values: list[str], maximum_items: int) -> list[str]:
    normalized = [" ".join(value.split()).strip().lower() for value in values]
    normalized = list(dict.fromkeys(value for value in normalized if value))
    if len(normalized) > maximum_items:
        raise ValueError(f"list cannot exceed {maximum_items} values")
    return normalized


class MarketIntelligenceContract(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ExtractedClaim(MarketIntelligenceContract):
    source_snapshot_id: str
    statement: str
    topics: list[str]
    entities: list[str]

    @field_validator("statement")
    @classmethod
    def validate_statement(cls, value: str) -> str:
        return _normalize_text(value, 500)

    @field_validator("topics")
    @classmethod
    def validate_topics(cls, value: list[str]) -> list[str]:
        normalized = _normalize_labels(value, 6)
        if not normalized:
            raise ValueError("each claim requires at least one topic")
        return normalized

    @field_validator("entities")
    @classmethod
    def validate_entities(cls, value: list[str]) -> list[str]:
        return _normalize_labels(value, 8)


class ClaimExtraction(MarketIntelligenceContract):
    claims: list[ExtractedClaim] = Field(min_length=1, max_length=80)


class ThemeDraft(MarketIntelligenceContract):
    name: str
    description: str
    why_now: str
    signal_ids: list[str] = Field(min_length=1, max_length=8)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _normalize_text(value, 120)

    @field_validator("description", "why_now")
    @classmethod
    def validate_description(cls, value: str) -> str:
        return _normalize_text(value, 500)

    @field_validator("signal_ids")
    @classmethod
    def validate_signal_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("signal_ids cannot contain duplicates")
        return value


class ThemeFormation(MarketIntelligenceContract):
    themes: list[ThemeDraft] = Field(max_length=5)


class ContradictionFinding(MarketIntelligenceContract):
    target_claim_id: str
    evidence_claim_id: str
    explanation: str

    @field_validator("explanation")
    @classmethod
    def validate_explanation(cls, value: str) -> str:
        return _normalize_text(value, 400)


class ContradictionReview(MarketIntelligenceContract):
    findings: list[ContradictionFinding] = Field(max_length=12)
    limitations: list[str] = Field(max_length=8)
    research_questions: list[str] = Field(max_length=8)

    @field_validator("limitations", "research_questions")
    @classmethod
    def validate_text_list(cls, value: list[str]) -> list[str]:
        return [_normalize_text(item, 400) for item in value]


class CitedDraft(MarketIntelligenceContract):
    text: str
    claim_ids: list[str] = Field(min_length=1, max_length=8)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        return _normalize_text(value, 700)

    @field_validator("claim_ids")
    @classmethod
    def validate_claim_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("claim_ids cannot contain duplicates")
        return value


class AffectedAreaDraft(MarketIntelligenceContract):
    name: str
    relationship: Literal["direct", "second_order", "third_order"]
    direction: Literal["positive", "negative", "mixed", "unknown"]
    rationale: CitedDraft

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _normalize_text(value, 120)


class ImpactStepDraft(MarketIntelligenceContract):
    from_node: str
    to_node: str
    effect_order: Literal["direct", "second_order", "third_order"]
    direction: Literal["positive", "negative", "mixed", "unknown"]
    mechanism: CitedDraft

    @field_validator("from_node", "to_node")
    @classmethod
    def validate_node(cls, value: str) -> str:
        return _normalize_text(value, 120)


class InvestmentLensDraft(MarketIntelligenceContract):
    long_term_relevance: CitedDraft
    research_posture: Literal[
        "research_now",
        "watch_for_confirmation",
        "insufficient_evidence",
    ]
    posture_rationale: CitedDraft
    what_to_watch: list[CitedDraft] = Field(min_length=1, max_length=3)


class ThesisDraft(MarketIntelligenceContract):
    theme_id: str
    summary: CitedDraft
    why_now: CitedDraft
    thesis_statement: CitedDraft
    mechanism: CitedDraft
    affected_industries: list[AffectedAreaDraft] = Field(min_length=1, max_length=3)
    affected_companies: list[AffectedAreaDraft] = Field(max_length=3)
    impact_paths: list[ImpactStepDraft] = Field(max_length=4)
    bull_case: list[CitedDraft] = Field(min_length=1, max_length=2)
    bear_case: list[CitedDraft] = Field(min_length=1, max_length=2)
    risks: list[CitedDraft] = Field(min_length=1, max_length=3)
    invalidation_conditions: list[CitedDraft] = Field(min_length=1, max_length=3)
    research_questions: list[CitedDraft] = Field(min_length=1, max_length=4)
    investment_lens: InvestmentLensDraft


class MarketIntelligenceModel(Protocol):
    def extract_claims(self, input_packet: dict[str, object]) -> ClaimExtraction:
        """Extract source-bound atomic claims from a closed source packet."""
        ...

    def form_themes(self, input_packet: dict[str, object]) -> ThemeFormation:
        """Group deterministic signals without inventing new facts."""
        ...

    def review_contradictions(
        self, input_packet: dict[str, object]
    ) -> ContradictionReview:
        """Challenge themes using the available evidence ledger."""
        ...

    def synthesize_thesis(self, input_packet: dict[str, object]) -> ThesisDraft:
        """Synthesize one evidence-bound preliminary research thesis."""
        ...
