"""Generation ORM model.

V1.0 Frozen Baseline.

New columns must be added as nullable with a default so that existing
records and Alembic-less development deployments are unaffected.
"""

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import BaseModel


class Generation(BaseModel):
    """Represents a single test generation request and its results.

    Stores the input source code, specification, configuration,
    and the generated output (parsed JSON and rendered pytest code).

    architecture_version records which architecture produced this record,
    enabling cross-version comparison in future history views.
    """

    __tablename__ = "generations"

    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    specification: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str] = mapped_column(String(50), default="python")
    framework: Mapped[str] = mapped_column(String(50), default="pytest")
    status: Mapped[str] = mapped_column(String(20), default="pending")

    generated_tests_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_tests_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Phase 4.5: Production hardening fields
    prompt_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    # V1.0: Architecture version that produced this record.
    # Allows history to distinguish V1/V2/V3 generations.
    # Nullable so legacy rows and test fixtures without this field
    # remain valid — new records always populate it via the service.
    architecture_version: Mapped[str | None] = mapped_column(
        String(20), nullable=True, default=None
    )

    # Phase 3: Sandbox execution results — nullable so records produced
    # before sandbox was enabled (or with ENABLE_SANDBOX=False) remain valid.
    # Populated by GenerationService when sandbox_client is injected and
    # ENABLE_SANDBOX=True.
    sandbox_exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sandbox_stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    sandbox_stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
    sandbox_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Code Coverage metrics (coverage.py integration)
    coverage_line_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    coverage_branch_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    coverage_total_statements: Mapped[int | None] = mapped_column(Integer, nullable=True)
    coverage_covered_statements: Mapped[int | None] = mapped_column(Integer, nullable=True)
    coverage_missing_statements: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Feature #2: Self-Healing Test Generation metadata
    repair_attempted: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    repair_success: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    repair_count: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    repair_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    repair_failure_type: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    repair_reason: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)

    # Feature #3: Test Quality & Mutation Evaluation metadata
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_rating: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mutation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    mutation_duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    killed_mutants: Mapped[int | None] = mapped_column(Integer, nullable=True)
    survived_mutants: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timeout_mutants: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_mutants: Mapped[int | None] = mapped_column(Integer, nullable=True)
    smell_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    smell_breakdown_json: Mapped[str | None] = mapped_column(Text, nullable=True)
