"""Async Job API routes — Phase 3.

Implements:
  POST /api/v2/jobs/generate — Submit source code for async test generation.
                               Returns 202 Accepted with a job_id immediately.
  GET  /api/v2/jobs/{job_id} — Poll job status and retrieve generation_id
                               on completion.

Architecture rules:
  - Routes are thin; all business logic lives in job_engine.py.
  - Both endpoints require authentication (require_active_user).
  - POST schedules a BackgroundTask — the HTTP response is returned
    before pipeline execution begins.
  - The event loop is never blocked (blocking work is offloaded in the engine).
"""

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Request

from app.auth.dependencies import require_active_user
from app.core.config import settings
from app.exceptions import NotFoundException
from app.models.user import User
from app.repositories.job_repository import JobRepository
from app.schemas.job import JobStatusResponse, JobSubmitRequest, JobSubmitResponse
from app.services.job_engine import execute_job
from dependencies import get_job_repository

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post(
    "/generate",
    response_model=JobSubmitResponse,
    status_code=202,
    summary="Submit source code for async test generation",
)
async def submit_job(
    body: JobSubmitRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: User = Depends(require_active_user),
    job_repo: JobRepository = Depends(get_job_repository),
) -> JobSubmitResponse:
    """Accept a generation request, create a PENDING job, and return immediately.

    The actual test generation pipeline runs asynchronously as a BackgroundTask.
    Use GET /api/v2/jobs/{job_id} to poll for completion.

    Returns:
        HTTP 202 Accepted with the job_id.
    """
    request_id = request.state.request_id if hasattr(request.state, "request_id") else "unknown"

    # Create the job record in PENDING state
    job = job_repo.create({
        "status": "pending",
        "user_id": current_user.id,
        "retry_count": 0,
    })

    logger.info(
        "job_submitted",
        job_id=job.id,
        user_id=current_user.id,
        request_id=request_id,
    )

    # Build the input payload the engine will consume
    input_data = {
        "source_code": body.source_code,
        "specification": body.specification,
        "language": body.language,
        "framework": body.framework,
    }

    # Schedule the background execution — returns immediately
    background_tasks.add_task(execute_job, job.id, input_data)

    return JobSubmitResponse(
        job_id=job.id,
        status=job.status,
        message="Job accepted and queued for processing.",
    )


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Poll async job status",
)
async def get_job_status(
    job_id: str,
    current_user: User = Depends(require_active_user),
    job_repo: JobRepository = Depends(get_job_repository),
) -> JobStatusResponse:
    """Return the current status of an async generation job.

    When status is 'completed', the response includes generation_id which
    can be used to retrieve the full generation result via the V1 endpoint:
    GET /api/v1/generations/{generation_id}

    Phase 4: When status='completed' and ENABLE_CONFIDENCE=True, the response
    also includes a `confidence` block with the generation quality assessment.

    Returns:
        JobStatusResponse with current lifecycle state.

    Raises:
        404 Not Found if the job_id does not exist.
    """
    job = job_repo.get_by_id(job_id)
    if job is None:
        raise NotFoundException(detail=f"Job '{job_id}' not found.")

    # ----------------------------------------------------------------
    # Phase 4: Compute confidence for completed jobs
    # ----------------------------------------------------------------
    confidence_schema = None
    if (
        job.status == "completed"
        and job.generation_id is not None
        and settings.ENABLE_CONFIDENCE
    ):
        try:
            from app.evaluation.confidence import calculate_confidence
            from app.repositories.generation_repository import GenerationRepository
            from app.schemas.confidence import (
                ConfidenceMetaSchema,
                ConfidenceSchema,
                ConfidenceSignalsSchema,
            )

            gen_repo = GenerationRepository(job_repo._session)
            gen = gen_repo.get_by_id(job.generation_id)
            if gen is not None and gen.generated_tests_json:
                import json
                parsed = json.loads(gen.generated_tests_json)
                test_count = len(parsed.get("test_cases", []))
                score = calculate_confidence(
                    test_count=test_count,
                    validation_warnings=[],
                    sandbox_exit_code=gen.sandbox_exit_code,
                )
                confidence_schema = ConfidenceSchema(
                    overall=score.overall,
                    grade=score.grade,
                    signals=ConfidenceSignalsSchema(
                        sandbox=score.sandbox_signal,
                        validation=score.validation_signal,
                        test_count=score.test_count_signal,
                    ),
                    metadata=ConfidenceMetaSchema(
                        test_count=score.test_count,
                        warning_count=score.warning_count,
                        sandbox_exit_code=score.sandbox_exit_code,
                    ),
                )
        except Exception as exc:
            logger.warning("confidence_computation_failed", error=str(exc), job_id=job_id)

    # ----------------------------------------------------------------
    # V2.2: Extract quality metrics for completed jobs
    # ----------------------------------------------------------------
    quality_schema = None
    if job.status == "completed" and job.generation_id is not None:
        try:
            from app.repositories.generation_repository import GenerationRepository
            from app.schemas.quality import (
                QualityBreakdownResponse,
                QualityMetricsResponse,
                QualityPipelineStatus,
                MutationSummaryResponse,
                TestSmellSummaryResponse,
            )
            import json

            gen_repo = GenerationRepository(job_repo._session)
            gen = gen_repo.get_by_id(job.generation_id)
            if gen is not None and getattr(gen, "quality_score", None) is not None:
                smell_breakdown = {}
                if getattr(gen, "smell_breakdown_json", None):
                    try:
                        smell_breakdown = json.loads(gen.smell_breakdown_json)
                    except Exception:
                        pass

                mut_resp = MutationSummaryResponse(
                    total_mutants=(gen.killed_mutants or 0) + (gen.survived_mutants or 0) + (gen.timeout_mutants or 0) + (gen.error_mutants or 0),
                    killed_mutants=gen.killed_mutants or 0,
                    survived_mutants=gen.survived_mutants or 0,
                    timeout_mutants=gen.timeout_mutants or 0,
                    incompatible_mutants=gen.error_mutants or 0,
                    mutation_score_pct=gen.mutation_score or 0.0,
                    duration_ms=0.0,
                )
                smell_resp = TestSmellSummaryResponse(
                    total_smells=gen.smell_count or 0,
                    high_severity_count=smell_breakdown.get("high", 0),
                    medium_severity_count=smell_breakdown.get("medium", 0),
                    low_severity_count=smell_breakdown.get("low", 0),
                )
                breakdown = QualityBreakdownResponse(
                    coverage_score=gen.coverage_line_pct or 0.0,
                    mutation_score=gen.mutation_score or 0.0,
                    smell_hygiene_score=max(0.0, 100.0 - (gen.smell_count or 0) * 5.0),
                    semantic_score=0.0,
                )
                quality_schema = QualityMetricsResponse(
                    overall_score=gen.quality_score or 0.0,
                    rating=gen.quality_rating or "UNKNOWN",
                    pipeline_status=QualityPipelineStatus.COMPLETED,
                    breakdown=breakdown,
                    mutation=mut_resp,
                    smells=smell_resp,
                )
        except Exception as exc:
            logger.warning("quality_metrics_extraction_failed", error=str(exc), job_id=job_id)

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        retry_count=job.retry_count,
        last_checkpoint=job.last_checkpoint,
        checkpoint_updated_at=job.checkpoint_updated_at,
        generation_id=job.generation_id,
        error_code=job.error_code,
        error_detail=job.error_detail,
        created_at=job.created_at,
        updated_at=job.updated_at,
        confidence=confidence_schema,
        quality_metrics=quality_schema,
    )


@router.get(
    "/{job_id}/quality",
    summary="Retrieve job quality evaluation metrics",
)
async def get_job_quality(
    job_id: str,
    current_user: User = Depends(require_active_user),
    job_repo: JobRepository = Depends(get_job_repository),
):
    """Retrieve composite quality metrics for a completed job."""
    status_resp = await get_job_status(job_id=job_id, current_user=current_user, job_repo=job_repo)
    if status_resp.quality_metrics is None:
        raise NotFoundException(detail=f"Quality metrics for job '{job_id}' not available.")
    return status_resp.quality_metrics


@router.get(
    "/{job_id}/mutation-summary",
    summary="Retrieve job mutation testing summary",
)
async def get_job_mutation_summary(
    job_id: str,
    current_user: User = Depends(require_active_user),
    job_repo: JobRepository = Depends(get_job_repository),
):
    """Retrieve mutation testing summary for a completed job."""
    status_resp = await get_job_status(job_id=job_id, current_user=current_user, job_repo=job_repo)
    if status_resp.quality_metrics is None:
        raise NotFoundException(detail=f"Mutation summary for job '{job_id}' not available.")
    return status_resp.quality_metrics.mutation


@router.get(
    "/{job_id}/smells",
    summary="Retrieve job test smell diagnostics",
)
async def get_job_smells(
    job_id: str,
    current_user: User = Depends(require_active_user),
    job_repo: JobRepository = Depends(get_job_repository),
):
    """Retrieve static test smell diagnostics for a completed job."""
    status_resp = await get_job_status(job_id=job_id, current_user=current_user, job_repo=job_repo)
    if status_resp.quality_metrics is None:
        raise NotFoundException(detail=f"Test smell diagnostics for job '{job_id}' not available.")
    return status_resp.quality_metrics.smells
