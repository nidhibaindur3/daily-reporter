import logging
from time import perf_counter
from typing import Any, Literal, Optional, Protocol, TypeVar

from openai import OpenAIError
from pydantic import BaseModel, ValidationError

from app.ai.contracts import AIInvalidOutputError, AINotConfiguredError, AIProviderError
from app.ai.market_intelligence_contracts import (
    ClaimExtraction,
    ContradictionReview,
    ThemeFormation,
    ThesisDraft,
)
from app.ai.market_intelligence_prompts import (
    CLAIM_EXTRACTION_INSTRUCTIONS,
    CONTRADICTION_INSTRUCTIONS,
    THEME_FORMATION_INSTRUCTIONS,
    THESIS_INSTRUCTIONS,
    build_stage_input,
)

logger = logging.getLogger(__name__)
OutputT = TypeVar("OutputT", bound=BaseModel)


class ParsedResponse(Protocol):
    id: str
    output_parsed: Optional[BaseModel]
    usage: Optional[Any]
    status: Optional[str]


class ResponsesParser(Protocol):
    def parse(self, **kwargs: object) -> ParsedResponse:
        """Parse a structured Responses API result."""
        ...


class OpenAIClient(Protocol):
    responses: ResponsesParser


class OpenAIMarketIntelligenceModel:
    def __init__(
        self,
        client: OpenAIClient,
        model: str,
        max_output_tokens: int,
        reasoning_effort: Literal["minimal", "low", "medium", "high"],
        verbosity: Literal["low", "medium", "high"],
    ) -> None:
        self._client = client
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._reasoning_effort = reasoning_effort
        self._verbosity = verbosity

    def extract_claims(self, input_packet: dict[str, object]) -> ClaimExtraction:
        return self._parse(
            "claim_extraction",
            CLAIM_EXTRACTION_INSTRUCTIONS,
            input_packet,
            ClaimExtraction,
        )

    def form_themes(self, input_packet: dict[str, object]) -> ThemeFormation:
        return self._parse(
            "theme_formation",
            THEME_FORMATION_INSTRUCTIONS,
            input_packet,
            ThemeFormation,
        )

    def review_contradictions(
        self, input_packet: dict[str, object]
    ) -> ContradictionReview:
        return self._parse(
            "contradiction_review",
            CONTRADICTION_INSTRUCTIONS,
            input_packet,
            ContradictionReview,
        )

    def synthesize_thesis(self, input_packet: dict[str, object]) -> ThesisDraft:
        return self._parse(
            "thesis_synthesis",
            THESIS_INSTRUCTIONS,
            input_packet,
            ThesisDraft,
        )

    def _parse(
        self,
        stage: str,
        instructions: str,
        packet: dict[str, object],
        output_type: type[OutputT],
    ) -> OutputT:
        started_at = perf_counter()
        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=instructions,
                input=build_stage_input(stage, packet),
                text_format=output_type,
                max_output_tokens=self._max_output_tokens,
                store=False,
                tools=[],
                reasoning={"effort": self._reasoning_effort},
                text={"verbosity": self._verbosity},
            )
        except ValidationError as exc:
            locations = ",".join(
                ".".join(str(item) for item in error["loc"])
                for error in exc.errors(include_input=False)
            )
            self._log_failure(
                stage,
                started_at,
                f"schema_validation:{locations or 'unknown'}",
            )
            raise AIInvalidOutputError("structured model output was invalid") from exc
        except OpenAIError as exc:
            self._log_failure(stage, started_at, type(exc).__name__)
            raise AIProviderError("model provider request failed") from exc

        parsed = response.output_parsed
        if parsed is None or not isinstance(parsed, output_type):
            self._log_failure(stage, started_at, "missing_parsed_output")
            raise AIInvalidOutputError("model response did not contain parsed output")

        latency_ms = round((perf_counter() - started_at) * 1000)
        usage = response.usage
        logger.info(
            "market_intelligence_model_completed stage=%s model=%s latency_ms=%d "
            "input_tokens=%d output_tokens=%d total_tokens=%d",
            stage,
            self._model,
            latency_ms,
            getattr(usage, "input_tokens", 0),
            getattr(usage, "output_tokens", 0),
            getattr(usage, "total_tokens", 0),
        )
        return parsed

    def _log_failure(self, stage: str, started_at: float, reason: str) -> None:
        logger.warning(
            "market_intelligence_model_failed stage=%s model=%s "
            "latency_ms=%d reason=%s",
            stage,
            self._model,
            round((perf_counter() - started_at) * 1000),
            reason,
        )


class UnconfiguredMarketIntelligenceModel:
    def _raise(self) -> None:
        raise AINotConfiguredError("OpenAI API key is not configured")

    def extract_claims(self, input_packet: dict[str, object]) -> ClaimExtraction:
        del input_packet
        self._raise()
        raise AssertionError("unreachable")

    def form_themes(self, input_packet: dict[str, object]) -> ThemeFormation:
        del input_packet
        self._raise()
        raise AssertionError("unreachable")

    def review_contradictions(
        self, input_packet: dict[str, object]
    ) -> ContradictionReview:
        del input_packet
        self._raise()
        raise AssertionError("unreachable")

    def synthesize_thesis(self, input_packet: dict[str, object]) -> ThesisDraft:
        del input_packet
        self._raise()
        raise AssertionError("unreachable")
