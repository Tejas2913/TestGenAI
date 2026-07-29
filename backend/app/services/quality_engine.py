"""Quality Engine Service for TestGen AI v2.2.

Pure computation service that calculates weighted composite Quality Scores (0-100),
dynamically normalizes active component weights, and classifies qualitative ratings.
Stateless, deterministic, and free of I/O or side-effects.
"""

from typing import Any
import structlog

from app.core.config import settings
from app.domain.mutation import MutationSummary
from app.domain.test_quality import (
    CompositeQualityResult,
    QualityBreakdown,
    SemanticQualityRating,
)
from app.domain.test_smell import TestSmellSummary

logger = structlog.get_logger(__name__)


class QualityEngine:
    """Calculates composite quality scores (0-100) and qualitative ratings."""

    def __init__(self, provider: Any = None) -> None:
        """Initialize QualityEngine with optional LLM provider for semantic review."""
        self.provider = provider

    def normalize_weights(self, active_components: dict[str, bool]) -> dict[str, float]:
        """Dynamically normalize active component weights so their sum equals 1.0.

        Active components map keys ('coverage', 'mutation', 'hygiene', 'semantic')
        to booleans indicating whether evaluation data is present.
        """
        configured_weights = {
            "coverage": getattr(settings, "QUALITY_WEIGHT_COVERAGE", 0.25),
            "mutation": getattr(settings, "QUALITY_WEIGHT_MUTATION", 0.35),
            "hygiene": getattr(settings, "QUALITY_WEIGHT_HYGIENE", 0.20),
            "semantic": getattr(settings, "QUALITY_WEIGHT_SEMANTIC", 0.20),
        }

        active_sum = sum(
            configured_weights[k]
            for k, is_active in active_components.items()
            if is_active and k in configured_weights
        )

        if active_sum <= 0:
            return {k: 0.0 for k in configured_weights}

        return {
            k: (configured_weights[k] / active_sum) if active_components.get(k, False) else 0.0
            for k in configured_weights
        }

    def calculate_rating(self, score: float) -> str:
        """Classify a composite Quality Score (0-100) into a qualitative rating string."""
        excellent_min = getattr(settings, "QUALITY_THRESHOLD_EXCELLENT", 90.0)
        good_min = getattr(settings, "QUALITY_THRESHOLD_GOOD", 80.0)
        fair_min = getattr(settings, "QUALITY_THRESHOLD_FAIR", 60.0)

        clamped = max(0.0, min(100.0, float(score)))

        if clamped >= excellent_min:
            return "EXCELLENT"
        if clamped >= good_min:
            return "GOOD"
        if clamped >= fair_min:
            return "FAIR"
        return "NEEDS_IMPROVEMENT"

    def compute_composite_score(
        self,
        coverage_pct: float | None = None,
        smell_summary: TestSmellSummary | None = None,
        mutation_summary: MutationSummary | None = None,
        semantic_rating: SemanticQualityRating | None = None,
        evaluation_duration_ms: float = 0.0,
    ) -> CompositeQualityResult:
        """Calculate composite Quality Score (0-100) with dynamic weight normalization."""
        try:
            active_components = {
                "coverage": coverage_pct is not None,
                "mutation": mutation_summary is not None,
                "hygiene": smell_summary is not None,
                "semantic": semantic_rating is not None,
            }

            norm_weights = self.normalize_weights(active_components)

            # Sub-score 1: Coverage
            cov_subscore = 0.0
            if coverage_pct is not None:
                cov_subscore = max(0.0, min(100.0, float(coverage_pct)))

            # Sub-score 2: Mutation
            mut_subscore = 0.0
            if mutation_summary is not None:
                mut_subscore = max(0.0, min(100.0, float(mutation_summary.mutation_score_pct)))

            # Sub-score 3: Code Smell Hygiene
            hygiene_subscore = 0.0
            if smell_summary is not None:
                high_deduction = smell_summary.high_severity_count * 15.0
                med_deduction = smell_summary.medium_severity_count * 8.0
                low_deduction = smell_summary.low_severity_count * 3.0
                total_deduction = high_deduction + med_deduction + low_deduction
                hygiene_subscore = max(0.0, min(100.0, 100.0 - total_deduction))

            # Sub-score 4: Semantic Quality Rating
            semantic_subscore = 0.0
            if semantic_rating is not None:
                ratings = [
                    semantic_rating.assertion_strength,
                    semantic_rating.edge_case_coverage,
                    semantic_rating.readability,
                    semantic_rating.exception_handling,
                ]
                valid_ratings = [max(0.0, min(10.0, float(r))) for r in ratings if r > 0.0]
                if valid_ratings:
                    avg_rating = sum(valid_ratings) / len(valid_ratings)
                    semantic_subscore = max(0.0, min(100.0, avg_rating * 10.0))

            breakdown = QualityBreakdown(
                coverage_score=round(cov_subscore, 1),
                mutation_score=round(mut_subscore, 1),
                smell_hygiene_score=round(hygiene_subscore, 1),
                semantic_score=round(semantic_subscore, 1),
            )

            overall_score = (
                cov_subscore * norm_weights["coverage"]
                + mut_subscore * norm_weights["mutation"]
                + hygiene_subscore * norm_weights["hygiene"]
                + semantic_subscore * norm_weights["semantic"]
            )
            overall_score = round(max(0.0, min(100.0, overall_score)), 1)
            rating = self.calculate_rating(overall_score) if any(active_components.values()) else "UNKNOWN"

            return CompositeQualityResult(
                overall_score=overall_score,
                rating=rating,
                breakdown=breakdown,
                mutation=mutation_summary or MutationSummary(),
                smells=smell_summary or TestSmellSummary(),
                semantic=semantic_rating or SemanticQualityRating(),
                evaluation_duration_ms=round(evaluation_duration_ms, 1),
            )
        except Exception as exc:
            logger.warning("quality_engine_computation_error", error=str(exc))
            return CompositeQualityResult(
                overall_score=0.0,
                rating="UNKNOWN",
                breakdown=QualityBreakdown(),
                mutation=mutation_summary or MutationSummary(),
                smells=smell_summary or TestSmellSummary(),
                semantic=semantic_rating or SemanticQualityRating(),
                evaluation_duration_ms=round(evaluation_duration_ms, 1),
            )

    def evaluate_semantic_quality(
        self,
        source_code: str,
        test_code: str,
    ) -> SemanticQualityRating:
        """Evaluate test code semantic quality using LLM assertion review."""
        raise NotImplementedError

    def evaluate_quality(
        self,
        source_code: str = "",
        test_code: str = "",
        coverage_pct: float | None = None,
        smell_summary: TestSmellSummary | None = None,
        mutation_summary: MutationSummary | None = None,
        semantic_rating: SemanticQualityRating | None = None,
        sandbox_client: Any = None,
        evaluation_duration_ms: float = 0.0,
    ) -> CompositeQualityResult:
        """Run complete quality evaluation pipeline across active inputs."""
        return self.compute_composite_score(
            coverage_pct=coverage_pct,
            smell_summary=smell_summary,
            mutation_summary=mutation_summary,
            semantic_rating=semantic_rating,
            evaluation_duration_ms=evaluation_duration_ms,
        )
