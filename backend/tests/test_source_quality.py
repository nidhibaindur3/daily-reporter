from app.domain.source_quality import source_authority_score


def test_source_quality_defaults_preserve_authoritative_hierarchy() -> None:
    assert source_authority_score("government_regulatory") > source_authority_score(
        "specialist"
    )
    assert source_authority_score("company_filing") > source_authority_score(
        "high_quality_journalism"
    )
    assert source_authority_score("high_quality_journalism") > source_authority_score(
        "discovery"
    )
