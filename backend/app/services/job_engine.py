"""Async Job Engine — Phase 3.

This module is the heart of the V2.1 async generation pipeline.

Architecture responsibilities:
  - execute_job()      — Async entry point for BackgroundTasks.
                         Offloads all blocking work to threads.
  - _run_job_sync()   — Synchronous worker: claim, pipeline, checkpoint, repair.
  - startup_recovery() — Called once at startup; recovers PROCESSING → ORPHANED
                          → RETRYING jobs.
  - _self_heal()       — Repair loop for fixable sandbox failures (max 3 attempts).

Concurrency model:
  - FastAPI BackgroundTasks calls execute_job(job_id) — this is async.
  - All blocking SQLAlchemy, LLM, and HTTP calls happen inside
    anyio.to_thread.run_sync() so the event loop is never blocked.

State machine:
  PENDING
    ↓  (atomic_claim succeeds)
  PROCESSING
    ↓  (pipeline + sandbox complete)
  COMPLETED

  PROCESSING → FAILED           (unrecoverable error)
  PROCESSING → ORPHANED         (process crash detected at startup)
  ORPHANED   → RETRYING         (startup recovery, retry_count < MAX_STARTUP_RETRIES)
  RETRYING   → PENDING          (claim_for_retry → re-queued)

Self-healing:
  When sandbox exit_code == 1 and the stderr indicates a fixable error
  (SyntaxError, IndentationError, ModuleNotFoundError), the engine asks
  the LLM to repair the generated code and re-executes the sandbox.
  Maximum MAX_REPAIR_ATTEMPTS repairs per job.
"""

import json
import re

import anyio
import structlog

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.job import (
    CHECKPOINT_ANALYZED,
    CHECKPOINT_LLM_RESPONDED,
    CHECKPOINT_PARSED,
    CHECKPOINT_PROMPTED,
    CHECKPOINT_SANDBOX_TESTED,
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_ORPHANED,
    JOB_STATUS_PENDING,
    JOB_STATUS_RETRYING,
)
from app.ai.providers.gemini_provider import GeminiProvider
from app.infrastructure.providers.router import LLMProviderRouter
from app.repositories.generation_repository import GenerationRepository
from app.repositories.job_repository import JobRepository
from app.services.generation_service import GenerationService

logger = structlog.get_logger(__name__)

# Maximum sandbox repair attempts per job (architecture: max 3).
MAX_REPAIR_ATTEMPTS: int = 3

# Maximum startup retries for orphaned jobs (architecture: max 1).
MAX_STARTUP_RETRIES: int = 1

# Error patterns that indicate the generated code is repairable.
_REPAIRABLE_PATTERNS: list[re.Pattern] = [
    re.compile(r"SyntaxError", re.IGNORECASE),
    re.compile(r"IndentationError", re.IGNORECASE),
    re.compile(r"ModuleNotFoundError", re.IGNORECASE),
    re.compile(r"ImportError", re.IGNORECASE),
]

from app.domain.failure_classifier import classify_sandbox_failure


def _is_repairable(stderr: str) -> bool:
    """Return True iff the sandbox failure is worth attempting to repair.

    Delegates to structured FailureClassifier domain logic.
    """
    classification = classify_sandbox_failure(exit_code=1, stderr=stderr)
    return classification.is_repairable


def _make_repair_prompt(generated_code: str, stderr: str) -> str:
    """Build the LLM repair prompt from the broken code and the error output."""
    return (
        "The following pytest test code has an error. Fix ONLY the error "
        "shown. Do NOT change test logic, assertions, or expected values. "
        "Return ONLY the corrected Python source code — no markdown, no "
        "explanation.\n\n"
        f"Error:\n{stderr[:2000]}\n\n"
        f"Code:\n{generated_code}"
    )


# ---------------------------------------------------------------------------
# Core execution
# ---------------------------------------------------------------------------


def _run_job_sync(job_id: str, input_data: dict) -> None:
    """Synchronous worker — runs in a thread pool via anyio.to_thread.run_sync.

    Args:
        job_id:     The GenerationJob UUID to execute.
        input_data: Dict with source_code, specification, language, framework,
                    resume_from_checkpoint, checkpoint_payload.
    """
    log = logger.bind(job_id=job_id)
    db = SessionLocal()
    try:
        job_repo = JobRepository(db)

        # ----------------------------------------------------------------
        # Step 1: Atomic claim — PENDING → PROCESSING
        # ----------------------------------------------------------------
        claimed = job_repo.atomic_claim(job_id)
        if not claimed:
            log.info("job_claim_skipped", reason="already claimed by another worker")
            return

        log.info("job_claimed")

        # ----------------------------------------------------------------
        # Step 2: Build service collaborators
        # ----------------------------------------------------------------
        gen_repo = GenerationRepository(db)
        # Use the enterprise router so Gemini 503/429 automatically
        # fails over to OpenAI → Claude → Groq → OpenRouter.
        provider = LLMProviderRouter(mock_mode=settings.MOCK_MODE)

        # Inject SandboxClient when sandbox is enabled
        sandbox_client = None
        if settings.ENABLE_SANDBOX:
            from dependencies import get_sandbox_client
            sandbox_client = get_sandbox_client()

        service = GenerationService(
            repository=gen_repo,
            llm_provider=provider,
            sandbox_client=sandbox_client,
        )

        # ----------------------------------------------------------------
        # Step 3: Run the synchronous pipeline
        # ----------------------------------------------------------------
        source_code = input_data["source_code"]
        specification = input_data.get("specification")
        language = input_data.get("language", "python")
        framework = input_data.get("framework", "pytest")
        resume_cp = input_data.get("resume_from_checkpoint")
        cp_payload = input_data.get("checkpoint_payload")

        # Save ANALYZED checkpoint early so we know the pipeline started
        job_repo.save_checkpoint(job_id, CHECKPOINT_ANALYZED)
        log.debug("checkpoint_saved", checkpoint=CHECKPOINT_ANALYZED)

        generation = service.generate(
            source_code=source_code,
            specification=specification,
            language=language,
            framework=framework,
            resume_from_checkpoint=resume_cp,
            checkpoint_payload=cp_payload,
        )

        if generation is None:
            job_repo.update(job_id, {
                "status": JOB_STATUS_FAILED,
                "error_code": "INTERNAL_ERROR",
                "error_detail": "GenerationService returned None",
            })
            log.error("job_generation_returned_none")
            return

        # Save LLM_RESPONDED checkpoint
        job_repo.save_checkpoint(
            job_id,
            CHECKPOINT_LLM_RESPONDED,
            payload_json=json.dumps({"generation_id": generation.id}),
        )

        # ----------------------------------------------------------------
        # Step 4: Self-healing repair loop (if sandbox enabled and failed)
        # ----------------------------------------------------------------
        if (
            settings.ENABLE_SANDBOX
            and settings.ENABLE_SELF_HEAL
            and sandbox_client is not None
            and generation.generated_tests_code
        ):
            heal_res = _self_heal(
                job_id=job_id,
                generation=generation,
                sandbox_client=sandbox_client,
                provider=provider,
                log=log,
            )

            update_fields = {
                "repair_attempted": heal_res.repair_performed,
                "repair_success": heal_res.repair_success,
                "repair_count": heal_res.repair_count,
                "repair_duration_ms": heal_res.repair_duration_ms,
            }
            if heal_res.classification:
                update_fields["repair_failure_type"] = str(heal_res.classification.category)
                update_fields["repair_reason"] = heal_res.classification.reason

            if heal_res.repair_performed and heal_res.repaired_code and heal_res.sandbox_result:
                generation.generated_tests_code = heal_res.repaired_code
                if hasattr(generation, "sandbox_exit_code"):
                    generation.sandbox_exit_code = heal_res.sandbox_result.exit_code
                if hasattr(generation, "sandbox_stdout"):
                    generation.sandbox_stdout = heal_res.sandbox_result.stdout
                if hasattr(generation, "sandbox_stderr"):
                    generation.sandbox_stderr = heal_res.sandbox_result.stderr
                if hasattr(generation, "sandbox_duration_ms"):
                    generation.sandbox_duration_ms = heal_res.sandbox_result.duration_ms

                update_fields["generated_tests_code"] = heal_res.repaired_code
                update_fields["sandbox_exit_code"] = heal_res.sandbox_result.exit_code
                update_fields["sandbox_stdout"] = heal_res.sandbox_result.stdout
                update_fields["sandbox_stderr"] = heal_res.sandbox_result.stderr
                update_fields["sandbox_duration_ms"] = heal_res.sandbox_result.duration_ms

            # Persist repair metadata to DB using existing gen_repo
            gen_repo.update(generation.id, update_fields)

        # ----------------------------------------------------------------
        # Step 4.5: Quality Pipeline evaluation & persistence (V2.2)
        # JobEngine depends ONLY on QualityPipeline, not individual quality services.
        # ----------------------------------------------------------------
        if getattr(settings, "ENABLE_QUALITY_EVALUATION", False) and generation.generated_tests_code:
            try:
                from app.services.quality_pipeline import QualityPipeline
                pipeline = QualityPipeline()
                cov_pct = getattr(generation, "coverage_line_pct", None)
                quality_res = pipeline.run_pipeline(
                    source_code=generation.source_code,
                    test_code=generation.generated_tests_code,
                    coverage_pct=cov_pct,
                    sandbox_client=sandbox_client,
                )
                pipeline.persist_quality_metrics(generation, quality_res)
                gen_repo.update(generation.id, {
                    "quality_score": generation.quality_score,
                    "quality_rating": generation.quality_rating,
                    "mutation_score": generation.mutation_score,
                    "mutation_duration_ms": generation.mutation_duration_ms,
                    "killed_mutants": generation.killed_mutants,
                    "survived_mutants": generation.survived_mutants,
                    "timeout_mutants": generation.timeout_mutants,
                    "error_mutants": generation.error_mutants,
                    "smell_count": generation.smell_count,
                    "smell_breakdown_json": generation.smell_breakdown_json,
                })
            except Exception as q_exc:
                log.warning("quality_pipeline_job_step_failed", error=str(q_exc))

        # ----------------------------------------------------------------
        # Step 5: Save SANDBOX_TESTED checkpoint and mark COMPLETED
        # ----------------------------------------------------------------
        job_repo.save_checkpoint(job_id, CHECKPOINT_SANDBOX_TESTED)
        job_repo.update(job_id, {
            "status": JOB_STATUS_COMPLETED,
            "generation_id": generation.id,
        })
        log.info("job_completed", generation_id=generation.id)

    except Exception as exc:
        log.error("job_execution_failed", error=str(exc), exc_info=True)
        try:
            job_repo.update(job_id, {
                "status": JOB_STATUS_FAILED,
                "error_code": "INTERNAL_ERROR",
                "error_detail": str(exc)[:1000],
            })
        except Exception:
            pass  # DB might be broken; best effort
    finally:
        db.close()


def _self_heal(
    job_id: str,
    generation,
    sandbox_client,
    provider,
    log,
):
    """Self-healing repair pass — pure execution helper that returns SelfHealingResult.

    Flow:
      1. Check initial sandbox execution result. If exit_code == 0, bypass repair pass entirely.
      2. Classify failure via classify_sandbox_failure(). If not repairable, return original failure.
      3. Build surgical repair prompt using PromptBuilder.
      4. Request LLM repair pass. If LLM fails, return original failure.
      5. Pass repaired code through production TestCodeValidator. If validation fails, return original failure.
      6. Re-run sandbox execution ONCE with repaired test code. Return SelfHealingResult.
    """
    import time
    from app.sandbox.schemas import (
        SANDBOX_UNAVAILABLE_EXIT_CODE,
        SandboxExecuteRequest,
    )
    from app.domain.failure_classifier import classify_sandbox_failure
    from app.domain.self_healing import SelfHealingResult
    from app.ai.prompt_builder import PromptBuilder

    current_code = generation.generated_tests_code or ""
    raw_source = getattr(generation, "source_code", None)
    source_code = raw_source if isinstance(raw_source, str) else ""

    # Initial sandbox execution check
    req = SandboxExecuteRequest(
        code=current_code,
        source_code=source_code,
        framework="pytest",
        timeout_seconds=settings.SANDBOX_TIMEOUT_SECONDS,
    )
    initial_result = sandbox_client.execute(req)

    # 1. Success check: bypass repair pass completely
    if initial_result.exit_code == 0:
        log.info("self_heal_bypassed_success")
        return SelfHealingResult(
            repair_performed=False,
            repair_success=False,
            repair_count=0,
            repair_duration_ms=0.0,
            sandbox_result=initial_result,
            initial_result=initial_result,
        )

    if initial_result.exit_code == SANDBOX_UNAVAILABLE_EXIT_CODE:
        log.warning("self_heal_sandbox_unavailable")
        return SelfHealingResult(
            repair_performed=False,
            repair_success=False,
            repair_count=0,
            repair_duration_ms=0.0,
            sandbox_result=initial_result,
            initial_result=initial_result,
        )

    # 2. Failure classification check
    classification = classify_sandbox_failure(
        exit_code=initial_result.exit_code,
        stdout=initial_result.stdout,
        stderr=initial_result.stderr,
    )

    if not classification.is_repairable:
        log.info(
            "self_heal_not_repairable",
            category=classification.category,
            rule_id=classification.rule_id,
            reason=classification.reason,
        )
        return SelfHealingResult(
            repair_performed=False,
            repair_success=False,
            repair_count=0,
            repair_duration_ms=0.0,
            sandbox_result=initial_result,
            initial_result=initial_result,
            classification=classification,
        )

    # 3. Build surgical repair prompt payload
    repair_start_time = time.perf_counter()
    log.info(
        "self_heal_attempt_started",
        category=classification.category,
        rule_id=classification.rule_id,
        reason=classification.reason,
    )
    try:
        prompt_version = getattr(generation, "prompt_version", None) or "v1"
        builder = PromptBuilder(prompt_version=prompt_version)
        prompt_payload = builder.build_repair_prompt(
            source_code=source_code,
            generated_tests=current_code,
            traceback=initial_result.stderr,
            failure_category=classification.category,
            rule_id=classification.rule_id,
            failure_reason=classification.reason,
        )
    except Exception as prompt_exc:
        duration_ms = (time.perf_counter() - repair_start_time) * 1000.0
        log.warning("self_heal_prompt_building_failed", error=str(prompt_exc))
        return SelfHealingResult(
            repair_performed=True,
            repair_success=False,
            repair_count=1,
            repair_duration_ms=duration_ms,
            sandbox_result=initial_result,
            initial_result=initial_result,
            classification=classification,
        )

    # 4. LLM Repair Pass
    try:
        repaired_raw = provider.generate(prompt_payload)
    except Exception as llm_exc:
        duration_ms = (time.perf_counter() - repair_start_time) * 1000.0
        log.warning("self_heal_llm_failed", error=str(llm_exc))
        return SelfHealingResult(
            repair_performed=True,
            repair_success=False,
            repair_count=1,
            repair_duration_ms=duration_ms,
            sandbox_result=initial_result,
            initial_result=initial_result,
            classification=classification,
        )

    # 5. Validation Pipeline: reuse production TestCodeValidator
    from app.ai.validators import TestCodeValidator
    validator = TestCodeValidator()
    try:
        repaired_code = validator.validate_code(repaired_raw)
    except Exception as val_exc:
        duration_ms = (time.perf_counter() - repair_start_time) * 1000.0
        log.warning("self_heal_validation_failed", error=str(val_exc))
        return SelfHealingResult(
            repair_performed=True,
            repair_success=False,
            repair_count=1,
            repair_duration_ms=duration_ms,
            sandbox_result=initial_result,
            initial_result=initial_result,
            classification=classification,
        )

    # 6. Re-run sandbox ONCE with validated repaired code
    repaired_req = SandboxExecuteRequest(
        code=repaired_code,
        source_code=source_code,
        framework="pytest",
        timeout_seconds=settings.SANDBOX_TIMEOUT_SECONDS,
    )
    second_result = sandbox_client.execute(repaired_req)
    duration_ms = (time.perf_counter() - repair_start_time) * 1000.0
    repair_success = (second_result.exit_code == 0)

    log.info(
        "self_heal_second_execution_completed",
        initial_exit_code=initial_result.exit_code,
        second_exit_code=second_result.exit_code,
        repair_success=repair_success,
        duration_ms=duration_ms,
    )

    return SelfHealingResult(
        repair_performed=True,
        repair_success=repair_success,
        repair_count=1,
        repair_duration_ms=duration_ms,
        repaired_code=repaired_code,
        sandbox_result=second_result,
        initial_result=initial_result,
        classification=classification,
    )


def _strip_markdown(text: str) -> str:
    """Remove ```python ... ``` fences using TestCodeValidator."""
    from app.ai.validators import TestCodeValidator
    return TestCodeValidator._strip_markdown(text)


# ---------------------------------------------------------------------------
# Async entry point for FastAPI BackgroundTasks
# ---------------------------------------------------------------------------


async def execute_job(job_id: str, input_data: dict) -> None:
    """Async wrapper — offloads the synchronous pipeline to a thread pool.

    FastAPI BackgroundTasks calls this function. The function is async so
    it can use anyio.to_thread.run_sync to avoid blocking the event loop.

    Args:
        job_id:     UUID of the GenerationJob to execute.
        input_data: Pipeline input parameters (source_code, specification, etc.)
    """
    log = logger.bind(job_id=job_id)
    log.info("job_background_task_started")
    try:
        await anyio.to_thread.run_sync(
            lambda: _run_job_sync(job_id, input_data),
            abandon_on_cancel=False,
        )
    except Exception as exc:
        log.error("job_async_wrapper_error", error=str(exc), exc_info=True)


# ---------------------------------------------------------------------------
# Startup recovery
# ---------------------------------------------------------------------------


def startup_recovery() -> int:
    """Detect and recover crashed jobs at application startup.

    Algorithm (synchronous — called before the event loop is running):
      1. Mark all PROCESSING jobs as ORPHANED (they were running when
         the previous process crashed).
      2. For each ORPHANED job with retry_count < MAX_STARTUP_RETRIES,
         transition it back to PENDING via claim_for_retry().
      3. Return the count of jobs re-queued for recovery.

    The BackgroundTasks that will re-execute these jobs are scheduled by
    main.py after startup_recovery() completes (using asyncio.ensure_future
    or similar). Phase 3 schedules them at startup lifespan.

    Returns:
        Number of jobs queued for retry.
    """
    db = None
    try:
        db = SessionLocal()
        job_repo = JobRepository(db)

        # Step 1: PROCESSING → ORPHANED
        orphaned_ids = job_repo.mark_orphaned_jobs()
        if orphaned_ids:
            logger.warning(
                "startup_recovery_orphaned_jobs",
                count=len(orphaned_ids),
                job_ids=orphaned_ids,
            )

        # Step 2: ORPHANED → PENDING (for jobs that haven't exceeded retry limit)
        retried_count = 0
        orphaned_jobs = job_repo.get_jobs_by_status(JOB_STATUS_ORPHANED)
        for job in orphaned_jobs:
            if job.retry_count < MAX_STARTUP_RETRIES:
                if job_repo.claim_for_retry(job.id):
                    retried_count += 1
                    logger.info(
                        "startup_recovery_job_requeued",
                        job_id=job.id,
                        retry_count=job.retry_count,
                    )
            else:
                # Exceeded retry limit — mark FAILED
                job_repo.update(job.id, {
                    "status": JOB_STATUS_FAILED,
                    "error_code": "STARTUP_RETRY_EXHAUSTED",
                    "error_detail": (
                        f"Job exceeded maximum startup retries "
                        f"({MAX_STARTUP_RETRIES})."
                    ),
                })
                logger.warning(
                    "startup_recovery_retry_exhausted",
                    job_id=job.id,
                    retry_count=job.retry_count,
                )

        logger.info(
            "startup_recovery_complete",
            orphaned=len(orphaned_ids),
            requeued=retried_count,
        )
        return retried_count

    except Exception as exc:
        logger.error("startup_recovery_error", error=str(exc), exc_info=True)
        return 0
    finally:
        if db is not None:
            db.close()


async def schedule_recovery_jobs() -> None:
    """Re-execute PENDING recovery jobs that startup_recovery() re-queued.

    Called from the lifespan context manager after startup_recovery().
    Fetches all PENDING jobs that have retry_count > 0 (indicating they
    are recovery candidates, not freshly submitted jobs) and schedules
    background execution for each.
    """
    db = SessionLocal()
    try:
        job_repo = JobRepository(db)
        pending_jobs = job_repo.get_jobs_by_status(JOB_STATUS_PENDING)
        recovery_jobs = [j for j in pending_jobs if j.retry_count > 0]

        for job in recovery_jobs:
            # Reconstruct minimal input_data from stored checkpoint payload
            input_data: dict = {}
            if job.checkpoint_payload:
                try:
                    input_data = json.loads(job.checkpoint_payload)
                except Exception:
                    input_data = {}

            # Load original source_code from related Generation if available
            if "source_code" not in input_data and job.generation_id:
                try:
                    from app.repositories.generation_repository import (
                        GenerationRepository,
                    )
                    gen_repo = GenerationRepository(db)
                    gen = gen_repo.get_by_id(job.generation_id)
                    if gen:
                        input_data["source_code"] = gen.source_code
                        input_data["specification"] = gen.specification
                        input_data["language"] = gen.language
                        input_data["framework"] = gen.framework
                except Exception:
                    pass

            if "source_code" not in input_data or not input_data["source_code"]:
                logger.warning(
                    "startup_recovery_missing_source",
                    job_id=job.id,
                )
                continue

            input_data["resume_from_checkpoint"] = job.last_checkpoint
            input_data["checkpoint_payload"] = job.checkpoint_payload

            logger.info(
                "startup_recovery_rescheduling_job",
                job_id=job.id,
                checkpoint=job.last_checkpoint,
            )
            await execute_job(job.id, input_data)

    except Exception as exc:
        logger.error("schedule_recovery_jobs_error", error=str(exc), exc_info=True)
    finally:
        db.close()
