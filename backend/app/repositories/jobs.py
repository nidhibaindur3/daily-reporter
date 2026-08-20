from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.db.models.market_intelligence import JobModel
from app.domain.jobs import ClaimedJob


class JobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def claim_next(
        self,
        worker_id: str,
        lease_seconds: int,
        run_id: Optional[str] = None,
    ) -> Optional[ClaimedJob]:
        now = datetime.now(timezone.utc)
        claimable = or_(
            and_(JobModel.status == "queued", JobModel.available_at <= now),
            and_(
                JobModel.status == "running",
                JobModel.lease_expires_at.is_not(None),
                JobModel.lease_expires_at <= now,
            ),
        )
        statement = select(JobModel).where(
            claimable,
            JobModel.attempts < JobModel.max_attempts,
        )
        if run_id is not None:
            statement = statement.where(JobModel.run_id == run_id)
        job = self._session.execute(
            statement.order_by(JobModel.available_at, JobModel.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        ).scalar_one_or_none()
        if job is None:
            self._session.rollback()
            return None

        lease_expires_at = now + timedelta(seconds=lease_seconds)
        job.status = "running"
        job.attempts += 1
        job.locked_by = worker_id
        job.locked_at = now
        job.lease_expires_at = lease_expires_at
        job.updated_at = now
        self._session.commit()
        return ClaimedJob(
            id=job.id,
            run_id=job.run_id,
            job_type=job.job_type,
            attempts=job.attempts,
            max_attempts=job.max_attempts,
            lease_expires_at=lease_expires_at,
        )

    def complete(self, job_id: str) -> None:
        now = datetime.now(timezone.utc)
        job = self._session.get(JobModel, job_id)
        if job is None:
            raise LookupError("job not found")
        job.status = "complete"
        job.locked_by = None
        job.locked_at = None
        job.lease_expires_at = None
        job.error_code = None
        job.updated_at = now
        job.completed_at = now
        self._session.commit()

    def fail(
        self,
        job_id: str,
        error_code: str,
        retry_delay_seconds: int,
        force_terminal: bool = False,
    ) -> bool:
        now = datetime.now(timezone.utc)
        job = self._session.get(JobModel, job_id)
        if job is None:
            raise LookupError("job not found")
        terminal = force_terminal or job.attempts >= job.max_attempts
        job.status = "failed" if terminal else "queued"
        job.available_at = now + timedelta(seconds=retry_delay_seconds)
        job.locked_by = None
        job.locked_at = None
        job.lease_expires_at = None
        job.error_code = error_code
        job.updated_at = now
        job.completed_at = now if terminal else None
        self._session.commit()
        return terminal
