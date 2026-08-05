"""Composite Quality Score Domain Models for TestGen AI v2.2.

Provides domain entities representing semantic quality ratings, sub-score breakdowns,
and composite Quality Score calculation results.
"""

from dataclasses import dataclass, field
from app.domain.mutation import MutationSummary
from app.domain.test_smell import TestSmellSummary


@dataclass
class SemanticQualityRating:
    """LLM-assisted semantic quality evaluation scores on a 1-10 scale."""

    evaluated: bool = False
    assertion_strength: float = 0.0
    edge_case_coverage: float = 0.0
    readability: float = 0.0
    exception_handling: float = 0.0
    reasoning: str = "Semantic quality evaluation was not executed for this job."


@dataclass
class QualityBreakdown:
    """Component weight and sub-score breakdown of the Quality Score."""

    coverage_score: float = 0.0
    mutation_score: float = 0.0
    smell_hygiene_score: float = 0.0
    semantic_score: float | None = None


@dataclass
class CompositeQualityResult:
    """Final aggregated Quality Score result combining all evaluation vectors."""

    overall_score: float = 0.0
    rating: str = "UNKNOWN"
    breakdown: QualityBreakdown = field(default_factory=QualityBreakdown)
    mutation: MutationSummary = field(default_factory=MutationSummary)
    smells: TestSmellSummary = field(default_factory=TestSmellSummary)
    semantic: SemanticQualityRating = field(default_factory=SemanticQualityRating)
    evaluation_duration_ms: float = 0.0
