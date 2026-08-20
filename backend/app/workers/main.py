import logging
import os
import socket
import time
from typing import Optional

from app.core.config import Settings, get_settings
from app.core.container import ApplicationRuntime, build_runtime
from app.db.session import SessionLocal
from app.domain.jobs import ClaimedJob
from app.repositories.jobs import JobRepository
from app.repositories.market_intelligence import MarketIntelligenceRepository
from app.services.market_intelligence import (
    MarketIntelligencePipeline,
    MarketIntelligencePipelineError,
)

logger = logging.getLogger(__name__)


def _claim_job(settings: Settings, worker_id: str) -> Optional[ClaimedJob]:
    with SessionLocal() as session:
        return JobRepository(session).claim_next(
            worker_id=worker_id,
            lease_seconds=settings.market_intelligence_job_lease_seconds,
        )


def _finish_failure(
    job: ClaimedJob,
    settings: Settings,
    error_code: str,
    force_terminal: bool,
) -> None:
    with SessionLocal() as session:
        terminal = JobRepository(session).fail(
            job_id=job.id,
            error_code=error_code,
            retry_delay_seconds=settings.market_intelligence_job_retry_seconds,
            force_terminal=force_terminal,
        )
        MarketIntelligenceRepository(session).fail_run(
            job.run_id,
            error_code,
            terminal=terminal,
        )


def process_job(
    job: ClaimedJob,
    settings: Settings,
    runtime: ApplicationRuntime,
) -> None:
    if job.job_type != "market_intelligence.discovery":
        _finish_failure(job, settings, "unsupported_job_type", True)
        return

    try:
        with SessionLocal() as session:
            pipeline = MarketIntelligencePipeline(
                store=MarketIntelligenceRepository(session),
                news_service=runtime.news_service,
                market_service=runtime.market_service,
                model=runtime.market_intelligence_model,
                source_limit=settings.market_intelligence_source_limit,
            )
            pipeline.run(job.run_id)
        with SessionLocal() as session:
            JobRepository(session).complete(job.id)
    except MarketIntelligencePipelineError as exc:
        logger.warning(
            "market intelligence job failed code=%s retryable=%s",
            exc.error_code,
            exc.retryable,
        )
        _finish_failure(job, settings, exc.error_code, not exc.retryable)
    except Exception:
        logger.exception("market intelligence job failed code=internal_error")
        _finish_failure(job, settings, "internal_error", False)


def run_once(
    settings: Settings,
    runtime: ApplicationRuntime,
    worker_id: str,
) -> bool:
    job = _claim_job(settings, worker_id)
    if job is None:
        return False
    process_job(job, settings, runtime)
    return True


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = get_settings()
    runtime = build_runtime(settings)
    worker_id = f"{socket.gethostname()}:{os.getpid()}"
    logger.info("market intelligence worker started worker_id=%s", worker_id)
    try:
        while True:
            if not run_once(settings, runtime, worker_id):
                time.sleep(settings.market_intelligence_worker_poll_seconds)
    except KeyboardInterrupt:
        logger.info("market intelligence worker stopped")
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
