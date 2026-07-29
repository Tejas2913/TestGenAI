"""Job API schemas — Phase 3 / Phase 4.

Request and response models for the async job endpoints:
  POST /api/v2/jobs/generate → JobSubmitResponse (202 Accepted)
  GET  /api/v2/jobs/{job_id} → JobStatusResponse

Phase 4 addition:
  JobStatusResponse.confidence — Optional ConfidenceSchema populated
  when status='completed' and settings.ENABLE_CONFIDENCE=True.

These schemas are deliberately separate from Generation schemas so
the async job lifecycle is self-contained and does not couple to V1
Generation model fields.
"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.confidence import ConfidenceSchema
from app.schemas.quality import QualityMetricsResponse


class JobSubmitRequest(BaseModel):
    """Request body for POST /api/v2/jobs/generate."""

    source_code: str = Field(
        description="Python source code to generate tests for.",
        min_length=1,
    )
    specification: str | None = Field(
        default=None,
        description="Optional plain-English specification or constraints.",
    )
    language: str = Field(
        default="python",
        description="Source code language (V2.1 supports 'python' only).",
    )
    framework: str = Field(
        default="pytest",
        description="Test framework (V2.1 supports 'pytest' only).",
    )


class JobSubmitResponse(BaseModel):
    """Response body for POST /api/v2/jobs/generate (HTTP 202 Accepted).

    The client uses job_id to poll GET /api/v2/jobs/{job_id}.
    """

    job_id: str = Field(description="UUID of the created GenerationJob.")
    status: str = Field(description="Initial job status — always 'pending'.")
    message: str = Field(
        default="Job accepted and queued for processing.",
        description="Human-readable confirmation.",
    )


class JobStatusResponse(BaseModel):
    """Response body for GET /api/v2/jobs/{job_id}.

    Exposes all lifecycle fields required for client polling.
    Sensitive internal fields (checkpoint_payload) are excluded.

    Phase 4: adds optional `confidence` field populated on COMPLETED jobs
    when settings.ENABLE_CONFIDENCE=True.
    """

    job_id: str = Field(description="UUID of the GenerationJob.")
    status: str = Field(description="Current lifecycle status.")
    retry_count: int = Field(description="Number of execution retries.")
    last_checkpoint: str | None = Field(
        default=None,
        description="Last successfully completed pipeline stage name.",
    )
    checkpoint_updated_at: datetime | None = Field(
        default=None,
        description="Timestamp of the last checkpoint update.",
    )
    generation_id: str | None = Field(
        default=None,
        description="ID of the resulting Generation record (set on COMPLETED).",
    )
    error_code: str | None = Field(
        default=None,
        description="Error classification code (set on FAILED).",
    )
    error_detail: str | None = Field(
        default=None,
        description="Human-readable error message (set on FAILED).",
    )
    created_at: datetime = Field(description="Job creation timestamp.")
    updated_at: datetime = Field(description="Last status change timestamp.")

    # Phase 4: confidence metadata for completed jobs
    confidence: ConfidenceSchema | None = Field(
        default=None,
        description=(
            "Confidence score for the completed generation. "
            "Populated when status='completed' and ENABLE_CONFIDENCE=True."
        ),
    )

    # Feature #3: V2.2 Test Quality & Mutation Evaluation metadata
    quality_metrics: QualityMetricsResponse | None = Field(
        default=None,
        description="Quality evaluation metrics for completed job generation",
    )

    model_config = {"from_attributes": True}
