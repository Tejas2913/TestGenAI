"""Unit tests verifying Phase 1 Architecture Scaffolding for TestGen AI v2.2.

Verifies:
  - Domain models (Mutation, TestSmell, TestQuality) instantiate correctly.
  - MutationProvider ABC interface cannot be instantiated directly.
  - App settings contain v2.2 feature flags and quality score weights.
  - Pydantic quality response schemas serialize cleanly.
  - Empty service class methods raise NotImplementedError.
"""

import pytest

from app.core.config import settings
from app.domain.mutation import (
    MutantResult,
    MutationCategory,
    MutationProvider,
    MutationSummary,
)
from app.domain.test_quality import (
    CompositeQualityResult,
    QualityBreakdown,
    SemanticQualityRating,
)
from app.domain.test_smell import (
    TestSmellCategory,
    TestSmellDiagnostic,
    TestSmellSummary,
)
from app.schemas.generation import GenerationResponse, GenerationStatus
from app.schemas.quality import (
    MutantResultResponse,
    MutationSummaryResponse,
    QualityBreakdownResponse,
    QualityMetricsResponse,
    SemanticQualityResponse,
    TestSmellDiagnosticResponse,
    TestSmellSummaryResponse,
)
from app.services.mutation_runner import MutationRunner
from app.services.quality_engine import QualityEngine
from app.services.test_smell_detector import TestSmellDetector


class TestV22QualityScaffolding:
    """Test suite for v2.2 Phase 1 architecture scaffolding."""

    def test_domain_models_instantiation(self) -> None:
        """Verify dataclasses and enums instantiate properly."""
        mutant = MutantResult(
            mutant_id="MUT_1",
            category=MutationCategory.BINARY_OPERATOR,
            description="Changed + to -",
            original_line=10,
            mutated_line_content="return a - b",
            status="KILLED",
        )
        assert mutant.category == MutationCategory.BINARY_OPERATOR
        assert mutant.status == "KILLED"

        mut_summary = MutationSummary(total_mutants=1, killed_mutants=1, mutants=[mutant])
        assert mut_summary.total_mutants == 1

        smell = TestSmellDiagnostic(
            smell_type=TestSmellCategory.ASSERTION_ROULETTE,
            test_name="test_foo",
            line_number=5,
            severity="LOW",
            message="No message",
            recommendation="Add message",
        )
        assert smell.smell_type == TestSmellCategory.ASSERTION_ROULETTE

        smell_summary = TestSmellSummary(total_smells=1, diagnostics=[smell])
        assert smell_summary.total_smells == 1

        semantic = SemanticQualityRating(assertion_strength=8.5)
        breakdown = QualityBreakdown(coverage_score=90.0)
        quality_res = CompositeQualityResult(
            overall_score=88.5,
            rating="GOOD",
            breakdown=breakdown,
            mutation=mut_summary,
            smells=smell_summary,
            semantic=semantic,
        )
        assert quality_res.overall_score == 88.5

    def test_mutation_provider_abc_cannot_be_instantiated(self) -> None:
        """Verify MutationProvider ABC raises TypeError on direct instantiation."""
        with pytest.raises(TypeError):
            MutationProvider()  # type: ignore[abstract]

    def test_v22_settings_present(self) -> None:
        """Verify v2.2 settings exist in App config."""
        assert hasattr(settings, "ENABLE_QUALITY_EVALUATION")
        assert hasattr(settings, "ENABLE_MUTATION_TESTING")
        assert hasattr(settings, "MUTATION_PROVIDER_CLASS")
        assert settings.ENABLE_QUALITY_EVALUATION is False
        assert settings.ENABLE_MUTATION_TESTING is False
        assert settings.QUALITY_WEIGHT_COVERAGE == 0.25
        assert settings.QUALITY_WEIGHT_MUTATION == 0.35
        assert settings.QUALITY_WEIGHT_HYGIENE == 0.20
        assert settings.QUALITY_WEIGHT_SEMANTIC == 0.20

    def test_quality_schemas_serialization(self) -> None:
        """Verify Pydantic response schemas serialize cleanly."""
        mut_resp = MutantResultResponse(
            mutant_id="MUT_1",
            category=MutationCategory.COMPARISON_OPERATOR,
            description="Changed > to <",
            original_line=12,
            mutated_line_content="if a < b:",
            status="KILLED",
        )
        mut_sum_resp = MutationSummaryResponse(
            total_mutants=1, killed_mutants=1, mutants=[mut_resp]
        )
        smell_diag_resp = TestSmellDiagnosticResponse(
            smell_type=TestSmellCategory.DUPLICATE_ASSERTION,
            test_name="test_bar",
            line_number=8,
            severity="MEDIUM",
            message="Duplicate assert",
            recommendation="Deduplicate assert",
        )
        smell_sum_resp = TestSmellSummaryResponse(
            total_smells=1, diagnostics=[smell_diag_resp]
        )
        semantic_resp = SemanticQualityResponse(assertion_strength=9.0)
        breakdown_resp = QualityBreakdownResponse(coverage_score=95.0)

        quality_metrics = QualityMetricsResponse(
            overall_score=92.0,
            rating="EXCELLENT",
            breakdown=breakdown_resp,
            mutation=mut_sum_resp,
            smells=smell_sum_resp,
            semantic=semantic_resp,
        )

        gen_resp = GenerationResponse(
            id="gen-999",
            source_code="def foo(): pass",
            specification=None,
            language="python",
            framework="pytest",
            status=GenerationStatus.COMPLETED,
            generated_tests_json=None,
            generated_tests_code="def test_foo(): pass",
            error_message=None,
            prompt_version="v1",
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            duration_ms=100.0,
            architecture_version="2.2",
            quality_metrics=quality_metrics,
            created_at="2026-07-29T10:00:00Z",
            updated_at="2026-07-29T10:00:00Z",
        )

        data = gen_resp.model_dump()
        assert data["quality_metrics"]["overall_score"] == 92.0
        assert data["quality_metrics"]["rating"] == "EXCELLENT"
        assert data["quality_metrics"]["mutation"]["total_mutants"] == 1

    def test_service_skeletons_raise_not_implemented_error(self) -> None:
        """Verify implemented Phase 2, 3, 4 services instantiate and un-implemented methods raise NotImplementedError."""
        # MutationRunner is implemented in Phase 4
        m_runner = MutationRunner()
        m_res = m_runner.generate_mutants("def f(a, b): return a == b")
        assert len(m_res) >= 1

        # TestSmellDetector is implemented in Phase 2
        detector = TestSmellDetector()
        res = detector.detect("def test_f(): pass")
        assert res.total_smells == 1  # empty test

        # QualityEngine is implemented in Phase 3
        engine = QualityEngine()
        q_res = engine.evaluate_quality(coverage_pct=100.0)
        assert q_res.overall_score == 100.0

        with pytest.raises(NotImplementedError):
            engine.evaluate_semantic_quality("def f(): pass", "def test_f(): pass")
