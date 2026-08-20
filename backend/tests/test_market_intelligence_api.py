from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api.dependencies import get_market_intelligence_service
from app.domain.market_intelligence import DiscoveryRun
from app.main import app
from app.services.market_intelligence import MarketIntelligenceNotConfiguredError

NOW = datetime(2026, 8, 19, 18, tzinfo=timezone.utc)


def run_record() -> DiscoveryRun:
    return DiscoveryRun(
        id="run-1",
        status="queued",
        current_stage="sources",
        window_hours=48,
        maximum_themes=3,
        focus_topics=("grid infrastructure",),
        workflow_version="market_intelligence.workflow.v1",
        error_code=None,
        created_at=NOW,
        updated_at=NOW,
        completed_at=None,
    )


class SuccessfulService:
    def start_run(self, window_hours, maximum_themes, focus_topics):
        assert window_hours == 48
        assert maximum_themes == 3
        assert focus_topics == ("grid infrastructure",)
        return run_record()


class UnconfiguredService:
    def start_run(self, window_hours, maximum_themes, focus_topics):
        raise MarketIntelligenceNotConfiguredError("not configured")


def test_start_discovery_run_returns_durable_job_status() -> None:
    app.dependency_overrides[get_market_intelligence_service] = SuccessfulService
    try:
        response = TestClient(app).post(
            "/api/v1/market-intelligence/runs",
            json={
                "window_hours": 48,
                "maximum_themes": 3,
                "focus_topics": [" Grid Infrastructure "],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["run_id"] == "run-1"
    assert response.json()["current_stage"] == "sources"


def test_start_discovery_run_requires_model_configuration() -> None:
    app.dependency_overrides[get_market_intelligence_service] = UnconfiguredService
    try:
        response = TestClient(app).post(
            "/api/v1/market-intelligence/runs",
            json={"window_hours": 48, "maximum_themes": 3},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"detail": "market intelligence is not configured"}
