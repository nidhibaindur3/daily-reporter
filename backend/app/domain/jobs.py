from dataclasses import dataclass
from datetime import datetime
from typing import Literal

JobStatus = Literal["queued", "running", "complete", "failed", "cancelled"]


@dataclass(frozen=True)
class ClaimedJob:
    id: str
    run_id: str
    job_type: str
    attempts: int
    max_attempts: int
    lease_expires_at: datetime
