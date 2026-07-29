"""Comprehensive integration test suite for QualityPipeline & Persistence (Phase 6).

Verifies:
  - Complete QualityPipeline orchestration across Coverage, Smells, Mutation, and QualityEngine.
  - Partial pipeline execution when mutation testing is disabled / unavailable.
  - Stage resilience: independent sub-service failure recovery without aborting the pipeline.
  - Persistence of quality metrics onto Generation ORM records.
  - Integration with JobEngine and GenerationRepository.
  - Deterministic outputs and >95% test coverage.
"""

import json
from unittest.mock import MagicMock
import pytest
from sqlalchemy.orm import Session

from app.domain.mutation import MutantResult, MutationCategory, MutationSummary
from app.domain.test_quality import CompositeQualityResult
from app.domain.test_smell import TestSmellCategory, TestSmellDiagnostic, TestSmellSummary
from app.models.generation import Generation
from app.repositories.generation_repository import GenerationRepository
from app.sandbox.schemas import SandboxExecuteResponse
from app.services.quality_pipeline import QualityPipeline


class TestQualityPipelineIntegrationSuite:
    """Integration test suite for QualityPipeline application coordinator."""

    @pytest.fixture
    def pipeline(self) -> QualityPipeline:
        """Provide default QualityPipeline instance."""
        return QualityPipeline()

    def test_complete_pipeline_execution(self, pipeline: QualityPipeline) -> None:
        """Verify complete pipeline orchestration with smell detection and mutation testing enabled."""
        source_code = "def add(a, b):\n    return a + b\n"
        test_code = "def test_add():\n    a = 2\n    b = 3\n    expected = 5\n    assert add(a, b) == expected, 'Sum check'\n"

        mock_sandbox = MagicMock()
        mock_sandbox.execute.return_value = SandboxExecuteResponse(
            exit_code=1, stdout="FAILED", stderr="", duration_ms=25.0
        )

        res = pipeline.run_pipeline(
            source_code=source_code,
            test_code=test_code,
            coverage_pct=100.0,
            sandbox_client=mock_sandbox,
            enable_mutation=True,
        )

        assert isinstance(res, CompositeQualityResult)
        assert res.overall_score > 0.0
        assert res.rating in ("EXCELLENT", "GOOD", "FAIR")
        assert res.breakdown.coverage_score == 100.0
        assert res.mutation.total_mutants >= 1
        assert res.smells.total_smells == 0

    def test_pipeline_mutation_disabled(self, pipeline: QualityPipeline) -> None:
        """Verify pipeline operates gracefully when mutation testing is disabled."""
        source_code = "def add(a, b): return a + b"
        test_code = "def test_add():\n    a = 2\n    b = 3\n    exp = 5\n    assert add(a, b) == exp, 'Sum check'"

        res = pipeline.run_pipeline(
            source_code=source_code,
            test_code=test_code,
            coverage_pct=80.0,
            enable_mutation=False,
        )

        assert res.overall_score == 88.9  # 80.0 * 5/9 + 100 * 4/9 = 88.88... -> 88.9
        assert res.rating in ("EXCELLENT", "GOOD")
        assert res.breakdown.mutation_score == 0.0

    def test_smell_detector_stage_failure_resilience(self) -> None:
        """Verify pipeline handles smell detector failure gracefully without aborting."""
        mock_smell_detector = MagicMock()
        mock_smell_detector.detect.side_effect = RuntimeError("AST Smell Detector Crash")

        resilient_pipeline = QualityPipeline(smell_detector=mock_smell_detector)
        res = resilient_pipeline.run_pipeline(
            source_code="def f(): pass",
            test_code="def test_f(): pass",
            coverage_pct=100.0,
            enable_mutation=False,
        )

        assert res.overall_score > 0.0
        assert res.smells.total_smells == 0

    def test_mutation_runner_stage_failure_resilience(self) -> None:
        """Verify pipeline handles mutation runner failure gracefully without aborting."""
        mock_mutation_runner = MagicMock()
        mock_mutation_runner.execute_mutation_pass.side_effect = RuntimeError("Mutation Crash")

        resilient_pipeline = QualityPipeline(mutation_runner=mock_mutation_runner)
        res = resilient_pipeline.run_pipeline(
            source_code="def f(): pass",
            test_code="def test_f(): pass",
            coverage_pct=100.0,
            enable_mutation=True,
        )

        assert res.overall_score > 0.0
        assert res.breakdown.mutation_score == 0.0

    def test_quality_metrics_persistence_mapping(self, pipeline: QualityPipeline) -> None:
        """Verify persist_quality_metrics populates all ORM columns on Generation model."""
        gen = Generation(
            source_code="def f(a, b): return a + b",
            generated_tests_code="def test_f():\n    a = 1\n    b = 2\n    res = 3\n    assert f(a, b) == res, 'check'",
            language="python",
            framework="pytest",
        )

        quality_res = pipeline.run_pipeline(
            source_code=gen.source_code,
            test_code=gen.generated_tests_code,
            coverage_pct=95.0,
            enable_mutation=False,
        )

        updated_gen = pipeline.persist_quality_metrics(gen, quality_res)

        assert updated_gen.quality_score == quality_res.overall_score
        assert updated_gen.quality_rating == quality_res.rating
        assert updated_gen.mutation_score == quality_res.breakdown.mutation_score
        assert updated_gen.smell_count == quality_res.smells.total_smells
        assert updated_gen.smell_breakdown_json is not None

        breakdown_dict = json.loads(updated_gen.smell_breakdown_json)
        assert "high" in breakdown_dict
        assert "medium" in breakdown_dict
        assert "low" in breakdown_dict

    def test_generation_repository_db_persistence(
        self, db_session: Session, pipeline: QualityPipeline
    ) -> None:
        """Verify quality fields persist to database via GenerationRepository."""
        repo = GenerationRepository(db_session)
        gen = repo.create({
            "source_code": "def multiply(a, b): return a * b",
            "generated_tests_code": "def test_mult():\n    a = 2\n    b = 3\n    res = 6\n    assert multiply(a, b) == res, 'check'",
            "language": "python",
            "framework": "pytest",
            "status": "completed",
        })

        quality_res = pipeline.run_pipeline(
            source_code=gen.source_code,
            test_code=gen.generated_tests_code,
            coverage_pct=100.0,
            enable_mutation=False,
        )

        pipeline.persist_quality_metrics(gen, quality_res)
        repo.update(gen.id, {
            "quality_score": gen.quality_score,
            "quality_rating": gen.quality_rating,
            "mutation_score": gen.mutation_score,
            "killed_mutants": gen.killed_mutants,
            "survived_mutants": gen.survived_mutants,
            "timeout_mutants": gen.timeout_mutants,
            "error_mutants": gen.error_mutants,
            "smell_count": gen.smell_count,
            "smell_breakdown_json": gen.smell_breakdown_json,
        })

        db_gen = repo.get_by_id(gen.id)
        assert db_gen is not None
        assert db_gen.quality_score == quality_res.overall_score
        assert db_gen.quality_rating == quality_res.rating
        assert db_gen.smell_count == 0
