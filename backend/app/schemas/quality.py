"""Pydantic API Response Schemas for Test Quality Evaluation & Mutation Analysis.

V2.2 additive schemas for quality metrics, mutation testing results,
test smell diagnostics, and composite quality ratings.
"""

from enum import StrEnum

from pydantic import BaseModel, Field

from app.domain.mutation import MutationCategory
from app.domain.test_smell import TestSmellCategory


class QualityPipelineStatus(StrEnum):
    """Lifecycle execution status of the Quality Pipeline independent of job status."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class MutantResultResponse(BaseModel):
    """API response model for an individual mutant execution result."""

    mutant_id: str = Field(description="Unique identifier of the mutant")
    category: MutationCategory = Field(description="AST mutation category")
    description: str = Field(description="Human-readable description of mutation applied")
    original_line: int = Field(description="Line number in source code where mutation occurred")
    mutated_line_content: str = Field(description="Mutated line content")
    status: str = Field(description="Mutant execution outcome (KILLED, SURVIVED, TIMEOUT, INCOMPATIBLE)")
    killing_test: str | None = Field(default=None, description="Name of the test function that killed this mutant")
    execution_time_ms: float = Field(default=0.0, description="Execution time in milliseconds")


class MutationSummaryResponse(BaseModel):
    """API response model for aggregated mutation testing results."""

    total_mutants: int = Field(default=0, description="Total mutants generated")
    killed_mutants: int = Field(default=0, description="Number of mutants killed by tests")
    survived_mutants: int = Field(default=0, description="Number of mutants that survived")
    timeout_mutants: int = Field(default=0, description="Number of mutants that timed out")
    incompatible_mutants: int = Field(default=0, description="Number of incompatible mutants")
    mutation_score_pct: float = Field(default=0.0, description="Percentage of mutants killed (0.0 to 100.0)")
    duration_ms: float = Field(default=0.0, description="Total mutation pass duration in milliseconds")
    mutants: list[MutantResultResponse] = Field(
        default_factory=list, description="Detailed list of individual mutant outcomes"
    )


class TestSmellDiagnosticResponse(BaseModel):
    """API response model for an individual test smell diagnostic."""

    __test__ = False

    smell_type: TestSmellCategory = Field(description="Category of static test smell")
    test_name: str = Field(description="Name of the test function containing the smell")
    line_number: int = Field(description="Line number where smell was detected")
    severity: str = Field(description="Diagnostic severity level (LOW, MEDIUM, HIGH)")
    message: str = Field(description="Diagnostic message explaining the smell")
    recommendation: str = Field(description="Actionable recommendation to resolve the smell")


class TestSmellSummaryResponse(BaseModel):
    """API response model for aggregated test smell scan findings."""

    __test__ = False

    total_smells: int = Field(default=0, description="Total number of test smells detected")
    high_severity_count: int = Field(default=0, description="Number of high-severity smells")
    medium_severity_count: int = Field(default=0, description="Number of medium-severity smells")
    low_severity_count: int = Field(default=0, description="Number of low-severity smells")
    diagnostics: list[TestSmellDiagnosticResponse] = Field(
        default_factory=list, description="List of individual smell diagnostics"
    )


class SemanticQualityResponse(BaseModel):
    """API response model for LLM-assisted semantic quality ratings."""

    assertion_strength: float = Field(default=0.0, description="Assertion strength rating (1.0 to 10.0)")
    edge_case_coverage: float = Field(default=0.0, description="Edge case coverage rating (1.0 to 10.0)")
    readability: float = Field(default=0.0, description="Test code readability rating (1.0 to 10.0)")
    exception_handling: float = Field(default=0.0, description="Exception handling rating (1.0 to 10.0)")
    reasoning: str = Field(default="", description="LLM qualitative reasoning narrative")


class QualityBreakdownResponse(BaseModel):
    """API response model for Quality Score sub-score component weights."""

    coverage_score: float = Field(default=0.0, description="Line & branch coverage sub-score (0.0 to 100.0)")
    mutation_score: float = Field(default=0.0, description="Mutation score sub-score (0.0 to 100.0)")
    smell_hygiene_score: float = Field(default=0.0, description="Code smell hygiene sub-score (0.0 to 100.0)")
    semantic_score: float = Field(default=0.0, description="Semantic quality sub-score (0.0 to 100.0)")


class QualityMetricsResponse(BaseModel):
    """API response model for complete test quality evaluation results."""

    overall_score: float = Field(default=0.0, description="Composite Quality Score (0.0 to 100.0)")
    rating: str = Field(default="UNKNOWN", description="Qualitative rating label (EXCELLENT, GOOD, FAIR, NEEDS_IMPROVEMENT)")
    pipeline_status: QualityPipelineStatus = Field(
        default=QualityPipelineStatus.COMPLETED, description="Execution status of Quality Pipeline"
    )
    breakdown: QualityBreakdownResponse = Field(
        default_factory=QualityBreakdownResponse, description="Component weight sub-score breakdown"
    )
    mutation: MutationSummaryResponse = Field(
        default_factory=MutationSummaryResponse, description="Mutation testing summary"
    )
    smells: TestSmellSummaryResponse = Field(
        default_factory=TestSmellSummaryResponse, description="Test smell scan summary"
    )
    semantic: SemanticQualityResponse = Field(
        default_factory=SemanticQualityResponse, description="Semantic quality ratings"
    )
    evaluation_duration_ms: float = Field(default=0.0, description="Total quality evaluation duration in ms")

    model_config = {"from_attributes": True}
