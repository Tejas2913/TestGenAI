"""Repository for GenerationJob model — V2.1.

Provides CRUD operations inherited from BaseRepository plus
domain-specific methods required by the async job engine (Phase 3).

Phase 3 additions:
  - atomic_claim()      — optimistic single-winner PENDING→PROCESSING transition
  - save_checkpoint()   — persist pipeline stage progress
  - get_jobs_by_status()— bulk status query for startup recovery
  - mark_orphaned_jobs()— transition all PROCESSING→ORPHANED on startup
"""

from datetime import datetime

from sqlalchemy import text

from app.models.job import (
    JOB_STATUS_ORPHANED,
    JOB_STATUS_PENDING,
    JOB_STATUS_PROCESSING,
    GenerationJob,
)
from app.repositories.base import BaseRepository


class JobRepository(BaseRepository[GenerationJob]):
    """Data access layer for GenerationJob records.

    Inherits standard create / get_by_id / update / get_all from
    BaseRepository. Domain-specific methods for atomic claiming and
    checkpoint writes added in Phase 3.
    """

    model = GenerationJob

    # ------------------------------------------------------------------
    # Phase 3: Atomic job claiming
    # ------------------------------------------------------------------

    def atomic_claim(self, job_id: str) -> bool:
        """Atomically transition a job from PENDING → PROCESSING.

        Uses a single UPDATE statement with a WHERE predicate on both
        ``id`` AND ``status = 'pending'``. This guarantees exactly one
        worker wins the race; all others see rowcount == 0 and skip.

        Args:
            job_id: The job to claim.

        Returns:
            True  — this worker successfully claimed the job.
            False — another worker already claimed it (or it does not exist).
        """
        result = self._session.execute(
            text(
                "UPDATE generation_jobs "
                "SET status = :new_status, updated_at = :now "
                "WHERE id = :job_id AND status = :required_status"
            ),
            {
                "new_status": JOB_STATUS_PROCESSING,
                "now": datetime.utcnow().isoformat(sep=" "),
                "job_id": job_id,
                "required_status": JOB_STATUS_PENDING,
            },
        )
        self._session.commit()
        return result.rowcount == 1

    # ------------------------------------------------------------------
    # Phase 3: Checkpoint persistence
    # ------------------------------------------------------------------

    def save_checkpoint(
        self,
        job_id: str,
        checkpoint_name: str,
        payload_json: str | None = None,
    ) -> None:
        """Persist the last successfully completed pipeline stage.

        This is called after each pipeline stage completes so that a
        crashed/orphaned job can resume from here instead of restarting
        the entire pipeline.

        Args:
            job_id:          The job being executed.
            checkpoint_name: One of the CHECKPOINT_* constants from
                             app.models.job (e.g. CHECKPOINT_LLM_RESPONDED).
            payload_json:    Optional serialised JSON output of the stage
                             (e.g. the raw LLM response at LLM_RESPONDED).
        """
        self._session.execute(
            text(
                "UPDATE generation_jobs "
                "SET last_checkpoint = :cp, "
                "    checkpoint_payload = :payload, "
                "    checkpoint_updated_at = :now, "
                "    updated_at = :now "
                "WHERE id = :job_id"
            ),
            {
                "cp": checkpoint_name,
                "payload": payload_json,
                "now": datetime.utcnow().isoformat(sep=" "),
                "job_id": job_id,
            },
        )
        self._session.commit()

    # ------------------------------------------------------------------
    # Phase 3: Startup recovery helpers
    # ------------------------------------------------------------------

    def get_jobs_by_status(self, status: str) -> list[GenerationJob]:
        """Return all jobs with the given status value.

        Used by startup recovery to find PROCESSING and ORPHANED jobs.
        """
        from sqlalchemy import select
        return list(
            self._session.scalars(
                select(GenerationJob).where(GenerationJob.status == status)
            )
        )

    def mark_orphaned_jobs(self) -> list[str]:
        """Transition all PROCESSING jobs → ORPHANED.

        Called once at application startup.  A job still in PROCESSING
        at startup means the previous process crashed mid-execution.

        Returns:
            List of job IDs that were marked ORPHANED.
        """
        result = self._session.execute(
            text(
                "UPDATE generation_jobs "
                "SET status = :orphaned, updated_at = :now "
                "WHERE status = :processing"
            ),
            {
                "orphaned": JOB_STATUS_ORPHANED,
                "processing": JOB_STATUS_PROCESSING,
                "now": datetime.utcnow().isoformat(sep=" "),
            },
        )
        self._session.commit()

        if result.rowcount == 0:
            return []

        # Return the IDs we just orphaned so the engine can schedule retries.
        from sqlalchemy import select
        orphaned = list(
            self._session.scalars(
                select(GenerationJob.id).where(
                    GenerationJob.status == JOB_STATUS_ORPHANED
                )
            )
        )
        return orphaned

    def claim_for_retry(self, job_id: str) -> bool:
        """Transition an ORPHANED job → PENDING so it can be re-claimed.

        Increments retry_count atomically. Returns True if the job was
        successfully transitioned (i.e. it was still ORPHANED).
        """
        result = self._session.execute(
            text(
                "UPDATE generation_jobs "
                "SET status = :pending, "
                "    retry_count = retry_count + 1, "
                "    updated_at = :now "
                "WHERE id = :job_id AND status = :orphaned"
            ),
            {
                "pending": JOB_STATUS_PENDING,
                "orphaned": JOB_STATUS_ORPHANED,
                "now": datetime.utcnow().isoformat(sep=" "),
                "job_id": job_id,
            },
        )
        self._session.commit()
        return result.rowcount == 1
