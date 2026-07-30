"""TestGen AI v2.3 — End-to-End Pipeline Orchestrator

Executes the complete Planner → Generator → Reviewer → Repair workflow
and produces a comprehensive V23GenerationResult with embedded analytics,
per-stage latencies, token usage, and structured outputs.
"""

import time
import uuid
from typing import Optional
import structlog

from app.agents.generator import GeneratorAgent
from app.agents.planner import PlannerAgent
from app.agents.repair import RepairAgent
from app.agents.reviewer import ReviewerAgent
from app.domain.v23_generation_result import V23GenerationResult, WorkflowAnalytics, WorkflowStageLatency
from app.domain.v23_models import AgentWorkflowContext, GenerationRequest
from app.exceptions.v23_exceptions import WorkflowExecutionError
from app.infrastructure.prompts.manager import PromptManager
from app.infrastructure.providers.router import LLMProviderRouter
from app.workflows.agent_workflow import AgentWorkflow

logger = structlog.get_logger()


class V23Pipeline:
    """Full end-to-end TestGen AI v2.3 pipeline.

    Orchestrates the complete multi-agent workflow and collects granular analytics
    across each stage, returning a V23GenerationResult.
    """

    def __init__(
        self,
        prompt_manager: Optional[PromptManager] = None,
        provider_router: Optional[LLMProviderRouter] = None,
    ) -> None:
        pm = prompt_manager or PromptManager()
        router = provider_router or LLMProviderRouter()

        self.workflow = AgentWorkflow(agents=[
            PlannerAgent(prompt_manager=pm, provider_router=router),
            GeneratorAgent(prompt_manager=pm, provider_router=router),
            ReviewerAgent(prompt_manager=pm, provider_router=router),
            RepairAgent(prompt_manager=pm, provider_router=router),
        ])
        self.log = logger.bind(component="V23Pipeline")

    def run(self, request: GenerationRequest, request_id: Optional[str] = None) -> V23GenerationResult:
        """Execute the full workflow and return V23GenerationResult.

        Args:
            request: Incoming GenerationRequest.
            request_id: Optional external request correlation ID.

        Returns:
            V23GenerationResult with all artifacts and analytics.
        """
        req_id = request_id or str(uuid.uuid4())
        workflow_id = self.workflow.workflow_id
        self.log.info("v23_pipeline_started", workflow_id=workflow_id, request_id=req_id)

        stage_latencies: dict = {}
        pipeline_start = time.perf_counter()

        try:
            # ── Stage 1: Repository Context ──────────────────────────
            t0 = time.perf_counter()
            # Context init is inside AgentWorkflow
            stage_latencies["repository_context_ms"] = 0.0  # In Phase 3 this is populated separately

            # ── Stages 2-5: Multi-Agent Workflow ─────────────────────
            context = self.workflow.execute_workflow(request)
            total_ms = round((time.perf_counter() - pipeline_start) * 1000, 2)

            # Derive per-stage latencies from reasoning traces
            stage_latencies = _derive_stage_latencies(context, total_ms)

            # ── Build V23GenerationResult ─────────────────────────────
            result = _build_result(
                context=context,
                request=request,
                workflow_id=workflow_id,
                request_id=req_id,
                stage_latencies=stage_latencies,
                total_ms=total_ms,
                status="completed",
            )
            self.log.info(
                "v23_pipeline_completed",
                workflow_id=workflow_id,
                request_id=req_id,
                total_ms=total_ms,
                tests_count=result.generated_test_count,
                repair_count=result.repair_count,
                review_score=result.analytics.review_score,
            )
            return result

        except WorkflowExecutionError as exc:
            total_ms = round((time.perf_counter() - pipeline_start) * 1000, 2)
            self.log.error("v23_pipeline_failed", workflow_id=workflow_id, request_id=req_id, error=str(exc))
            return V23GenerationResult(
                workflow_id=workflow_id,
                request_id=req_id,
                status="failed",
                workflow_status="failed",
                total_execution_ms=total_ms,
                failure_reason=str(exc),
            )


def _derive_stage_latencies(context: AgentWorkflowContext, total_ms: float) -> dict:
    """Estimate per-stage latencies from reasoning traces (equal split if unavailable)."""
    traces = context.reasoning_traces
    n = max(len(traces), 1)
    per_stage = round(total_ms / n, 2)

    planning_ms = per_stage
    generation_ms = per_stage
    review_ms = per_stage
    repair_ms = 0.0

    # Check if repair was executed
    if context.repair_history:
        repair_ms = per_stage

    return {
        "repository_context_ms": 0.0,
        "planning_ms": planning_ms,
        "generation_ms": generation_ms,
        "review_ms": review_ms,
        "repair_ms": repair_ms,
        "total_ms": total_ms,
    }


def _build_result(
    context: AgentWorkflowContext,
    request: GenerationRequest,
    workflow_id: str,
    request_id: str,
    stage_latencies: dict,
    total_ms: float,
    status: str,
) -> V23GenerationResult:
    """Convert AgentWorkflowContext into a complete V23GenerationResult."""
    review = context.review_report
    provider_decision = context.provider_decision

    # Serialise generated tests
    generated_tests_dicts = []
    for gt in (context.generated_tests or []):
        generated_tests_dicts.append({
            "test_name": gt.test_name,
            "test_code": gt.test_code,
            "target_function": gt.target_function,
            "target_module": gt.target_module,
            "framework": gt.framework,
            "imports": list(gt.imports),
            "confidence": gt.confidence,
        })

    # Serialise review report
    review_dict = None
    if review:
        review_dict = {
            "is_approved": review.is_approved,
            "overall_score": review.overall_score,
            "summary": review.summary,
            "coverage_analysis": review.coverage_analysis,
            "issues": list(review.issues),
            "strengths": list(review.strengths),
            "recommendations": list(review.recommendations),
            "confidence": review.confidence,
        }

    # Serialise repair history
    repair_dicts = []
    for action in (context.repair_history or []):
        repair_dicts.append({
            "repair_type": action.repair_type,
            "reason": action.reason,
            "original_code_length": len(action.original_code),
            "repaired_code_length": len(action.repaired_code),
        })

    # Provider info
    provider_name = provider_decision.selected_provider if provider_decision else "unknown"
    estimated_cost = provider_decision.estimated_cost if provider_decision else 0.0
    token_usage = context.token_usage

    # Test plan summary
    plan_summary: dict = {}
    if context.test_plan:
        plan_summary = {
            "target_functions": list(context.test_plan.target_functions),
            "test_cases_count": len(context.test_plan.test_cases),
            "edge_cases_count": len(context.test_plan.edge_cases),
            "mock_requirements": list(context.test_plan.mock_requirements),
        }

    # Repository metadata
    repo_meta: dict = {}
    if context.repository_context:
        rc = context.repository_context
        repo_meta = {
            "functions_count": len(rc.functions),
            "classes_count": len(rc.classes),
            "files_count": len(rc.files),
            "dependencies": list(rc.dependencies),
        }

    # Analytics
    latency_obj = WorkflowStageLatency(
        repository_context_ms=stage_latencies.get("repository_context_ms", 0.0),
        planning_ms=stage_latencies.get("planning_ms", 0.0),
        generation_ms=stage_latencies.get("generation_ms", 0.0),
        review_ms=stage_latencies.get("review_ms", 0.0),
        repair_ms=stage_latencies.get("repair_ms", 0.0),
        total_ms=total_ms,
    )
    analytics = WorkflowAnalytics(
        latency=latency_obj,
        provider_used=provider_name,
        prompt_tokens=token_usage.prompt_tokens,
        completion_tokens=token_usage.completion_tokens,
        total_tokens=token_usage.total_tokens,
        estimated_cost_usd=estimated_cost,
        review_score=review.overall_score if review else 0.0,
        approved=review.is_approved if review else True,
        repair_count=len(repair_dicts),
        generated_test_count=len(generated_tests_dicts),
        issue_count=len(review.issues) if review else 0,
    )

    # Reasoning traces
    trace_dicts = []
    for t in context.reasoning_traces:
        trace_dicts.append({
            "timestamp": t.timestamp,
            "agent_name": t.agent_name,
            "step_action": t.step_action,
            "rationale_summary": t.rationale_summary,
        })

    return V23GenerationResult(
        workflow_id=workflow_id,
        request_id=request_id,
        status=status,
        source_code_summary=request.source_code[:200] + ("..." if len(request.source_code) > 200 else ""),
        repository_metadata=repo_meta,
        test_plan_summary=plan_summary,
        generated_tests=generated_tests_dicts,
        generated_test_count=len(generated_tests_dicts),
        review_report=review_dict,
        repair_history=repair_dicts,
        repair_count=len(repair_dicts),
        provider_decisions=[{
            "provider": provider_name,
            "strategy": provider_decision.strategy_used if provider_decision else "N/A",
            "estimated_cost": estimated_cost,
            "latency_ms": provider_decision.latency_ms if provider_decision else 0.0,
        }],
        analytics=analytics,
        total_prompt_tokens=token_usage.prompt_tokens,
        total_completion_tokens=token_usage.completion_tokens,
        total_tokens=token_usage.total_tokens,
        estimated_cost_usd=estimated_cost,
        total_execution_ms=total_ms,
        workflow_status=status,
        failure_reason=None,
        reasoning_traces=trace_dicts,
    )
