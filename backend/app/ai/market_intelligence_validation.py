import re
from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation

from app.ai.market_intelligence_contracts import (
    AffectedAreaDraft,
    CitedDraft,
    ClaimExtraction,
    ContradictionReview,
    ThemeFormation,
    ThesisDraft,
)
from app.domain.market_intelligence import (
    ClaimRecord,
    SignalRecord,
    SourceSnapshotView,
)

_NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9])[-+]?\d[\d,]*(?:\.\d+)?%?")
_URL_PATTERN = re.compile(
    r"(?:https?://|www\.|\b(?:[a-z0-9-]+\.)+"
    r"(?:com|org|net|gov|edu|io|ai|dev|tech|news)\b)",
    re.IGNORECASE,
)
_TRADING_DIRECTIVE_PATTERN = re.compile(
    r"\b(?:you should|consider|recommend)\s+(?:buying|selling|shorting|trading)\b"
    r"|\b(?:buy|sell|short|trade)\s+(?:the\s+)?(?:stock|shares?|asset|position)\b"
    r"|\b(?:go long|go short|price target)\b",
    re.IGNORECASE,
)
_GENERIC_INDUSTRY_LABELS = {
    "business",
    "businesses",
    "companies",
    "economy",
    "industry",
    "industries",
    "market",
    "markets",
    "technology",
    "world",
}


class MarketIntelligenceValidationError(ValueError):
    def __init__(self, reason_codes: Iterable[str]) -> None:
        self.reason_codes = tuple(sorted(set(reason_codes)))
        super().__init__("market intelligence output validation failed")


def validate_claim_extraction(
    output: ClaimExtraction,
    snapshots: tuple[SourceSnapshotView, ...],
) -> None:
    known = {view.snapshot.id: view for view in snapshots}
    reasons: set[str] = set()
    for claim in output.claims:
        view = known.get(claim.source_snapshot_id)
        if view is None:
            reasons.add("unknown_source_snapshot_id")
            continue
        reasons.update(_unsafe_text_reasons(claim.statement))
        if not _numeric_tokens(claim.statement).issubset(
            _numeric_tokens(view.snapshot.excerpt)
        ):
            reasons.add("unsupported_numeric_value")
    if reasons:
        raise MarketIntelligenceValidationError(reasons)


def sanitize_claim_extraction(
    output: ClaimExtraction,
    snapshots: tuple[SourceSnapshotView, ...],
) -> ClaimExtraction:
    """Keep only safe claims and literal source-grounded entity labels.

    A single malformed claim should not discard an otherwise valid extraction
    batch. Unknown citations, generated URLs, trading directives, and invented
    numeric values cause the individual claim to be dropped. Entity labels are
    optional metadata, so ungrounded labels are removed without weakening the
    provenance of the claim itself.
    """
    known = {view.snapshot.id: view for view in snapshots}
    valid_claims = []
    rejected_reasons: set[str] = set()
    for claim in output.claims:
        view = known.get(claim.source_snapshot_id)
        if view is None:
            rejected_reasons.add("unknown_source_snapshot_id")
            continue

        claim_reasons = _unsafe_text_reasons(claim.statement)
        if not _numeric_tokens(claim.statement).issubset(
            _numeric_tokens(view.snapshot.excerpt)
        ):
            claim_reasons.add("unsupported_numeric_value")
        if claim_reasons:
            rejected_reasons.update(claim_reasons)
            continue

        excerpt = view.snapshot.excerpt.lower()
        grounded_entities = [
            entity for entity in claim.entities if entity.lower() in excerpt
        ]
        valid_claims.append(claim.model_copy(update={"entities": grounded_entities}))

    if not valid_claims:
        rejected_reasons.add("no_valid_claims")
        raise MarketIntelligenceValidationError(rejected_reasons)
    return ClaimExtraction(claims=valid_claims)


def validate_theme_formation(
    output: ThemeFormation,
    signals: tuple[SignalRecord, ...],
    maximum_themes: int,
) -> None:
    known_ids = {signal.id for signal in signals}
    reasons: set[str] = set()
    if len(output.themes) > maximum_themes:
        reasons.add("too_many_themes")
    for theme in output.themes:
        if not set(theme.signal_ids).issubset(known_ids):
            reasons.add("unknown_signal_id")
        reasons.update(_unsafe_text_reasons(theme.name))
        reasons.update(_unsafe_text_reasons(theme.description))
        reasons.update(_unsafe_text_reasons(theme.why_now))
        if _numeric_tokens(f"{theme.name} {theme.description} {theme.why_now}"):
            reasons.add("unsupported_numeric_value")
    if reasons:
        raise MarketIntelligenceValidationError(reasons)


def sanitize_theme_formation(
    output: ThemeFormation,
    signals: tuple[SignalRecord, ...],
    maximum_themes: int,
) -> ThemeFormation:
    """Discard malformed theme candidates without rejecting the whole batch."""
    known_ids = {signal.id for signal in signals}
    valid_themes = []
    for theme in output.themes:
        text = f"{theme.name} {theme.description} {theme.why_now}"
        if not set(theme.signal_ids).issubset(known_ids):
            continue
        if _unsafe_text_reasons(text) or _numeric_tokens(text):
            continue
        valid_themes.append(theme)
        if len(valid_themes) == maximum_themes:
            break
    return ThemeFormation(themes=valid_themes)


def validate_contradiction_review(
    output: ContradictionReview,
    claims: tuple[ClaimRecord, ...],
) -> None:
    known_ids = {claim.id for claim in claims}
    reasons: set[str] = set()
    for finding in output.findings:
        if (
            finding.target_claim_id not in known_ids
            or finding.evidence_claim_id not in known_ids
        ):
            reasons.add("unknown_claim_id")
        if finding.target_claim_id == finding.evidence_claim_id:
            reasons.add("self_contradiction")
        reasons.update(_unsafe_text_reasons(finding.explanation))
    for value in (*output.limitations, *output.research_questions):
        reasons.update(_unsafe_text_reasons(value))
    if reasons:
        raise MarketIntelligenceValidationError(reasons)


def sanitize_contradiction_review(
    output: ContradictionReview,
    claims: tuple[ClaimRecord, ...],
) -> ContradictionReview:
    """Remove untraceable contradiction candidates and unsafe free text."""
    known_ids = {claim.id for claim in claims}
    findings = [
        finding
        for finding in output.findings
        if finding.target_claim_id in known_ids
        and finding.evidence_claim_id in known_ids
        and finding.target_claim_id != finding.evidence_claim_id
        and not _unsafe_text_reasons(finding.explanation)
    ]
    limitations = [
        value for value in output.limitations if not _unsafe_text_reasons(value)
    ]
    research_questions = [
        value for value in output.research_questions if not _unsafe_text_reasons(value)
    ]
    return ContradictionReview(
        findings=findings,
        limitations=limitations,
        research_questions=research_questions,
    )


def validate_thesis_draft(
    output: ThesisDraft,
    theme_id: str,
    claims: tuple[ClaimRecord, ...],
) -> None:
    if output.theme_id != theme_id:
        raise MarketIntelligenceValidationError(("wrong_theme_id",))

    known_claims = {claim.id: claim for claim in claims}
    reasons: set[str] = set()
    for cited in cited_drafts(output):
        if not set(cited.claim_ids).issubset(known_claims):
            reasons.add("unknown_claim_id")
            continue
        reasons.update(_unsafe_text_reasons(cited.text))
        supported_numbers: set[str] = set()
        for claim_id in cited.claim_ids:
            supported_numbers.update(_numeric_tokens(known_claims[claim_id].statement))
        if not _numeric_tokens(cited.text).issubset(supported_numbers):
            reasons.add("unsupported_numeric_value")
    for company in output.affected_companies:
        reasons.update(_unsafe_text_reasons(company.name))
        if not _area_name_is_grounded(company, known_claims, entity_only=True):
            reasons.add("unsupported_company")
    for industry in output.affected_industries:
        reasons.update(_unsafe_text_reasons(industry.name))
        if not _industry_inference_is_supported(industry, known_claims):
            reasons.add("unsupported_industry")
    for impact in output.impact_paths:
        reasons.update(_unsafe_text_reasons(impact.from_node))
        reasons.update(_unsafe_text_reasons(impact.to_node))
    if reasons:
        raise MarketIntelligenceValidationError(reasons)


def sanitize_thesis_draft(
    output: ThesisDraft,
    claims: tuple[ClaimRecord, ...],
) -> ThesisDraft:
    """Keep cited industry inferences while removing unsupported company names."""
    known_claims = {claim.id: claim for claim in claims}
    industries = [
        area
        for area in output.affected_industries
        if not _unsafe_text_reasons(area.name)
        and _industry_inference_is_supported(area, known_claims)
    ]
    companies = [
        area
        for area in output.affected_companies
        if not _unsafe_text_reasons(area.name)
        and _area_name_is_grounded(area, known_claims, entity_only=True)
    ]
    return output.model_copy(
        update={
            "affected_industries": industries,
            "affected_companies": companies,
        }
    )


def cited_drafts(output: ThesisDraft) -> Iterable[CitedDraft]:
    yield output.summary
    yield output.why_now
    yield output.thesis_statement
    yield output.mechanism
    yield from output.bull_case
    yield from output.bear_case
    yield from output.risks
    yield from output.invalidation_conditions
    yield from output.research_questions
    yield output.investment_lens.long_term_relevance
    yield output.investment_lens.posture_rationale
    yield from output.investment_lens.what_to_watch
    for item in output.affected_industries:
        yield item.rationale
    for item in output.affected_companies:
        yield item.rationale
    for item in output.impact_paths:
        yield item.mechanism


def claim_source_ids(
    claim_ids: Iterable[str], claim_sources: Mapping[str, tuple[str, ...]]
) -> list[str]:
    return list(
        dict.fromkeys(
            source_id
            for claim_id in claim_ids
            for source_id in claim_sources.get(claim_id, ())
        )
    )


def _area_name_is_grounded(
    area: AffectedAreaDraft,
    known_claims: Mapping[str, ClaimRecord],
    entity_only: bool,
) -> bool:
    label = area.name.lower()
    for claim_id in area.rationale.claim_ids:
        claim = known_claims.get(claim_id)
        if claim is None:
            continue
        allowed = set(claim.entities)
        if not entity_only:
            allowed.update(claim.topics)
        if label in allowed:
            return True
    return False


def _industry_inference_is_supported(
    area: AffectedAreaDraft,
    known_claims: Mapping[str, ClaimRecord],
) -> bool:
    """Allow a specific industry inference when its rationale cites known claims.

    Unlike a company name, an industry classification is an analytical label
    and need not appear verbatim in a source. Its rationale still has to resolve
    to source-grounded premise claims.
    """
    if area.name.strip().lower() in _GENERIC_INDUSTRY_LABELS:
        return False
    return any(claim_id in known_claims for claim_id in area.rationale.claim_ids)


def _unsafe_text_reasons(value: str) -> set[str]:
    reasons = set()
    if _URL_PATTERN.search(value):
        reasons.add("generated_url")
    if _TRADING_DIRECTIVE_PATTERN.search(value):
        reasons.add("trading_directive")
    return reasons


def _numeric_tokens(value: str) -> set[str]:
    tokens: set[str] = set()
    for match in _NUMBER_PATTERN.finditer(value):
        token = match.group(0).replace(",", "").removesuffix("%")
        try:
            number = Decimal(token)
        except InvalidOperation:
            continue
        normalized = format(number, "f")
        if "." in normalized:
            normalized = normalized.rstrip("0").rstrip(".")
        tokens.add("0" if normalized in {"-0", "+0"} else normalized)
    return tokens
