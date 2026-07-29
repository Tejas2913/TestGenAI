"""Pydantic schemas for the Generation resource.

V1.0 Contract — frozen baseline.
Fields must NOT be renamed or removed. V2 extensions must be additive
(new optional fields with defaults).

V1 GenerationResponse contract:
  id                   — UUID string, primary key
  source_code          — original submitted source
  specification        — optional natural-language specification
  language             — target language (default: "python")
  framework            — test framework (default: "pytest")
  status               — GenerationStatus enum
  generated_tests_json — structured JSON string (null on failure)
  generated_tests_code — plain-text test code (null on failure)
  error_message        — human-readable error (null on success)
  prompt_version       — which prompt version was used (e.g. "v1")
  input_tokens         — LLM input token count (null on failure)
  output_tokens        — LLM output token count (null on failure)
  total_tokens         — input + output tokens (null on failure)
  duration_ms          — end-to-end generation time in ms (null on failure)
  architecture_version — architecture that produced this record (e.g. "1.0")
  created_at           — UTC timestamp of record creation
  updated_at           — UTC timestamp of last update
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


from app.domain.failure_classifier import FailureCategory


from app.schemas.quality import QualityMetricsResponse


class GenerationStatus(StrEnum):
    """Lifecycle status of a generation request."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class GenerationCreate(BaseModel):
    """Request body for creating a new test generation.

    Input size limits are enforced here as the first line of defense.
    Configurable limits are applied at the service layer; these are
    hard upper bounds.
    """

    source_code: str = Field(
        min_length=1,
        max_length=100_000,
        description="Python source code to test (max 100KB)",
    )
    specification: str | None = Field(
        default=None,
        max_length=50_000,
        description="Natural language specification (max 50KB)",
    )
    language: str = Field(default="python", description="Source code language")
    framework: str = Field(default="pytest", description="Test framework to target")


class GenerationResponse(BaseModel):
    """Response body representing a Generation record.

    V1.0 frozen contract — see module docstring for field definitions.

    Phase 3 additions (all optional, None when sandbox disabled):
      sandbox_exit_code    — 0=pass, 1=fail, -1=unavailable, None=not run
      sandbox_stdout       — captured pytest stdout
      sandbox_stderr       — captured pytest stderr (tracebacks, errors)
      sandbox_duration_ms  — sandbox wall-clock execution time
    """

    id: str
    source_code: str
    specification: str | None
    language: str
    framework: str
    status: GenerationStatus
    generated_tests_json: str | None
    generated_tests_code: str | None
    error_message: str | None
    prompt_version: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    duration_ms: float | None
    architecture_version: str | None   # which architecture produced this record

    # Phase 3: sandbox execution results (None when sandbox not run)
    sandbox_exit_code: int | None = None
    sandbox_stdout: str | None = None
    sandbox_stderr: str | None = None
    sandbox_duration_ms: float | None = None

    # Code Coverage metrics (None when coverage not available/not run)
    coverage_line_pct: float | None = None
    coverage_branch_pct: float | None = None
    coverage_total_statements: int | None = None
    coverage_covered_statements: int | None = None
    coverage_missing_statements: int | None = None

    # Feature #2: Self-Healing Test Generation metadata
    repair_attempted: bool = False
    repair_success: bool = False
    repair_count: int = 0
    repair_duration_ms: float = 0.0
    repair_failure_type: FailureCategory | None = None
    repair_reason: str | None = None

    # Feature #3: V2.2 Test Quality & Mutation Evaluation metadata
    quality_metrics: QualityMetricsResponse | None = None

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
