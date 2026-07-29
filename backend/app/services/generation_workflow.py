"""Generation Workflow Application Coordinator for TestGen AI v2.2.

Coordinates the complete end-to-end business generation lifecycle across:
  AI Test Generation -> Sandbox Execution -> Coverage Analysis ->
  Self-Healing -> QualityPipeline -> Persistence

JobEngine relies on GenerationWorkflow to execute business logic while
JobEngine retains sole responsibility for job state transitions & worker lifecycle.
"""

from typing import Any
import structlog

from app.core.config import settings
from app.models.generation import Generation
from app.repositories.generation_repository import GenerationRepository
from app.services.job_engine import _self_heal
from app.services.quality_pipeline import QualityPipeline

logger = structlog.get_logger(__name__)


class GenerationWorkflow:
    """Application-level workflow coordinator for test generation & quality evaluation."""

    def __init__(
        self,
        quality_pipeline: QualityPipeline | None = None,
    ) -> None:
        """Initialize workflow coordinator with optional QualityPipeline."""
        self.quality_pipeline = quality_pipeline or QualityPipeline()

    def execute_workflow(
        self,
        source_code: str,
        specification: str | None = None,
        language: str = "python",
        framework: str = "pytest",
        job_id: str | None = None,
        provider: Any = None,
        sandbox_client: Any = None,
        gen_repo: GenerationRepository | None = None,
        enable_quality: bool | None = None,
        enable_mutation: bool | None = None,
    ) -> Generation:
        """Execute the complete generation, execution, self-healing, quality, and persistence workflow."""
        # Step 1: Initial AI Test Generation
        if provider is None:
            from app.ai.provider import get_llm_provider
            provider = get_llm_provider()

        generated_raw, prompt_ver, tok_meta = provider.generate_tests(
            source_code=source_code,
            specification=specification,
            language=language,
            framework=framework,
        )

        tests_code = generated_raw.get("rendered_code")

        # Create initial Generation entity
        generation_data = {
            "source_code": source_code,
            "specification": specification,
            "language": language,
            "framework": framework,
            "status": "completed",
            "generated_tests_json": str(generated_raw),
            "generated_tests_code": tests_code,
            "prompt_version": prompt_ver,
            "input_tokens": tok_meta.input_tokens if tok_meta else None,
            "output_tokens": tok_meta.output_tokens if tok_meta else None,
            "total_tokens": tok_meta.total_tokens if tok_meta else None,
            "architecture_version": "V2.2",
        }

        generation = Generation(**generation_data)

        # Step 2: Sandbox Execution & Coverage
        if getattr(settings, "ENABLE_SANDBOX", True) and sandbox_client is not None and tests_code:
            from app.sandbox.schemas import SandboxExecuteRequest
            req = SandboxExecuteRequest(code=tests_code, source_code=source_code)
            sb_res = sandbox_client.execute(req)

            generation.sandbox_exit_code = sb_res.exit_code
            generation.sandbox_stdout = sb_res.stdout
            generation.sandbox_stderr = sb_res.stderr
            generation.sandbox_duration_ms = sb_res.duration_ms

        # Step 3: Self-Healing Pass (if tests failed with repairable error)
        if (
            getattr(settings, "ENABLE_SELF_HEALING", True)
            and getattr(settings, "ENABLE_SANDBOX", True)
            and sandbox_client is not None
            and tests_code
            and generation.sandbox_exit_code is not None
            and generation.sandbox_exit_code != 0
        ):
            try:
                heal_res = _self_heal(
                    job_id=job_id or "workflow",
                    generation=generation,
                    sandbox_client=sandbox_client,
                    provider=provider,
                    log=logger,
                )
                generation.repair_attempted = heal_res.repair_performed
                generation.repair_success = heal_res.repair_success
                generation.repair_count = heal_res.repair_count
                generation.repair_duration_ms = heal_res.repair_duration_ms
                if heal_res.classification:
                    generation.repair_failure_type = str(heal_res.classification.category)
                    generation.repair_reason = heal_res.classification.reason

                if heal_res.repair_performed and heal_res.repaired_code and heal_res.sandbox_result:
                    generation.generated_tests_code = heal_res.repaired_code
                    generation.sandbox_exit_code = heal_res.sandbox_result.exit_code
                    generation.sandbox_stdout = heal_res.sandbox_result.stdout
                    generation.sandbox_stderr = heal_res.sandbox_result.stderr
                    generation.sandbox_duration_ms = heal_res.sandbox_result.duration_ms
            except Exception as heal_exc:
                logger.warning("self_heal_workflow_failed", error=str(heal_exc))

        # Step 4: Quality Pipeline Evaluation & Metrics Persistence
        should_run_quality = True if enable_quality is True else getattr(settings, "ENABLE_QUALITY_EVALUATION", True) or True
        if should_run_quality and generation.generated_tests_code:
            try:
                cov_pct = getattr(generation, "coverage_line_pct", None)
                quality_res = self.quality_pipeline.run_pipeline(
                    source_code=generation.source_code,
                    test_code=generation.generated_tests_code,
                    coverage_pct=cov_pct,
                    sandbox_client=sandbox_client,
                    enable_mutation=enable_mutation,
                )
                self.quality_pipeline.persist_quality_metrics(generation, quality_res)
            except Exception as q_exc:
                logger.warning("quality_pipeline_workflow_failed", error=str(q_exc))

        # Step 5: Save Generation Record to Database
        if gen_repo is not None:
            gen_dict = {
                k: getattr(generation, k)
                for k in [
                    "source_code", "specification", "language", "framework", "status",
                    "generated_tests_json", "generated_tests_code", "prompt_version",
                    "input_tokens", "output_tokens", "total_tokens", "architecture_version",
                    "sandbox_exit_code", "sandbox_stdout", "sandbox_stderr", "sandbox_duration_ms",
                    "coverage_line_pct", "coverage_branch_pct", "coverage_total_statements",
                    "coverage_covered_statements", "coverage_missing_statements",
                    "repair_attempted", "repair_success", "repair_count", "repair_duration_ms",
                    "repair_failure_type", "repair_reason",
                    "quality_score", "quality_rating", "mutation_score", "killed_mutants",
                    "survived_mutants", "timeout_mutants", "error_mutants", "smell_count",
                    "smell_breakdown_json",
                ]
                if hasattr(generation, k) and getattr(generation, k) is not None
            }
            generation = gen_repo.create(gen_dict)

        return generation
