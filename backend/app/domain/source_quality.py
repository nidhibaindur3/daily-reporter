from typing import Final

# Claim-specific relevance and independence still matter. These values are only
# deterministic defaults for the source types retained by the application.
SOURCE_AUTHORITY_SCORES: Final[dict[str, float]] = {
    "primary": 1.0,
    "government_regulatory": 1.0,
    "market_data": 1.0,
    "company_filing": 0.95,
    "investor_relations": 0.9,
    "high_quality_journalism": 0.8,
    "academic_research": 0.8,
    "specialist": 0.6,
    "discovery": 0.2,
}


def source_authority_score(authority_tier: str) -> float:
    return SOURCE_AUTHORITY_SCORES.get(authority_tier, 0.4)
