"""Confidence scoring API schemas — Phase 4.

These Pydantic schemas are used to serialise ConfidenceScore objects
for API responses (e.g. included in JobStatusResponse when status='completed').
"""

from pydantic import BaseModel, Field


class ConfidenceSignalsSchema(BaseModel):
    """Raw signal values that contribute to the overall confidence score."""

    sandbox: float = Field(
        description="Sandbox execution signal (0.0-1.0). 1.0 = all tests passed.",
        ge=0.0,
        le=1.0,
    )
    validation: float = Field(
        description="Validation quality signal (0.0-1.0). 1.0 = zero warnings.",
        ge=0.0,
        le=1.0,
    )
    test_count: float = Field(
        description="Test count signal (0.0-1.0). 1.0 = count in ideal range [6-12].",
        ge=0.0,
        le=1.0,
    )


class ConfidenceMetaSchema(BaseModel):
    """Raw measurement values that the signals are derived from."""

    test_count: int = Field(description="Number of test cases generated.")
    warning_count: int = Field(description="Number of non-fatal validation warnings.")
    sandbox_exit_code: int | None = Field(
        default=None,
        description="Sandbox process exit code. None = sandbox not executed.",
    )


class ConfidenceSchema(BaseModel):
    """Complete confidence assessment for a completed generation job.

    Returned as part of JobStatusResponse.confidence when
    settings.ENABLE_CONFIDENCE=True and status='completed'.
    """

    overall: float = Field(
        description="Weighted confidence score in [0.0, 1.0].",
        ge=0.0,
        le=1.0,
    )
    grade: str = Field(
        description="Human-readable grade: HIGH (≥0.80), MEDIUM (≥0.55), LOW (<0.55).",
        pattern="^(HIGH|MEDIUM|LOW)$",
    )
    signals: ConfidenceSignalsSchema
    metadata: ConfidenceMetaSchema
