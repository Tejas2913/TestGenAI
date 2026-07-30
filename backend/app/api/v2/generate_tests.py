"""TestGen AI v2.3 — POST /api/v2/generate-tests REST Endpoint

Production endpoint exposing the full multi-agent AI pipeline synchronously.
Accepts source code, executes PlannerAgent → GeneratorAgent → ReviewerAgent → RepairAgent,
and returns V23GenerationResult as a structured JSON response.
"""

import uuid
from typing import Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.auth.dependencies import require_active_user
from app.domain.v23_models import GenerationRequest
from app.models.user import User
from app.workflows.v23_pipeline import V23Pipeline

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/generate-tests", tags=["generate-tests-v23"])


class GenerateTestsRequest(BaseModel):
    """Request body for POST /api/v2/generate-tests."""

    source_code: str = Field(..., min_length=10, description="Source code to generate tests for")
    specification: Optional[str] = Field(None, description="Optional natural language specification")
    language: str = Field("python", description="Programming language (default: python)")
    framework: str = Field("pytest", description="Test framework (default: pytest)")


class GenerateTestsResponse(BaseModel):
    """Structured GenerationResult response schema."""

    workflow_id: str
    request_id: str
    status: str
    generated_test_count: int
    repair_count: int
    total_execution_ms: float
    estimated_cost_usd: float
    review_score: float
    approved: bool
    generated_tests: list
    review_report: Optional[dict]
    repair_history: list
    analytics: dict
    reasoning_traces: list
    repository_metadata: dict
    test_plan_summary: dict
    provider_decisions: list


@router.post(
    "/",
    response_model=GenerateTestsResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate unit tests using the full multi-agent AI pipeline",
)
async def generate_tests(
    body: GenerateTestsRequest,
    request: Request,
    current_user: User = Depends(require_active_user),
) -> GenerateTestsResponse:
    """Execute the complete TestGen AI v2.3 multi-agent pipeline and return structured results.

    Executes in order:
      1. PlannerAgent — builds TestPlan from RepositoryContext
      2. GeneratorAgent — produces GeneratedTest objects from TestPlan
      3. ReviewerAgent — evaluates and scores GeneratedTests
      4. RepairAgent — surgically improves tests (only when review is not approved)

    Returns:
        GenerateTestsResponse with all artifacts and analytics.

    Raises:
        422 Unprocessable Entity: If source_code is missing or too short.
        500 Internal Server Error: If pipeline execution fails unexpectedly.
    """
    request_id = str(getattr(request.state, "request_id", uuid.uuid4()))
    log = logger.bind(
        endpoint="POST /api/v2/generate-tests",
        user_id=str(current_user.id),
        request_id=request_id,
    )
    log.info("generate_tests_request_received", language=body.language, framework=body.framework)

    generation_request = GenerationRequest(
        source_code=body.source_code,
        specification=body.specification,
        language=body.language,
        framework=body.framework,
        user_id=str(current_user.id),
    )

    try:
        pipeline = V23Pipeline()
        result = pipeline.run(generation_request, request_id=request_id)
    except Exception as exc:
        log.error("generate_tests_pipeline_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline execution failed: {exc}",
        )

    if result.status == "failed":
        log.warning("generate_tests_pipeline_returned_failed", reason=result.failure_reason)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline failed: {result.failure_reason}",
        )

    log.info(
        "generate_tests_completed",
        workflow_id=result.workflow_id,
        tests_count=result.generated_test_count,
        repair_count=result.repair_count,
        total_ms=result.total_execution_ms,
        review_score=result.analytics.review_score,
    )

    return GenerateTestsResponse(
        workflow_id=result.workflow_id,
        request_id=result.request_id,
        status=result.status,
        generated_test_count=result.generated_test_count,
        repair_count=result.repair_count,
        total_execution_ms=result.total_execution_ms,
        estimated_cost_usd=result.estimated_cost_usd,
        review_score=result.analytics.review_score,
        approved=result.analytics.approved,
        generated_tests=result.generated_tests,
        review_report=result.review_report,
        repair_history=result.repair_history,
        analytics=result.analytics.__dict__ if hasattr(result.analytics, "__dict__") else {},
        reasoning_traces=result.reasoning_traces,
        repository_metadata=result.repository_metadata,
        test_plan_summary=result.test_plan_summary,
        provider_decisions=result.provider_decisions,
    )
