"""Comprehensive unit test suite for QualityEngine service (Phase 3).

Verifies:
  - Full inputs composite Quality Score calculation.
  - Partial inputs weight auto-normalization (e.g. missing mutation, missing semantic).
  - Hygiene sub-score deductions based on smell severity (HIGH: -15, MEDIUM: -8, LOW: -3).
  - Semantic sub-score scaling from 1-10 rating to 0-100 score.
  - Qualitative rating classification (EXCELLENT, GOOD, FAIR, NEEDS_IMPROVEMENT).
  - Out of bounds / zero / maximum score handling and clamping.
  - Error resilience against unexpected exceptions.
"""

import pytest

from app.core.config import settings
from app.domain.mutation import MutationSummary
from app.domain.test_quality import SemanticQualityRating
from app.domain.test_smell import (
    TestSmellCategory,
    TestSmellDiagnostic,
    TestSmellSummary,
)
from app.services.quality_engine import QualityEngine


class TestQualityEngineSuite:
    """Test suite for QualityEngine score calculation & weight normalization."""

    @pytest.fixture
    def engine(self) -> QualityEngine:
        """Provide default QualityEngine instance."""
        return QualityEngine()

    def test_full_inputs_computation(self, engine: QualityEngine) -> None:
        """Verify composite score calculation with all 4 components active."""
        coverage_pct = 80.0  # 80.0 * 0.25 = 20.0
        mutation = MutationSummary(mutation_score_pct=100.0)  # 100.0 * 0.35 = 35.0
        smells = TestSmellSummary(
            total_smells=1,
            medium_severity_count=1,
            diagnostics=[
                TestSmellDiagnostic(
                    smell_type=TestSmellCategory.DUPLICATE_ASSERTION,
                    test_name="test_foo",
                    line_number=5,
                    severity="MEDIUM",
                    message="Duplicate assert",
                    recommendation="Remove",
                )
            ],
        )  # 100 - 8 = 92.0 * 0.20 = 18.4
        semantic = SemanticQualityRating(
            assertion_strength=9.0,
            edge_case_coverage=9.0,
            readability=9.0,
            exception_handling=9.0,
        )  # 9.0 * 10 = 90.0 * 0.20 = 18.0

        # Overall: 20.0 + 35.0 + 18.4 + 18.0 = 91.4 -> EXCELLENT
        res = engine.evaluate_quality(
            coverage_pct=coverage_pct,
            smell_summary=smells,
            mutation_summary=mutation,
            semantic_rating=semantic,
            evaluation_duration_ms=150.0,
        )

        assert res.overall_score == 91.4
        assert res.rating == "EXCELLENT"
        assert res.breakdown.coverage_score == 80.0
        assert res.breakdown.mutation_score == 100.0
        assert res.breakdown.smell_hygiene_score == 92.0
        assert res.breakdown.semantic_score == 90.0
        assert res.evaluation_duration_ms == 150.0

    def test_missing_mutation_and_semantic_weight_normalization(
        self, engine: QualityEngine
    ) -> None:
        """Verify weight auto-normalization when only Coverage and Smells are active.

        Configured weights:
        Coverage: 0.25, Smells: 0.20 -> Active sum = 0.45
        Normalized Coverage = 0.25 / 0.45 = 5/9 (~0.5555)
        Normalized Smells = 0.20 / 0.45 = 4/9 (~0.4444)
        """
        coverage_pct = 100.0  # 100.0 * (5/9) = 55.555...
        smells = TestSmellSummary(total_smells=0)  # 100.0 * (4/9) = 44.444...

        res = engine.evaluate_quality(
            coverage_pct=coverage_pct,
            smell_summary=smells,
            mutation_summary=None,
            semantic_rating=None,
        )

        assert res.overall_score == 100.0
        assert res.rating == "EXCELLENT"
        assert res.breakdown.coverage_score == 100.0
        assert res.breakdown.smell_hygiene_score == 100.0

    def test_weight_normalization_math_utility(self, engine: QualityEngine) -> None:
        """Verify normalize_weights helper directly."""
        active = {"coverage": True, "mutation": False, "hygiene": True, "semantic": False}
        weights = engine.normalize_weights(active)
        assert abs(weights["coverage"] - (0.25 / 0.45)) < 1e-6
        assert abs(weights["hygiene"] - (0.20 / 0.45)) < 1e-6
        assert weights["mutation"] == 0.0
        assert weights["semantic"] == 0.0
        assert abs(sum(weights.values()) - 1.0) < 1e-6

    def test_no_active_components_returns_zero(self, engine: QualityEngine) -> None:
        """Verify passing None for all components returns 0 score and UNKNOWN rating."""
        res = engine.evaluate_quality()
        assert res.overall_score == 0.0
        assert res.rating == "UNKNOWN"

    @pytest.mark.parametrize(
        "score,expected_rating",
        [
            (95.0, "EXCELLENT"),
            (90.0, "EXCELLENT"),
            (85.0, "GOOD"),
            (80.0, "GOOD"),
            (70.0, "FAIR"),
            (60.0, "FAIR"),
            (59.9, "NEEDS_IMPROVEMENT"),
            (0.0, "NEEDS_IMPROVEMENT"),
        ],
    )
    def test_calculate_rating_thresholds(
        self, engine: QualityEngine, score: float, expected_rating: str
    ) -> None:
        """Test calculate_rating threshold boundaries."""
        assert engine.calculate_rating(score) == expected_rating

    def test_smell_hygiene_deduction_formula(self, engine: QualityEngine) -> None:
        """Verify smell severity deductions: HIGH (-15), MEDIUM (-8), LOW (-3)."""
        smells = TestSmellSummary(
            total_smells=3,
            high_severity_count=1,   # -15
            medium_severity_count=1, # -8
            low_severity_count=1,    # -3
        )  # Total deduction = 26 -> Hygiene score = 74.0

        res = engine.compute_composite_score(smell_summary=smells)
        assert res.breakdown.smell_hygiene_score == 74.0

    def test_excessive_smell_deductions_clamped_to_zero(
        self, engine: QualityEngine
    ) -> None:
        """Verify hygiene sub-score does not go negative when deductions exceed 100."""
        smells = TestSmellSummary(
            total_smells=10,
            high_severity_count=10,  # -150 deduction
        )
        res = engine.compute_composite_score(smell_summary=smells)
        assert res.breakdown.smell_hygiene_score == 0.0

    def test_out_of_bounds_inputs_clamped(self, engine: QualityEngine) -> None:
        """Verify out-of-bounds input values are safely clamped to 0-100 range."""
        coverage_pct = 150.0  # Clamped to 100.0
        semantic = SemanticQualityRating(
            assertion_strength=15.0,  # Clamped to 10.0 -> 100.0 score
        )
        res = engine.compute_composite_score(
            coverage_pct=coverage_pct, semantic_rating=semantic
        )
        assert res.breakdown.coverage_score == 100.0
        assert res.breakdown.semantic_score == 100.0

    def test_evaluate_semantic_quality_raises_not_implemented(
        self, engine: QualityEngine
    ) -> None:
        """Verify LLM semantic evaluation method raises NotImplementedError in Phase 3."""
        with pytest.raises(NotImplementedError):
            engine.evaluate_semantic_quality("def f(): pass", "def test_f(): pass")
