"""Quality Pipeline Application Orchestrator for TestGen AI v2.2.

Coordinates static test smell detection, AST code mutation generation/execution,
composite quality score calculation, and database persistence.
Fails stages independently to provide resilient partial quality evaluations.
"""

import json
from typing import Any
import structlog

from app.core.config import settings
from app.domain.mutation import MutationSummary
from app.domain.test_quality import CompositeQualityResult
from app.domain.test_smell import TestSmellSummary
from app.models.generation import Generation
from app.services.mutation_execution.docker_executor import DockerMutationExecutor
from app.services.mutation_runner import MutationRunner
from app.services.quality_engine import QualityEngine
from app.services.test_smell_detector import TestSmellDetector

logger = structlog.get_logger(__name__)


class QualityPipeline:
    """Application-level coordinator for the TestGen AI v2.2 quality subsystem."""

    def __init__(
        self,
        smell_detector: TestSmellDetector | None = None,
        mutation_runner: MutationRunner | None = None,
        mutation_executor: Any | None = None,
        quality_engine: QualityEngine | None = None,
    ) -> None:
        """Initialize pipeline with injected or default services."""
        self.smell_detector = smell_detector or TestSmellDetector()
        self.mutation_runner = mutation_runner or MutationRunner()
        self.mutation_executor = mutation_executor or DockerMutationExecutor()
        self.quality_engine = quality_engine or QualityEngine()

    def run_pipeline(
        self,
        source_code: str,
        test_code: str,
        coverage_pct: float | None = None,
        sandbox_client: Any = None,
        enable_mutation: bool | None = None,
    ) -> CompositeQualityResult:
        """Execute complete quality evaluation workflow across specialized sub-services.

        Execution Order:
          Coverage -> TestSmellDetector -> MutationRunner/Executor -> QualityEngine

        Stage Resiliency: Each sub-service call is isolated in a try-except block.
        Partial failures fall back gracefully to partial score calculations.
        """
        # Stage 1: Static Test Smell Detection
        smell_summary: TestSmellSummary | None = None
        try:
            smell_summary = self.smell_detector.detect(test_code)
        except Exception as exc:
            logger.warning("quality_pipeline_smell_detector_failed", error=str(exc))
            smell_summary = TestSmellSummary()

        # Stage 2: AST Mutation Testing
        mutation_summary: MutationSummary | None = None
        should_run_mutation = (
            enable_mutation
            if enable_mutation is not None
            else getattr(settings, "ENABLE_MUTATION_TESTING", False)
        )

        if should_run_mutation:
            try:
                mutation_summary = self.mutation_runner.execute_mutation_pass(
                    source_code=source_code,
                    test_code=test_code,
                    sandbox_client=sandbox_client,
                )
            except Exception as exc:
                logger.warning("quality_pipeline_mutation_failed", error=str(exc))
                mutation_summary = None

        # Stage 3: Composite Score Computation & Qualitative Rating Classification
        try:
            return self.quality_engine.compute_composite_score(
                coverage_pct=coverage_pct,
                smell_summary=smell_summary,
                mutation_summary=mutation_summary,
                semantic_rating=None,
            )
        except Exception as exc:
            logger.warning("quality_pipeline_quality_engine_failed", error=str(exc))
            return CompositeQualityResult()

    def persist_quality_metrics(
        self,
        generation: Generation,
        quality_result: CompositeQualityResult,
    ) -> Generation:
        """Persist quality result fields onto a Generation ORM record."""
        generation.quality_score = quality_result.overall_score
        generation.quality_rating = quality_result.rating
        generation.mutation_score = quality_result.breakdown.mutation_score

        mut = quality_result.mutation
        generation.killed_mutants = mut.killed_mutants
        generation.survived_mutants = mut.survived_mutants
        generation.timeout_mutants = mut.timeout_mutants
        generation.error_mutants = mut.incompatible_mutants

        smells = quality_result.smells
        generation.smell_count = smells.total_smells

        smell_breakdown = {
            "high": smells.high_severity_count,
            "medium": smells.medium_severity_count,
            "low": smells.low_severity_count,
        }
        generation.smell_breakdown_json = json.dumps(smell_breakdown)

        return generation
