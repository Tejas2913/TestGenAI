"""GenerationJob ORM model — V2.1.

Manages the async execution lifecycle of a generation request.
This is strictly separate from the Generation model which stores
the final domain artifact (rendered code, parsed JSON, history).

Checkpoint columns allow recovery from in-progress PROCESSING jobs
after a process restart, without re-running completed pipeline stages.
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel

# Canonical job status values — kept as string constants so the DB column
# remains a plain String and does not require an Enum migration.
JOB_STATUS_PENDING = "pending"
JOB_STATUS_PROCESSING = "processing"
JOB_STATUS_ORPHANED = "orphaned"
JOB_STATUS_RETRYING = "retrying"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"
JOB_STATUS_CANCELLED = "cancelled"

# Valid pipeline checkpoint names, in execution order.
CHECKPOINT_ANALYZED = "ANALYZED"
CHECKPOINT_PROMPTED = "PROMPTED"
CHECKPOINT_LLM_RESPONDED = "LLM_RESPONDED"
CHECKPOINT_PARSED = "PARSED"
CHECKPOINT_SANDBOX_TESTED = "SANDBOX_TESTED"


class GenerationJob(BaseModel):
    """Tracks the asynchronous lifecycle of a single test generation request.

    Responsibilities:
        - Lifecycle state machine (PENDING → PROCESSING → COMPLETED/FAILED)
        - Retry and orphan recovery tracking
        - Pipeline checkpoint persistence for crash recovery
        - Foreign-key link to the resulting Generation record on completion

    This model does NOT store generated code or test output — those live
    in the Generation model and are referenced via generation_id.
    """

    __tablename__ = "generation_jobs"

    # ----------------------------------------------------------------
    # Lifecycle state
    # ----------------------------------------------------------------
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=JOB_STATUS_PENDING,
        index=True,
    )

    # ----------------------------------------------------------------
    # Ownership — user_id is nullable until auth is implemented in Phase 2.
    # It is defined now so Phase 2 only needs to enforce it, not migrate.
    # ----------------------------------------------------------------
    user_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    # ----------------------------------------------------------------
    # Link to the resulting Generation record (set on COMPLETED)
    # ----------------------------------------------------------------
    generation_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )

    # ----------------------------------------------------------------
    # Retry tracking
    # ----------------------------------------------------------------
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # ----------------------------------------------------------------
    # Checkpoint persistence
    # Stores the name of the last successfully completed pipeline stage
    # so that crash recovery can resume rather than restart from scratch.
    # ----------------------------------------------------------------
    last_checkpoint: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    # Serialised JSON output of the checkpointed stage (e.g., raw LLM
    # response stored at LLM_RESPONDED so we can skip the LLM call on retry).
    checkpoint_payload: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    checkpoint_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    # ----------------------------------------------------------------
    # Error information (populated on FAILED)
    # ----------------------------------------------------------------
    error_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
