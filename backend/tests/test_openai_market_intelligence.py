from types import SimpleNamespace

from app.ai.market_intelligence_contracts import ClaimExtraction, ExtractedClaim
from app.ai.openai_market_intelligence import OpenAIMarketIntelligenceModel


class RecordingResponses:
    def __init__(self, output) -> None:
        self.output = output
        self.kwargs: dict[str, object] = {}

    def parse(self, **kwargs: object):
        self.kwargs = kwargs
        return SimpleNamespace(
            id="response-1",
            output_parsed=self.output,
            usage=SimpleNamespace(
                input_tokens=20,
                output_tokens=10,
                total_tokens=30,
            ),
            status="completed",
        )


def test_openai_stage_uses_structured_output_without_tools_or_storage() -> None:
    output = ClaimExtraction(
        claims=[
            ExtractedClaim(
                source_snapshot_id="snapshot-1",
                statement="A source-bound statement.",
                topics=["infrastructure"],
                entities=[],
            )
        ]
    )
    responses = RecordingResponses(output)
    client = SimpleNamespace(responses=responses)
    model = OpenAIMarketIntelligenceModel(
        client=client,
        model="test-model",
        max_output_tokens=2000,
        reasoning_effort="minimal",
        verbosity="low",
    )

    result = model.extract_claims({"source_snapshots": []})

    assert result == output
    assert responses.kwargs["text_format"] is ClaimExtraction
    assert responses.kwargs["tools"] == []
    assert responses.kwargs["store"] is False
    assert "secret" not in str(responses.kwargs)
